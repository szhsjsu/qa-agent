from qa_agent.retrieval.hybrid import _expand_query


def test_expand_includes_numeric_form():
    variants = _expand_query("第三条规定了什么")
    assert any("第三条" in v for v in variants)


def test_expand_dotted_number():
    variants = _expand_query("查看 3.2.1 的内容")
    assert any("3.2.1" in v for v in variants)


def test_expand_table_keyword():
    variants = _expand_query("表格中第二行")
    assert any("表格" in v for v in variants)
