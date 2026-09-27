import { cn } from '../../lib/utils'
import { SEVERITY_LABEL } from '../../lib/utils'

const DOT_COLOR = {
  critical: 'bg-severity-critical',
  high: 'bg-severity-high',
  medium: 'bg-severity-medium',
  low: 'bg-severity-low',
  info: 'bg-severity-info',
}

const TEXT_COLOR = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-ink-500',
}

export function SeverityBadge({ severity, className }) {
  const key = (severity || 'info').toLowerCase()
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full bg-base-800 border border-base-600',
        TEXT_COLOR[key] || TEXT_COLOR.info,
        className
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', DOT_COLOR[key] || DOT_COLOR.info)} />
      {SEVERITY_LABEL[key] || severity}
    </span>
  )
}
