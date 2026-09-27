import { cn } from '../../lib/utils'

export function Skeleton({ className }) {
  return (
    <div
      className={cn('animate-pulse bg-base-700 rounded-md', className)}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-base-850 border border-base-600 rounded-card p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-base-700">
      <Skeleton className="h-5 w-16" />
      <Skeleton className="h-5 w-20" />
      <Skeleton className="h-5 flex-1" />
      <Skeleton className="h-5 w-24" />
    </div>
  )
}
