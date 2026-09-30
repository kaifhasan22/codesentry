import { Clock, Loader2, CheckCircle2, XCircle, HelpCircle } from 'lucide-react'

const STATUS = {
  queued: { label: 'Queued', icon: Clock, className: 'cs-status-queued' },
  running: { label: 'Running', icon: Loader2, className: 'cs-status-running' },
  completed: { label: 'Completed', icon: CheckCircle2, className: 'cs-status-completed' },
  failed: { label: 'Failed', icon: XCircle, className: 'cs-status-failed' },
}

export function ScanStatusBadge({ status }) {
  const config = STATUS[status] || { label: status || 'Unknown', icon: HelpCircle, className: 'cs-status-queued' }
  const Icon = config.icon
  return <span className={'cs-status ' + config.className}><Icon size={15} className={status === 'running' ? 'animate-spin' : ''} />{config.label}</span>
}
