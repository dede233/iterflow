import unicodedata


def requirement_title(value: str) -> str:
    if "\x00" in value:
        raise ValueError("需求标题不能包含空字符")
    value = value.strip()
    visible = [c for c in value if not c.isspace() and unicodedata.category(c) not in {"Cc", "Cf"}]
    if len(visible) < 2:
        raise ValueError("需求标题至少需要 2 个可见字符")
    return value
