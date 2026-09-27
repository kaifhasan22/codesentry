import { Clock, Loader2, CheckCircle2, XCircle, HelpCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

const CONFIG = {
  queued: { label: 'Queued', icon: Clock, color: 'text-ink-500', spin: false },
  running: { label: 'Running', icon: Loader2, color: 'text-beacon-400', spin: true },
  completed: { label: 'Completed', icon: CheckCircle2, color: 'text-emerald-400', spin: false },
  failed: { label: 'Failed', icon: XCircle, color: 'text-severity-critical', spin: false },
}

export function ScanStatusBadge({ status, className }) {
  const conf = CONFIG[status] || { label: status || 'Unknown', icon: HelpCircle, color: 'text-ink-500' }
  const Icon = conf.icon
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-sm font-medium', conf.color, className)}>
      <Icon size={14} className={conf.spin ? 'animate-spin' : ''} />
      {conf.label}
    </span>
  )
}
