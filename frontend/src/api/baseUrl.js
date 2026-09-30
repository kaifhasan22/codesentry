export function resolveApiBaseUrl(env = {}) {
  // Retain the original variable as an alias for existing local setups.
  return env.VITE_API_BASE_URL || env.VITE_API_URL || (env.PROD ? '' : 'http://localhost:8000')
}
