import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

const VARIANTS = {
  primary: 'bg-beacon-500 text-base-950 hover:bg-beacon-400 disabled:bg-beacon-500/40',
  secondary: 'bg-base-700 text-ink-100 hover:bg-base-600 border border-base-600',
  ghost: 'text-ink-300 hover:text-ink-100 hover:bg-base-800',
  danger: 'bg-severity-critical/15 text-severity-critical hover:bg-severity-critical/25 border border-severity-critical/30',
}

const SIZES = {
  sm: 'text-sm px-3 py-1.5 gap-1.5',
  md: 'text-sm px-4 py-2 gap-2',
  lg: 'text-base px-5 py-2.5 gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className,
  children,
  ...props
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-60',
        VARIANTS[variant],
        SIZES[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="animate-spin" size={16} />}
      {children}
    </button>
  )
}
