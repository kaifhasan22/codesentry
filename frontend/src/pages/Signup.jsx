import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlertCircle, ShieldHalf } from 'lucide-react'
import { register } from '../api/auth'
import { toUserMessage } from '../api/client'
import { validateSignup } from '../lib/signupValidation'
import { Header } from '../components/layout/Header'
import { ParticleField } from '../components/visual/ParticleField'

export function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(event) {
    event.preventDefault()
    if (loading) return
    const invalid = validateSignup(email, password, confirmation)
    setError(invalid)
    if (invalid) return
    setLoading(true)
    try {
      await register(email, password)
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (registrationError) {
      setError(toUserMessage(registrationError))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <Header />
      <ParticleField subtle />
      <main className="auth-content">
        <section className="cs-card auth-card">
          <div className="auth-brand"><ShieldHalf size={28} /></div>
          <h1>Create an account</h1>
          <p className="cs-description">Start your CodeSentry workspace.</p>
          {error && <div className="cs-alert" role="alert"><AlertCircle size={17} /><span>{error}</span></div>}
          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="cs-field" htmlFor="signup-email">Email</label>
              <input className="cs-input" id="signup-email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" required disabled={loading} />
            </div>
            <div className="auth-field">
              <label className="cs-field" htmlFor="signup-password">Password</label>
              <input className="cs-input" id="signup-password" type="password" autoComplete="new-password" minLength={8} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} aria-describedby="password-help" required disabled={loading} />
              <p id="password-help" className="cs-description">Use 8–128 characters.</p>
            </div>
            <div className="auth-field">
              <label className="cs-field" htmlFor="signup-confirmation">Confirm password</label>
              <input className="cs-input" id="signup-confirmation" type="password" autoComplete="new-password" minLength={8} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} required disabled={loading} />
            </div>
            <button className="cs-btn auth-submit" type="submit" disabled={loading}>{loading ? 'Creating account…' : 'Create account'}</button>
          </form>
          <p className="cs-description">Already have an account? <Link to="/login">Sign in</Link></p>
        </section>
      </main>
    </div>
  )
}
