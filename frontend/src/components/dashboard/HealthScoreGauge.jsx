function scoreColor(score) {
  if (score >= 80) return '#36b987'
  if (score >= 50) return '#e8bd4d'
  return '#e53030'
}

function scoreLabel(score) {
  if (score >= 80) return 'Healthy'
  if (score >= 50) return 'Needs attention'
  return 'At risk'
}

export function HealthScoreGauge({ score = 0, size = 160 }) {
  const value = Math.max(0, Math.min(100, Number(score) || 0))
  const color = scoreColor(value)
  return (
    <div style={{ display: 'grid', width: size, height: size, placeItems: 'center', borderRadius: '50%', background: 'conic-gradient(' + color + ' ' + value + '%, rgb(var(--base-700)) 0)' }}>
      <div style={{ display: 'flex', width: size - 24, height: size - 24, flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: 'rgb(var(--base-900))' }}>
        <strong style={{ color: 'rgb(var(--ink-100))', fontSize: 36, lineHeight: 1 }}>{Math.round(value)}</strong>
        <span style={{ marginTop: 7, color: 'rgb(var(--ink-500))', fontSize: 11 }}>/ 100</span>
        <span style={{ marginTop: 9, color, fontSize: 11, fontWeight: 700 }}>{scoreLabel(value)}</span>
      </div>
    </div>
  )
}
