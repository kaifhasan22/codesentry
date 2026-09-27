export function cn(...args) {
  return args.filter(Boolean).join(' ')
}

export function formatDate(isoString) {
  if (!isoString) return '—'
  const d = new Date(isoString)
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function durationBetween(startIso, endIso) {
  if (!startIso || !endIso) return null
  const ms = new Date(endIso) - new Date(startIso)
  if (ms < 0) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function shortRepoName(url) {
  if (!url) return ''
  const cleaned = url.replace(/\.git$/, '').replace(/\/$/, '')
  const parts = cleaned.split('/')
  return parts.slice(-2).join('/')
}

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info']

export const SEVERITY_LABEL = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export const CATEGORY_LABEL = {
  security: 'Security',
  complexity: 'Complexity',
  maintainability: 'Maintainability',
  style: 'Style',
  dead_code: 'Dead Code',
}
