import { AlertTriangle } from 'lucide-react'
import { Button } from './Button'

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      <div className="mb-4 w-12 h-12 rounded-full bg-severity-critical/10 border border-severity-critical/30 flex items-center justify-center">
        <AlertTriangle size={20} className="text-severity-critical" />
      </div>
      <h3 className="text-ink-100 font-medium">Something went wrong</h3>
      <p className="text-ink-500 text-sm mt-1 max-w-sm">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
