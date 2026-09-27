import { Card } from '../ui/Card'
import { cn } from '../../lib/utils'

export function StatCard({ label, value, icon: Icon, accentClass, sub }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <span className="text-sm text-ink-500 font-medium">{label}</span>
        {Icon && (
          <span className={cn('w-7 h-7 rounded-md flex items-center justify-center bg-base-700', accentClass)}>
            <Icon size={14} />
          </span>
        )}
      </div>
      <div className="mt-3 text-2xl font-display font-semibold text-ink-100">{value}</div>
      {sub && <div className="mt-1 text-xs text-ink-500">{sub}</div>}
    </Card>
  )
}
