import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ShieldHalf, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { toUserMessage } from '../api/client'
import { Button } from '../components/ui/Button'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login, sessionExpired, clearSessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    if (!email.trim() || !password) {
      setError('Enter both an email and password.')
      return
    }

    setLoading(true)
    try {
      await login(email.trim(), password)
      clearSessionExpired()
      navigate(location.state?.from || '/dashboard', { replace: true })
    } catch (err) {
      setError(toUserMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-950 px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 justify-center mb-8">
          <ShieldHalf size={24} className="text-beacon-500" />
          <span className="font-display font-semibold text-xl text-ink-100 tracking-tight">
            CodeSentry
          </span>
        </div>

        <div className="bg-base-850 border border-base-600 rounded-card p-6">
          <h1 className="text-lg font-display font-semibold text-ink-100 mb-1">Sign in</h1>
          <p className="text-sm text-ink-500 mb-6">Access your code health dashboard.</p>

          {sessionExpired && (
            <div className="mb-4 flex items-start gap-2 text-sm text-severity-medium bg-severity-medium/10 border border-severity-medium/20 rounded-md px-3 py-2">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              Your session has expired. Please sign in again.
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-start gap-2 text-sm text-severity-critical bg-severity-critical/10 border border-severity-critical/20 rounded-md px-3 py-2">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-ink-300 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-base-800 border border-base-600 rounded-md px-3 py-2 text-sm text-ink-100 placeholder:text-ink-700 focus:border-beacon-500 focus:ring-1 focus:ring-beacon-500 outline-none transition-colors"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-ink-300 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-base-800 border border-base-600 rounded-md px-3 py-2 text-sm text-ink-100 placeholder:text-ink-700 focus:border-beacon-500 focus:ring-1 focus:ring-beacon-500 outline-none transition-colors"
              />
            </div>

            <Button type="submit" loading={loading} className="w-full mt-2">
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
