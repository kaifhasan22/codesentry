import { useState } from 'react'
import { Link, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { AlertCircle, ShieldHalf } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { toUserMessage } from '../api/client'
import { Header } from '../components/layout/Header'
import { ParticleField } from '../components/visual/ParticleField'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login, isAuthenticated, sessionExpired, clearSessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    if (!email.trim() || !password) {
      setError('Enter both an email and password.')
      return
    }
    setLoading(true)
    try {
      await login(email.trim(), password)
      clearSessionExpired()
      navigate('/', { replace: true })
    } catch (loginError) {
      setError(toUserMessage(loginError))
    } finally {
      setLoading(false)
    }
  }

  if (isAuthenticated) return <Navigate to="/" replace />

  return (
    <div className="auth-screen">
      <Header />
      <ParticleField subtle />
      <main className="auth-content">
        <section className="cs-card auth-card">
          <div className="auth-brand"><ShieldHalf size={28} /></div>
          <h1>Sign in</h1>
          <p className="cs-description">Access your CodeSentry workspace.</p>

          {location.state?.registered && <p role="status" className="cs-description">Account created. Sign in to continue.</p>}
          {sessionExpired && <div className="cs-alert"><AlertCircle size={17} /> <span>Your session has expired. Please sign in again.</span></div>}
          {error && <div className="cs-alert"><AlertCircle size={17} /> <span>{error}</span></div>}

          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="cs-field" htmlFor="email">Email</label>
              <input
                className="cs-input"
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div className="auth-field">
              <label className="cs-field" htmlFor="password">Password</label>
              <input
                className="cs-input"
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>
            <button className="cs-btn auth-submit" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="cs-description">New to CodeSentry? <Link to="/signup">Create an account</Link></p>
        </section>
      </main>
    </div>
  )
}
