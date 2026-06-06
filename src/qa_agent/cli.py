"""CLI entrypoint."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import settings
from .ingest import ingest_pdf
from .index import build_index, load_index
from .retrieval import retrieve
from .agent import answer_question

app = typer.Typer(add_completion=False, help="Scanned-PDF QA Agent.")
console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def ingest(
    pdf: Path = typer.Argument(..., exists=True, readable=True),
    cache_dir: Path = typer.Option(Path("data/cache"), help="ingest 输出目录"),
    index_dir: Path = typer.Option(settings.index_dir, help="索引目录"),
    embed_model: str = typer.Option(settings.embedding_model),
    doc_id: str = typer.Option(None, help="文档 id，默认取文件名"),
):
    """解析 PDF → 切块 → 建立索引（一步到位）。"""
    meta = ingest_pdf(pdf, cache_dir, doc_id=doc_id)
    console.print(f"[green]ingest done[/green]: {meta['n_pages']} pages, {meta['n_chunks']} chunks, {meta['n_tables']} tables")
    chunks_path = cache_dir / f"{meta['doc_id']}.chunks.jsonl"
    imeta = build_index(chunks_path, index_dir, embed_model)
    console.print(f"[green]index built[/green]: dim={imeta['dim']} n={imeta['n_chunks']}")


@app.command()
def retrieve_cmd(
    question: str = typer.Argument(...),
    index_dir: Path = typer.Option(settings.index_dir),
    top_k: int = typer.Option(5),
):
    """只跑检索，看命中哪些 chunks。"""
    b = load_index(index_dir)
    results = retrieve(b, question, top_k_final=top_k)
    t = Table(title=f"retrieval: {question}")
    t.add_column("score"); t.add_column("page"); t.add_column("type"); t.add_column("sources"); t.add_column("preview")
    for r in results:
        t.add_row(f"{r.score:.3f}", str(r.chunk["page"]), r.chunk["type"], ",".join(r.sources), r.chunk["text"][:60])
    console.print(t)


@app.command()
def inspect(
    page: int = typer.Option(None, help="只看某页；不传则看 meta 汇总"),
    cache_dir: Path = typer.Option(Path("data/cache"), help="ingest 输出目录"),
    doc_id: str = typer.Option(None, help="文档 id，默认取 cache_dir 下唯一一份"),
):
    """查看 PDF 解析结果：每页是否扫描、OCR 置信度、抽出的正文与表格。"""
    if doc_id is None:
        metas = list(cache_dir.glob("*.meta.json"))
        if not metas:
            console.print("[red]未找到 ingest 结果，先跑 qa ingest[/red]"); raise typer.Exit(1)
        doc_id = metas[0].stem.replace(".meta", "")
    meta = json.loads((cache_dir / f"{doc_id}.meta.json").read_text())
    chunks = [json.loads(l) for l in (cache_dir / f"{doc_id}.chunks.jsonl").read_text().splitlines()]

    if page is None:
        console.print(f"[bold]文档[/bold] {meta['doc_id']}  共 {meta['n_pages']} 页 / {meta['n_chunks']} chunks / {meta['n_tables']} 表格\n")
        t = Table(title="每页解析路由 (PDF 类型判别)")
        t.add_column("page"); t.add_column("scanned"); t.add_column("text_layer_chars"); t.add_column("ocr_conf"); t.add_column("# chunks")
        per_page = {}
        for c in chunks:
            per_page[c["page"]] = per_page.get(c["page"], 0) + 1
        for p in meta["pages"]:
            t.add_row(
                str(p["page"]),
                "[yellow]Y[/yellow]" if p["is_scanned"] else "[green]N[/green]",
                str(p["text_layer_chars"]),
                f"{p['ocr_conf']:.3f}" if p["ocr_conf"] is not None else "-",
                str(per_page.get(p["page"], 0)),
            )
        console.print(t)
        console.print("\n[dim]看某页详情：qa inspect --page 1[/dim]")
        return

    page_chunks = [c for c in chunks if c["page"] == page]
    info = next((p for p in meta["pages"] if p["page"] == page), None)
    if not info:
        console.print(f"[red]页 {page} 不存在[/red]"); raise typer.Exit(1)
    console.print(f"\n[bold cyan]── 第 {page} 页 ──[/bold cyan]")
    console.print(f"  is_scanned = {info['is_scanned']}  text_layer_chars = {info['text_layer_chars']}  ocr_conf = {info['ocr_conf']}")
    console.print(f"  chunks: {len(page_chunks)} (text={sum(1 for c in page_chunks if c['type']!='table')}, table={sum(1 for c in page_chunks if c['type']=='table')})")

    for c in page_chunks:
        console.print(f"\n[bold]· {c['chunk_id']}[/bold]  type=[yellow]{c['type']}[/yellow]  clause={c.get('clause_id')}")
        if c["type"] == "table" and c.get("table_md"):
            console.print("[dim]── Markdown ──[/dim]")
            console.print(c["table_md"][:1500])
            if c.get("table_desc"):
                console.print("[dim]── 自然语言 (供向量检索) ──[/dim]")
                console.print(c["table_desc"][:500])
        else:
            console.print(c["text"][:800])


@app.command()
def ask(
    question: str = typer.Argument(...),
    index_dir: Path = typer.Option(settings.index_dir),
    json_out: bool = typer.Option(False, "--json", help="只输出 JSON"),
):
    """问答。"""
    b = load_index(index_dir)
    result = answer_question(b, question)
    if json_out:
        console.print_json(result.model_dump_json())
        return
    color = "red" if result.refused else "green"
    console.print(f"[bold {color}]A:[/bold {color}] {result.answer}")
    if result.citations:
        console.print("[dim]引用:[/dim]")
        for c in result.citations:
            console.print(f"  · p{c.page}: {c.quote}")
    console.print(f"[dim]confidence={result.confidence} grounded={result.grounded} latency={result.latency_ms:.0f}ms[/dim]")
    if result.reason:
        console.print(f"[dim]reason: {result.reason}[/dim]")


if __name__ == "__main__":
    app()
