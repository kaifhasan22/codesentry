import test from 'node:test'
import assert from 'node:assert/strict'
import { validateSignup } from '../src/lib/signupValidation.js'
import { register, login } from '../src/api/auth.js'
import { client, toUserMessage } from '../src/api/client.js'

test('signup validates email, password bounds, blank passwords and confirmation', () => {
  assert.equal(validateSignup(' person@example.com ', 'password1', 'password1'), null)
  for (const args of [['bad', 'password1', 'password1'], ['a@b.com', 'short', 'short'], ['a@b.com', ' '.repeat(8), ' '.repeat(8)], ['a@b.com', 'x'.repeat(129), 'x'.repeat(129)], ['a@b.com', 'password1', 'different']]) assert.ok(validateSignup(...args))
})

test('signup uses JSON without storing its token, then login uses OAuth form and stores token', async () => {
  const oldStorage = globalThis.localStorage
  const oldAdapter = client.defaults.adapter
  const items = new Map()
  globalThis.localStorage = { getItem: k => items.get(k), setItem: (k,v) => items.set(k,v) }
  const requests = []
  client.defaults.adapter = async config => {
    requests.push(config)
    return { data: { access_token: 'session' }, status: 200, headers: {}, config }
  }
  try {
    await register(' person@example.com ', 'password1')
    assert.deepEqual(JSON.parse(requests[0].data), { email: 'person@example.com', password: 'password1' })
    assert.equal(items.size, 0)
    await login('person@example.com', 'password1')
    assert.equal(new URLSearchParams(requests[1].data).get('username'), 'person@example.com')
    assert.equal(items.get('codesentry_token'), 'session')
  } finally { client.defaults.adapter = oldAdapter; globalThis.localStorage = oldStorage }
})

test('registration errors never expose response details', () => {
  for (const status of [400, 409, 422, 429, 500, 503]) {
    const message = toUserMessage({ config: { url: '/api/auth/register' }, response: { status, data: { detail: 'SECRET password account@example.com' } } })
    assert.equal(typeof message, 'string')
    assert.ok(!message.includes('SECRET'))
    assert.ok(!message.includes('account@example.com'))
  }
})
