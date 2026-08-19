from app.processing.cleaner import clean_text


def test_collapses_repeated_whitespace():
    assert clean_text("hello    world") == "hello world"


def test_collapses_excessive_newlines():
    result = clean_text("para one\n\n\n\n\npara two")
    assert result == "para one\n\npara two"


def test_strips_null_and_control_characters():
    result = clean_text("hello\x00world\x0bthere")
    assert "\x00" not in result
    assert "\x0b" not in result


def test_normalizes_crlf_line_endings():
    result = clean_text("line one\r\nline two\r\n")
    assert "\r" not in result
    assert "line one\nline two" in result


def test_preserves_meaningful_content():
    original = "The quick brown fox jumps over the lazy dog."
    assert clean_text(original) == original


def test_empty_input_returns_empty_string():
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_trims_trailing_whitespace_per_line():
    result = clean_text("hello   \nworld   ")
    assert result == "hello\nworld"
