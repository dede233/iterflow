import DOMPurify from 'dompurify'

export type DescriptionFormat = 'PLAIN' | 'HTML'
const tags = ['p', 'br', 'h2', 'h3', 'strong', 'b', 'em', 'i', 's', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'a']

export function safeRichTextLink(value: string): boolean {
  if (!/^(https?:\/\/|mailto:)/i.test(value) || /[\u0000-\u0020\u007f]/.test(value)) return false
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? !!url.hostname : url.protocol === 'mailto:' && !!url.pathname
  } catch { return false }
}

/** A fresh fragment avoids global DOMPurify hooks shared with other features. */
export function sanitizeRichText(value: string): string {
  const fragment = DOMPurify.sanitize(value, {
    ALLOWED_TAGS: tags,
    ALLOWED_ATTR: ['href', 'title', 'start'],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
    RETURN_DOM_FRAGMENT: true,
  })
  for (const link of fragment.querySelectorAll('a')) {
    if (!safeRichTextLink(link.getAttribute('href') || '')) link.removeAttribute('href')
    else {
      link.setAttribute('target', '_blank')
      link.setAttribute('rel', 'noopener noreferrer nofollow')
    }
  }
  const container = document.createElement('div')
  container.append(fragment)
  return container.innerHTML
}

export function plainTextToHtml(value: string): string {
  const escaped = value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  return `<p>${escaped.replace(/\r\n?|\n/g, '<br>')}</p>`
}

export function richTextPlainText(value: string): string {
  const visibleText = (text: string) => text.replace(/[\p{Cc}\p{Cf}]/gu, character => /[\n\r\t]/.test(character) ? character : '')
  const container = document.createElement('div')
  // Remove raw controls before HTML parsing can turn NUL into a visible replacement character.
  // This affects validation/summary text only; stored HTML/PLAIN content is unchanged.
  container.innerHTML = sanitizeRichText(visibleText(value)).replace(/<br\s*\/?\s*>|<\/(?:p|h2|h3|li|blockquote|pre)>/g, '\n')
  return visibleText(container.textContent || '').trim()
}
