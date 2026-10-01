import { beforeEach, expect, test } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '../src/context/AuthContext'
import { Login } from '../src/pages/Login'
import { Signup } from '../src/pages/Signup'
import { ProtectedRoute } from '../src/components/layout/ProtectedRoute'
import { client } from '../src/api/client'

let requests
beforeEach(() => {
  requests = []
  client.defaults.adapter = async config => {
    requests.push(config)
    return { status: 200, data: { access_token: 'test-token' }, headers: {}, config }
  }
})
function mount(path, state) {
  return render(<MemoryRouter initialEntries={[{ pathname: path, state }]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AuthProvider><Routes>
    <Route path="/" element={<h1>Home page</h1>} />
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
    <Route path="/dashboard" element={<ProtectedRoute><h1>Dashboard</h1></ProtectedRoute>} />
  </Routes></AuthProvider></MemoryRouter>)
}
async function signup(user, confirmation = 'password123') {
  await user.type(screen.getByLabelText('Email'), 'new@example.com')
  await user.type(screen.getByLabelText('Password', { exact: true }), 'password123')
  await user.type(screen.getByLabelText('Confirm password'), confirmation)
  await user.click(screen.getByRole('button', { name: 'Create account' }))
}
test('Sign In links to the public signup route', async () => {
  mount('/login')
  await userEvent.click(screen.getByRole('link', { name: 'Create an account' }))
  expect(screen.getByRole('heading', { name: 'Create an account' })).toBeTruthy()
})
test('signup rejects mismatched passwords without an API call', async () => {
  mount('/signup')
  await signup(userEvent.setup(), 'different123')
  expect(screen.getByRole('alert').textContent).toContain('Passwords do not match')
  expect(requests).toHaveLength(0)
})
test('successful signup redirects to Sign In and does not authenticate', async () => {
  mount('/signup')
  await signup(userEvent.setup())
  expect(await screen.findByRole('status')).toHaveProperty('textContent', 'Account created. Sign in to continue.')
  expect(requests[0].url).toBe('/api/auth/register')
  expect(localStorage.getItem('codesentry_token')).toBeNull()
})
test('duplicate signup shows a safe error and remains on signup', async () => {
  client.defaults.adapter = config => Promise.reject({ config, response: { status: 409, data: { detail: 'PRIVATE SQL email@example.com' } } })
  mount('/signup')
  await signup(userEvent.setup())
  expect(screen.getByRole('alert').textContent).toContain('Try signing in')
  expect(screen.getByRole('alert').textContent).not.toContain('PRIVATE')
})
test('successful login redirects home even when return state points to login', async () => {
  mount('/login', { from: '/login' })
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'new@example.com')
  await user.type(screen.getByLabelText('Password'), 'password123')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByRole('heading', { name: 'Home page' })).toBeTruthy()
  expect(localStorage.getItem('codesentry_token')).toBe('test-token')
})
test('invalid login stays on login and displays a safe error', async () => {
  client.defaults.adapter = config => Promise.reject({ config, response: { status: 401, data: { detail: 'PRIVATE' } } })
  mount('/login')
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'new@example.com')
  await user.type(screen.getByLabelText('Password'), 'wrongpassword')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByText('Invalid email or password. Please try again.')).toBeTruthy()
  expect(localStorage.getItem('codesentry_token')).toBeNull()
})
test('existing authenticated session redirects login directly home', async () => {
  localStorage.setItem('codesentry_token', 'existing')
  mount('/login')
  expect(await screen.findByRole('heading', { name: 'Home page' })).toBeTruthy()
})
test('direct dashboard route requires authentication', async () => {
  mount('/dashboard')
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy())
})

test('actual application exposes signup directly and links back to Sign In', async () => {
  const { default: App } = await import('../src/App')
  render(<MemoryRouter initialEntries={['/signup']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></MemoryRouter>)
  expect(screen.getByRole('heading', { name: 'Create an account' })).toBeTruthy()
  await userEvent.click(screen.getByRole('link', { name: 'Sign in', exact: true }))
  expect(screen.getByRole('heading', { name: 'Sign in' })).toBeTruthy()
})

test('actual application redirects authenticated direct login to home', async () => {
  const { default: App } = await import('../src/App')
  localStorage.setItem('codesentry_token', 'existing')
  render(<MemoryRouter initialEntries={['/login']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></MemoryRouter>)
  expect(await screen.findByRole('heading', { name: 'CodeSentry' })).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'Sign in' })).toBeNull()
})
