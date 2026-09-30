import test from 'node:test'
import assert from 'node:assert/strict'
import { client, setUnauthorizedHandler, toUserMessage } from '../src/api/client.js'

test('incorrect login does not expire an authenticated session; protected 401 does', async () => {
  const previous = globalThis.localStorage
  const items = new Map([['codesentry_token', 'test-session-token']])
  globalThis.localStorage = { getItem: key => items.get(key), removeItem: key => items.delete(key) }
  let expirations = 0
  setUnauthorizedHandler(() => { expirations += 1 })
  const adapter = config => Promise.reject({ config, response: { status: 401, data: { detail: 'Invalid email or password' } } })
  try {
    await assert.rejects(client.post('/api/auth/login', {}, { adapter }), error => {
      assert.equal(toUserMessage(error), 'Invalid email or password. Please try again.')
      return true
    })
    assert.equal(expirations, 0)
    assert.equal(items.get('codesentry_token'), 'test-session-token')
    await assert.rejects(client.get('/api/scans', { adapter }), error => {
      assert.equal(toUserMessage(error), 'Your session has expired. Please sign in again.')
      return true
    })
    assert.equal(expirations, 1)
    assert.equal(items.has('codesentry_token'), false)
  } finally {
    setUnauthorizedHandler(null)
    globalThis.localStorage = previous
  }
})

test('structured validation and internal errors become safe display strings', () => {
  assert.equal(typeof toUserMessage({ response: { status: 422, data: { detail: [{ msg: 'bad input' }] } } }), 'string')
  assert.equal(toUserMessage({ response: { status: 500, data: { detail: '/internal/secret' } } }), 'Something went wrong while communicating with CodeSentry.')
})
