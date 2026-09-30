import { Link, NavLink, useLocation } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '../../lib/utils'
import { useAuth } from '../../context/AuthContext'

const links = [
  { to: '/dashboard', label: 'Dashboard', end: true },
  { to: '/scans/new', label: 'New Scan' },
  { to: '/scans', label: 'Scan History' },
]

function initialTheme() {
  try {
    return localStorage.getItem('codesentry-ui-theme') || 'dark'
  } catch {
    return 'dark'
  }
}

export function Header() {
  const { isAuthenticated, logout } = useAuth()
  const location = useLocation()
  const [theme, setTheme] = useState(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    try {
      localStorage.setItem('codesentry-ui-theme', theme)
    } catch {
      // Theme still works for the current page when storage is unavailable.
    }
  }, [theme])

  return (
    <header className="site-header">
      <Link className="wordmark" to="/" aria-label="CodeSentry home">
        Code<span>Sentry</span>
      </Link>

      <nav className="app-nav" aria-label="Application pages">
        {links.map(({ to, label }, index) => (
          <span className="nav-group" key={to}>
            {index > 0 && <span className="nav-separator" aria-hidden="true">⋮</span>}
            <NavLink
              to={to}
              end
              className={({ isActive }) => {
                const isHistoryRoute = to === '/scans' && location.pathname.startsWith('/scans/') && location.pathname !== '/scans/new'
                return cn('nav-link', (isActive || isHistoryRoute) && 'nav-link-active')
              }}
            >
              {label}
            </NavLink>
          </span>
        ))}
      </nav>

      <div className="header-actions">
        {isAuthenticated ? (
          <button className="text-action" onClick={logout}>Sign out ↗</button>
        ) : (
          <Link className="text-action" to="/login" state={{ from: location.pathname }}>
            Sign in ↗
          </Link>
        )}
        <button
          className="theme-toggle"
          type="button"
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-pressed={theme === 'light'}
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  )
}
