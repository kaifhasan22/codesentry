import { cn } from '../../lib/utils'

function scoreColor(score) {
  if (score >= 80) return '#3FBF7F' // healthy
  if (score >= 50) return '#E8A33D' // beacon amber - needs attention
  return '#E5484D' // critical
}

function scoreLabel(score) {
  if (score >= 80) return 'Healthy'
  if (score >= 50) return 'Needs attention'
  return 'At risk'
}

export function HealthScoreGauge({ score = 0, size = 140, strokeWidth = 10, className }) {
  const clamped = Math.max(0, Math.min(100, score))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - clamped / 100)
  const color = scoreColor(clamped)

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#262E42"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="flex flex-col items-center" style={{ marginTop: -(size / 2 + 20) }}>
        <span className="font-display font-semibold text-3xl text-ink-100">{Math.round(clamped)}</span>
        <span className="text-xs text-ink-500">/ 100</span>
      </div>
      <span className="text-xs font-medium mt-2" style={{ color }}>
        {scoreLabel(clamped)}
      </span>
    </div>
  )
}
