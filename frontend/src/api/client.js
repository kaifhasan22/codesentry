import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

const TOKEN_KEY = 'codesentry_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Session-expiry hook the AuthContext subscribes to, so a 401 anywhere
// in the app can trigger a redirect to /login without every call site
// needing its own error handling for this case.
let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken()
      onUnauthorized?.()
    }
    return Promise.reject(error)
  }
)

// Turns an Axios error into a message safe to show a user (never a raw
// backend stack trace), per the app's error-state requirements.
export function toUserMessage(error) {
  const status = error.response?.status
  if (!error.response) {
    return 'Unable to reach CodeSentry. Check that the backend is running.'
  }
  if (status === 401) {
    return 'Your session has expired. Please sign in again.'
  }
  if (status === 400) {
    return error.response.data?.detail || 'Please check the repository URL.'
  }
  if (status === 404) {
    return 'That resource could not be found.'
  }
  if (status === 503) {
    return error.response.data?.detail || 'CodeSentry is temporarily unavailable. Please try again.'
  }
  if (status >= 500) {
    return 'Something went wrong while communicating with CodeSentry.'
  }
  return error.response.data?.detail || 'Something went wrong.'
}
