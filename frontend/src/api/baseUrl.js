export function resolveApiBaseUrl(env = {}) {
  // Retain the original variable as an alias for existing local setups.
  const base = (env.VITE_API_BASE_URL || env.VITE_API_URL || (env.PROD ? '' : 'http://localhost:8000')).trim().replace(/\/+$/, '')
  if (env.PROD && base) {
    const url = new URL(base)
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
      throw new Error('Production API base must be an HTTPS URL without credentials, query, fragment, or localhost. Leave it empty only with a same-origin API proxy.')
    }
  }
  return base
}
