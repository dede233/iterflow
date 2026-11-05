import pytest

from app.services.rich_text import sanitize_requirement_description


def test_plain_text_is_preserved_without_html_interpretation():
    text = '<script>alert("old text")</script>\n需求 <b>原文</b>'
    assert sanitize_requirement_description(text, "PLAIN") == text


def test_keeps_basic_formatting_and_safe_links():
    clean = sanitize_requirement_description(
        "<h2>需求标题</h2><p><strong>重点</strong>和<em>说明</em></p>"
        '<ol start="3"><li>步骤一</li></ol><a href="https://example.test/help">帮助</a>',
        "HTML",
    )
    assert "<h2>需求标题</h2>" in clean
    assert "<strong>重点</strong>" in clean
    assert '<ol start="3"><li>步骤一</li></ol>' in clean
    assert 'href="https://example.test/help"' in clean
    assert 'rel="noopener noreferrer nofollow"' in clean
    assert 'target="_blank"' in clean
    assert sanitize_requirement_description(clean, "HTML") == clean


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "jav&#x61;script:alert(1)",
        "java&#9;script:alert(1)",
        "data:text/html;base64,AAAA",
        "vbscript:msgbox(1)",
        "/relative",
        "//evil.test",
    ],
)
def test_rejects_unsafe_or_relative_link_targets(href):
    clean = sanitize_requirement_description(f'<p>说明<a href="{href}">链接</a></p>', "HTML")
    assert "href=" not in clean


def test_strips_active_content_attributes_and_embedded_resources():
    clean = sanitize_requirement_description(
        '<p id="login" style="position:fixed" onclick="attack()">保留文字</p>'
        "<script>attack()</script><style>body{display:none}</style>"
        '<img src="https://tracker.test" onerror="attack()"><iframe src="https://evil.test">'
        'frame</iframe><svg><a href="javascript:attack()">svg</a></svg>'
        '<form action="https://evil.test"><input name="password"></form>',
        "HTML",
    )
    assert "保留文字" in clean
    for forbidden in (
        "script",
        "style",
        "onclick",
        "img",
        "iframe",
        "svg",
        "input",
        "form",
        "attack",
        "tracker",
    ):
        assert forbidden not in clean


@pytest.mark.parametrize(
    "value", ["", "  ", "<p><br></p>", "<p>&nbsp;\u200b</p>", "<script>text</script>", "<p>字</p>"]
)
def test_requires_two_visible_characters_after_sanitization(value):
    with pytest.raises(ValueError, match="2 个文字字符"):
        sanitize_requirement_description(value, "HTML")


def test_bounds_input_and_utf8_storage_size():
    with pytest.raises(ValueError, match="100000"):
        sanitize_requirement_description("a" * 100_001, "PLAIN")
    with pytest.raises(ValueError, match="内容过长"):
        sanitize_requirement_description("中" * 20_001, "PLAIN")
    assert sanitize_requirement_description("中" * 20_000, "PLAIN") == "中" * 20_000


def test_unknown_format_cannot_fall_back_to_unsafe_html():
    with pytest.raises(ValueError, match="格式"):
        sanitize_requirement_description("正常内容", "MARKDOWN")


@pytest.mark.parametrize("format", ["PLAIN", "HTML"])
@pytest.mark.parametrize(
    "value",
    [
        "\u2060\u2060",
        "\u200c\u200d",
        "\u202a\u202e",
        "\u00ad\u061c",
        " \u2060\n\u200d\t ",
        "字 \u2060 \u200c ",
        "\x01\x02",
        "\x7f\x80",
        "字\x01\x02\u2060",
    ],
)
def test_control_characters_and_whitespace_do_not_satisfy_visible_text_minimum(value, format):
    source = f"<p>{value}</p>" if format == "HTML" else value
    with pytest.raises(ValueError, match="2 个文字字符"):
        sanitize_requirement_description(source, format)


@pytest.mark.parametrize("format", ["PLAIN", "HTML"])
@pytest.mark.parametrize("value", ["\x00\x01", "有效说明\x00"])
def test_rejects_nul_before_html_cleaning_or_database_storage(value, format):
    source = f"<p>{value}</p>" if format == "HTML" else value
    with pytest.raises(ValueError, match="不能包含空字符"):
        sanitize_requirement_description(source, format)


@pytest.mark.parametrize("format", ["PLAIN", "HTML"])
def test_validation_does_not_remove_emoji_joiners_from_stored_content(format):
    value = "研发👩\u200d💻说明\u2060"
    source = f"<p>{value}</p>" if format == "HTML" else value
    assert sanitize_requirement_description(source, format) == source
