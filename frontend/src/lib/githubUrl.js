// Match the raw URL contract enforced by the scan API.
const GITHUB_URL = /^https:\/\/(?:www\.)?github\.com\/([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9_.-]{1,100})\/?$/

export function isSupportedGithubUrl(url) {
  if (typeof url !== 'string' || url.length > 200) return false
  const match = url.match(GITHUB_URL)
  if (!match || match[0] !== url) return false
  const [, owner, rawName] = match
  const name = rawName.endsWith('.git') ? rawName.slice(0, -4) : rawName
  return !owner.endsWith('-') && !owner.includes('--') && !['', '.', '..'].includes(name) && !name.startsWith('-')
}
