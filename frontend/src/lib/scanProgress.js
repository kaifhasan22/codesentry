const STAGE_LABELS = {
  queued: 'Waiting to start',
  repository_preparation: 'Preparing repository',
  static_analysis: 'Static analysis',
  ai_review: 'AI review',
  finalization: 'Finalizing results',
  complete: 'Complete',
  failed: 'Failed',
}

export function stageLabel(stage) {
  return STAGE_LABELS[stage] || 'Scan in progress'
}

export function formatEstimatedRange(minSeconds, maxSeconds) {
  if (!Number.isFinite(minSeconds) || !Number.isFinite(maxSeconds)) return null
  const describe = (seconds) => {
    if (seconds < 60) return 'under a minute'
    const minutes = Math.ceil(seconds / 60)
    return `about ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`
  }
  const low = describe(minSeconds)
  const high = describe(maxSeconds)
  return low === high ? low : `${low} to ${high}`
}
