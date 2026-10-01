import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveApiBaseUrl } from '../src/api/baseUrl.js'

test('API base URL prefers the new variable and preserves the existing alias', () => {
  assert.equal(resolveApiBaseUrl({ PROD: true, VITE_API_BASE_URL: 'https://api.example.com', VITE_API_URL: 'https://old.example.com' }), 'https://api.example.com')
  assert.equal(resolveApiBaseUrl({ PROD: true, VITE_API_URL: 'https://old.example.com' }), 'https://old.example.com')
})

test('production has no implicit localhost API and development keeps its default', () => {
  assert.equal(resolveApiBaseUrl({ PROD: true }), '')
  assert.equal(resolveApiBaseUrl({ PROD: false }), 'http://localhost:8000')
  assert.equal(resolveApiBaseUrl(), 'http://localhost:8000')
})

test('production rejects insecure or credential-bearing API bases', () => {
  for (const base of ['http://13.203.54.122', 'https://localhost', 'https://user:password@api.example.com', 'https://api.example.com?token=secret', 'https://api.example.com#fragment']) {
    assert.throws(() => resolveApiBaseUrl({ PROD: true, VITE_API_BASE_URL: base }))
  }
  assert.equal(resolveApiBaseUrl({ PROD: true, VITE_API_BASE_URL: 'https://api.example.com/' }), 'https://api.example.com')
})
