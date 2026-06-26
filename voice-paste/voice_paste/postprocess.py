import re


def process(text: str, *, terminal_mode: bool = False) -> str:
    text = text.strip()
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    if terminal_mode:
        text = " ".join(text.splitlines())
    return text
