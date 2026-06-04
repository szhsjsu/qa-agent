from qa_agent.ingest.tables import table_to_markdown, table_to_nl


def test_md_basic():
    grid = [["A", "B"], ["1", "2"]]
    md = table_to_markdown(grid)
    assert "| A | B |" in md
    assert "| 1 | 2 |" in md


def test_nl_basic():
    grid = [["公司", "金额"], ["X", "100"], ["Y", "200"]]
    nl = table_to_nl(grid)
    assert "公司=X" in nl
    assert "金额=100" in nl
