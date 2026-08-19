"""
Text cleaning / normalization.

Deliberately conservative: strips control characters, collapses
excessive whitespace/newlines, and normalizes line endings, but never
rewrites or removes meaningful words/content.
"""
import re
import unicodedata

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", "")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _TRAILING_WS_RE.sub("\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()
