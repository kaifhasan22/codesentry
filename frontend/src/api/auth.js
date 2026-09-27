import { client, setToken, clearToken } from './client'

// Confirmed against /openapi.json: POST /api/auth/login is an OAuth2
// password-flow endpoint (FastAPI's OAuth2PasswordRequestForm), so the
// body must be application/x-www-form-urlencoded with `username` (the
// account email) and `password` - not a JSON {email, password} body.
export async function login(email, password) {
  const body = new URLSearchParams()
  body.set('grant_type', 'password')
  body.set('username', email)
  body.set('password', password)

  const { data } = await client.post('/api/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  setToken(data.access_token)
  return data
}

export function logout() {
  clearToken()
}
