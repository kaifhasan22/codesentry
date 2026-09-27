import { cn } from '../../lib/utils'

export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center py-16 px-6', className)}>
      {Icon && (
        <div className="mb-4 w-12 h-12 rounded-full bg-base-800 border border-base-600 flex items-center justify-center">
          <Icon size={22} className="text-ink-500" />
        </div>
      )}
      <h3 className="text-ink-100 font-medium">{title}</h3>
      {description && <p className="text-ink-500 text-sm mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
