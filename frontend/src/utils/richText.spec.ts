import { expect, it } from 'vitest'
import { plainTextToHtml, richTextPlainText, safeRichTextLink, sanitizeRichText } from './richText'

it('escapes legacy markup and preserves line breaks when entering the editor', () => {
  const source = '<img src=x onerror=attack()> & "旧文字"\n下一行'
  const html = plainTextToHtml(source)
  expect(html).not.toContain('<img')
  expect(richTextPlainText(html)).toBe(source)
})
it.each(['javascript:alert(1)', 'data:text/html,test', 'java\tscript:alert(1)', '/path', '//evil.test', 'https://', 'mailto:'])('rejects unsafe or incomplete links: %s', url => {
  expect(safeRichTextLink(url)).toBe(false)
  expect(sanitizeRichText(`<p>说明<a href="${url}">链接</a></p>`)).not.toContain('href=')
})
it.each(['https://example.test/path?q=1', 'http://example.test/', 'mailto:somebody@example.test'])('retains safe links with opener protection: %s', url => {
  expect(safeRichTextLink(url)).toBe(true)
  const html = sanitizeRichText(`<a href="${url}" target="window">说明</a>`)
  expect(html).toContain('target="_blank"')
  expect(html).toContain('rel="noopener noreferrer nofollow"')
})
it('strips active HTML, embedded resources and layout attributes', () => {
  const html = sanitizeRichText('<h2>说明</h2><p id="x" style="position:fixed" onclick="attack()">文本<img src=x onerror="attack()"></p><svg onload="attack()"></svg><iframe src="https://evil.test"></iframe><script>attack()</script>')
  expect(html).toBe('<h2>说明</h2><p>文本</p>')
})
it('extracts readable paragraphs and ignores invisible empty content', () => {
  expect(richTextPlainText('<p>第一段</p><p>第二段<br>换行</p>')).toBe('第一段\n第二段\n换行')
  expect(richTextPlainText('<p>&nbsp;\u200b\ufeff<br></p>')).toBe('')
})
it.each(['\u2060\u2060', '\u200c\u200d', '\u202a\u202e', '\u00ad\u061c', ' \u2060\n\u200d\t '])('ignores all Unicode format controls in validation text: %j', value => {
  expect(richTextPlainText(`<p>${value}</p>`)).toBe('')
})
it.each(['\x00\x01', '\x01\x02', '\x7f\x80', ' \x01\n\x02\r\t '])('ignores control-only content in HTML and escaped PLAIN validation text: %j', value => {
  expect(richTextPlainText(`<p>${value}</p>`)).toBe('')
  expect(richTextPlainText(plainTextToHtml(value))).toBe('')
})
it('excludes NUL from validation text while preserving visible content and paragraph separators', () => {
  const value = '有效\x00说明'
  expect(richTextPlainText(`<p>${value}</p>`)).toBe('有效说明')
  expect(richTextPlainText(plainTextToHtml(value))).toBe('有效说明')
  expect(richTextPlainText('<p>第一段\t内容</p><p>第二段\r\n换行</p>')).toBe('第一段\t内容\n第二段\n换行')
})
it('preserves emoji joiners in stored HTML while excluding controls from validation text', () => {
  const source = '<p>研发👩\u200d💻说明\u2060</p>'
  expect(sanitizeRichText(source)).toBe(source)
  expect(plainTextToHtml('研发👩\u200d💻说明\u2060')).toBe(source)
  expect(richTextPlainText(source)).toBe('研发👩💻说明')
  expect(richTextPlainText('<p>字 \u2060 \u200c </p>')).toBe('字')
})
