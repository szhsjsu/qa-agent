from qa_agent.ingest.chunker import _is_clause_start, _extract_clause_id, chunk_page_text


def test_clause_detection():
    assert _is_clause_start("第三条 风险控制")
    assert _is_clause_start("3.2.1 资产负债")
    assert _is_clause_start("一、总则")
    assert not _is_clause_start("普通段落开头")


def test_clause_id_extract():
    assert _extract_clause_id("第三条 风险控制") == "第三条"
    assert _extract_clause_id("3.2 控制目标 内容内容") == "3.2"
    assert _extract_clause_id("普通段落") is None


def test_chunker_keeps_clause_together():
    text = "第一条 总则\n本规定旨在……\n第二条 适用范围\n适用于……"
    chunks = chunk_page_text(text, page=1, doc_id="d1")
    assert len(chunks) == 2
    assert chunks[0]["clause_id"] == "第一条"
    assert chunks[1]["clause_id"] == "第二条"


def test_chunker_empty():
    assert chunk_page_text("", 1, "d1") == []
