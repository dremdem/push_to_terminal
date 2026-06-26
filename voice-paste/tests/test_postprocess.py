from voice_paste.postprocess import process


def test_trims_leading_trailing_whitespace():
    assert process("  hello world  ") == "hello world"


def test_collapses_excessive_blank_lines():
    assert process("hello\n\n\n\nworld") == "hello\n\nworld"


def test_terminal_mode_joins_lines():
    assert process("hello\nworld", terminal_mode=True) == "hello world"


def test_terminal_mode_collapses_multiple_spaces():
    assert process("hello   world", terminal_mode=True) == "hello   world"


def test_preserves_punctuation():
    assert process("Hello, world!") == "Hello, world!"


def test_no_trailing_newline():
    result = process("hello\n")
    assert not result.endswith("\n")


def test_empty_string():
    assert process("") == ""


def test_only_whitespace_returns_empty():
    assert process("   \n  \n  ") == ""
