"""Requirement content normalization. Plain legacy text is never interpreted as HTML."""

import unicodedata
from html.parser import HTMLParser

import nh3

MAX_DESCRIPTION_LENGTH = 100_000
# Both supported databases currently store descriptions in a TEXT column.
MAX_DESCRIPTION_BYTES = 60_000
TAGS = {
    "p",
    "br",
    "h2",
    "h3",
    "strong",
    "b",
    "em",
    "i",
    "s",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "a",
}
CLEANER = nh3.Cleaner(
    tags=TAGS,
    clean_content_tags={"script", "style", "iframe", "object", "template", "svg", "math"},
    attributes={"a": {"href", "title"}, "ol": {"start"}},
    url_schemes={"http", "https", "mailto"},
    url_relative="deny",
    link_rel="noopener noreferrer nofollow",
    set_tag_attribute_values={"a": {"target": "_blank"}},
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sanitize_requirement_description(value: str, format: str) -> str:
    if format not in {"PLAIN", "HTML"}:
        raise ValueError("不支持的需求描述格式")
    if "\x00" in value:
        raise ValueError("需求描述不能包含空字符")
    if len(value) > MAX_DESCRIPTION_LENGTH:
        raise ValueError("需求描述不能超过 100000 个字符")
    result = value if format == "PLAIN" else CLEANER.clean(value)
    if format == "HTML":
        extractor = _TextExtractor()
        extractor.feed(result)
        visible = "".join(extractor.parts)
    else:
        visible = result
    visible_characters = [
        c for c in visible if not c.isspace() and unicodedata.category(c) not in {"Cc", "Cf"}
    ]
    if len(visible_characters) < 2:
        raise ValueError("需求描述至少需要 2 个文字字符")
    if len(result.encode("utf-8")) > MAX_DESCRIPTION_BYTES:
        raise ValueError("需求描述内容过长, 请精简文字或格式")
    return result
