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
