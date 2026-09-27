import { NavLink } from 'react-router-dom'
import { ShieldHalf, LayoutGrid, ScanLine, History, LogOut } from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuth } from '../../context/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { to: '/scans/new', label: 'New Scan', icon: ScanLine },
  { to: '/scans', label: 'Scan History', icon: History },
]

export function Sidebar() {
  const { logout } = useAuth()

  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 bg-base-950 border-r border-base-700 flex flex-col">
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-base-700">
        <ShieldHalf size={20} className="text-beacon-500" />
        <span className="font-display font-semibold text-ink-100 tracking-tight">CodeSentry</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-beacon-950 text-beacon-400 border border-beacon-500/20'
                  : 'text-ink-500 hover:text-ink-100 hover:bg-base-800 border border-transparent'
              )
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-base-700">
        <button
          onClick={logout}
          className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium text-ink-500 hover:text-ink-100 hover:bg-base-800 w-full transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
