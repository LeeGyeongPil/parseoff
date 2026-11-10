from __future__ import annotations

from parseoff import metrics


def test_words_normalise_case_unicode_and_markdown() -> None:
    assert metrics.words("| ＡＢＣ | Q1 |\n| --- | --- |\n# Head") == ["abc", "q1", "head"]


def test_coverage_counts_multiset_and_is_none_for_empty_reference() -> None:
    assert metrics.coverage("a b b c", "a b c") == 0.75  # one of the two "b" is missing
    assert metrics.coverage("", "anything") is None
    assert metrics.coverage("   \n", "") is None
    assert metrics.coverage("a b", "") == 0.0


def test_agreement_order_sensitive_and_boundaries() -> None:
    assert metrics.agreement("one two three", "one two three") == 1.0
    assert metrics.agreement("a b c d", "c d a b") < 0.6
    assert metrics.agreement("", "") is None
    assert metrics.agreement("x", "") == 0.0


def test_table_and_heading_counts() -> None:
    md = "# Title\ntext\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\nmore\n\n| x | y |\n|:---|---:|\n| 3 | 4 |"
    assert metrics.count_tables(md) == 2
    assert metrics.count_headings(md) == 1
    assert metrics.count_tables("| just | pipes |\n| no | separator |") == 0
    assert metrics.count_headings("#hashtag is not a heading") == 0


def test_repeated_lines_need_enough_pages() -> None:
    pages = [f"ACME report\nbody {i} unique text here\nPage {i} of 4" for i in range(1, 5)]
    ratio, example = metrics.repeated_line_ratio(pages)
    assert ratio > 0.5 and example in {"acme report", "page # of #"}
    assert metrics.repeated_line_ratio(pages[:2]) == (0.0, "")  # two pages cannot prove repetition
    assert metrics.repeated_line_ratio(["", "", ""]) == (0.0, "")


def test_token_estimate_rounds_up() -> None:
    assert metrics.estimate_tokens("") == 0
    assert metrics.estimate_tokens("abcde") == 2
