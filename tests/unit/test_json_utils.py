from app.llm.json_utils import extract_json


def test_extract_json_finds_embedded_object():
    text = 'Sure, here you go: {"score": 0.8, "label": "RELEVANT", "reason": "ok"} thanks'
    assert extract_json(text) == {"score": 0.8, "label": "RELEVANT", "reason": "ok"}


def test_extract_json_returns_none_for_no_json():
    assert extract_json("no json here") is None


def test_extract_json_returns_none_for_broken_json():
    assert extract_json("{score: 0.8 broken}") is None


def test_extract_json_ignores_trailing_braces_after_the_real_object():
    """Regression test: a greedy `\\{.*\\}` regex would span from the first `{` to the *last*
    `}` in the text, swallowing this trailing brace and failing to parse otherwise-valid JSON."""
    text = 'Here you go: {"score": 0.9, "label": "RELEVANT", "reason": "matches"} let me know if you want more {details}.'
    assert extract_json(text) == {"score": 0.9, "label": "RELEVANT", "reason": "matches"}


def test_extract_json_skips_leading_stray_braces_before_the_real_object():
    """The first `{` in this text starts "{A, B}" -- a balanced but non-JSON substring. The
    scanner must move past it and try the next `{` rather than giving up."""
    text = 'The passage discusses {A, B} topics. {"score": 0.5, "label": "PARTIALLY_RELEVANT", "reason": "some overlap"}'
    assert extract_json(text) == {"score": 0.5, "label": "PARTIALLY_RELEVANT", "reason": "some overlap"}


def test_extract_json_handles_nested_braces_correctly():
    text = '{"claims": ["fact one"], "meta": {"nested": true}}'
    assert extract_json(text) == {"claims": ["fact one"], "meta": {"nested": True}}
