import katex from 'katex'
import 'katex/dist/katex.min.css'

function escapeHtml(text) {
  if (!text) return ''
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function normalizeLatexSlashes(text) {
  return String(text || '').replace(/\\\\(?=[a-zA-Z])/g, '\\')
}

export function latexToPlainText(text) {
  if (!text) return ''
  let output = normalizeLatexSlashes(text)
  output = output.replace(/\\(?:dfrac|frac)\{([^{}]+)\}\{([^{}]+)\}/g, '$1/$2')
  output = output.replace(/\\sqrt\{([^{}]+)\}/g, '√($1)')
  output = output.replace(/\\left|\\right/g, '')
  output = output.replace(/\\times/g, '×')
  output = output.replace(/\\div/g, '÷')
  output = output.replace(/\\cdot/g, '·')
  output = output.replace(/\\leq?/g, '≤')
  output = output.replace(/\\geq?/g, '≥')
  output = output.replace(/\\neq/g, '≠')
  output = output.replace(/\\pi/g, 'π')
  output = output.replace(/\\%/g, '%')
  output = output.replace(/\\[()]/g, '')
  output = output.replace(/\$/g, '')
  output = output.replace(/\{([^{}]+)\}/g, '$1')
  return output
}

function renderLatex(raw) {
  try {
    return katex.renderToString(raw.replace(/^\\dfrac/, '\\frac'), {
      displayMode: false,
      throwOnError: false,
    })
  } catch {
    return escapeHtml(latexToPlainText(raw))
  }
}

function renderBareLatexInEscapedText(text) {
  return text.replace(/\\(?:dfrac|frac)\{([^{}]+)\}\{([^{}]+)\}/g, raw => renderLatex(raw))
}

export function renderMath(text) {
  if (!text) return ''
  text = normalizeLatexSlashes(text)
  const parts = []
  let lastIdx = 0
  const regex = /\\\((.*?)\\\)|\$(.*?)\$/g
  let match
  while ((match = regex.exec(text)) !== null) {
    parts.push(renderBareLatexInEscapedText(escapeHtml(text.slice(lastIdx, match.index))))
    const mathContent = (match[1] || match[2]).trim()
    parts.push(renderLatex(mathContent))
    lastIdx = match.index + match[0].length
  }
  parts.push(renderBareLatexInEscapedText(escapeHtml(text.slice(lastIdx))))
  return parts.join('')
}
