import { cn } from '../../lib/utils'

export function Card({ className, children, ...props }) {
  return (
    <div
      className={cn(
        'bg-base-850 border border-base-600 rounded-card',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
