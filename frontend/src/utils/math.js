import katex from 'katex'
import 'katex/dist/katex.min.css'

function escapeHtml(text) {
  if (!text) return ''
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/**
 * 渲染文本中的 LaTeX 公式（$...$ 和 \(...\)）为 KaTeX 数学公式 HTML
 * 非公式部分自动 HTML 转义
 */
export function renderMath(text) {
  if (!text) return ''
  const parts = []
  let lastIdx = 0
  // Match \(...\) or $...$ (non-greedy)
  const regex = /\\\((.*?)\\\)|\$(.*?)\$/g
  let match
  while ((match = regex.exec(text)) !== null) {
    // Non-math part before match (HTML escaped)
    parts.push(escapeHtml(text.slice(lastIdx, match.index)))
    // Math part — group 1 is \(...\), group 2 is $...$
    const mathContent = (match[1] || match[2]).trim()
    try {
      parts.push(katex.renderToString(mathContent, {
        displayMode: false,
        throwOnError: false,
      }))
    } catch {
      // Fallback: show original delimiter text escaped
      parts.push(escapeHtml(match[0]))
    }
    lastIdx = match.index + match[0].length
  }
  // Remaining text after last math
  parts.push(escapeHtml(text.slice(lastIdx)))
  return parts.join('')
}
