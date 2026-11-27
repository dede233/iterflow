"""Requirement content normalization. Plain legacy text is never interpreted as HTML."""

import re
import unicodedata
from html.parser import HTMLParser

import nh3

MAX_DESCRIPTION_LENGTH = 100_000
# Both supported databases currently store descriptions in a TEXT column.
MAX_DESCRIPTION_BYTES = 60_000
TAGS = {
    "img",
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
IMAGE_REFERENCE = re.compile(r'<img data-file-id="([1-9][0-9]{0,17}|local-[a-f0-9-]{36})">')
CLEANER = nh3.Cleaner(
    tags=TAGS,
    clean_content_tags={"script", "style", "iframe", "object", "template", "svg", "math"},
    attributes={"img": {"data-file-id"}, "a": {"href", "title"}, "ol": {"start"}},
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


def sanitize_editor_content(
    value: str, format: str, *, label: str, min_chars: int = 2, max_chars: int | None = None
) -> str:
    if format not in {"PLAIN", "HTML"}:
        raise ValueError(f"不支持的{label}格式")
    if "\x00" in value:
        raise ValueError(f"{label}不能包含空字符")
    if len(value) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(f"{label}不能超过 100000 个字符")
    result = value if format == "PLAIN" else CLEANER.clean(value)
    if format == "HTML":
        # Keep only our source-less file references. Never accept remote URLs or inline data.
        result = re.sub(
            r"<img[^>]*>", lambda m: m[0] if IMAGE_REFERENCE.fullmatch(m[0]) else "", result
        )
        extractor = _TextExtractor()
        extractor.feed(result)
        visible = "".join(extractor.parts)
    else:
        visible = result
    visible_characters = [
        c for c in visible if not c.isspace() and unicodedata.category(c) not in {"Cc", "Cf"}
    ]
    if len(visible_characters) < min_chars:
        raise ValueError(f"{label}至少需要 {min_chars} 个文字字符")
    if max_chars is not None and len(visible) > max_chars:
        raise ValueError(f"{label}不能超过 {max_chars} 个字符")
    if len(result.encode("utf-8")) > MAX_DESCRIPTION_BYTES:
        raise ValueError(f"{label}内容过长, 请精简文字或格式")
    return result


def sanitize_requirement_description(value: str, format: str) -> str:
    return sanitize_editor_content(value, format, label="需求描述")
