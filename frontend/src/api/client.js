import axios from 'axios'
import { resolveApiBaseUrl } from './baseUrl.js'

const BASE_URL = resolveApiBaseUrl(import.meta.env)

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
    if (error.response?.status === 401 && !['/api/auth/login', '/api/auth/register'].includes(error.config?.url)) {
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
  if (error.config?.url === '/api/auth/register') {
    if (!error.response) return 'Unable to reach CodeSentry. Check your connection and try again.'
    if (status === 409) return 'Unable to create an account with these details. Try signing in or use different details.'
    if (status === 400 || status === 422) return 'Enter a valid email and a password of 8–128 characters.'
    if (status === 429) return 'Too many attempts. Please wait before trying again.'
    return 'Unable to create your account right now. Please try again later.'
  }
  if (!error.response) {
    return 'Unable to reach CodeSentry. Check that the backend is running.'
  }
  if (status === 401 && error.config?.url === '/api/auth/login') {
    return 'Invalid email or password. Please try again.'
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
  const detail = error.response.data?.detail
  return typeof detail === 'string' ? detail : status === 422
    ? 'Please check the submitted values and use a public GitHub repository URL.'
    : 'Something went wrong.'
}
