import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { getScan } from '../api/scans'
import { toUserMessage } from '../api/client'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { ReportExplorer } from '../components/issues/ReportExplorer'
import { IssueDetailDrawer } from '../components/issues/IssueDetailDrawer'
import { formatDate, durationBetween, shortRepoName, SEVERITY_ORDER } from '../lib/utils'
import { formatEstimatedRange, stageLabel } from '../lib/scanProgress'

const ACTIVE_STATUSES = ['queued', 'running']
const SCAN_STAGES = [
  ['repository_preparation', 'Prepare repository'],
  ['static_analysis', 'Static analysis'],
  ['ai_review', 'AI review'],
  ['finalization', 'Finalize results'],
]

export function ScanResults() {
  const { id } = useParams()
  const [state, setState] = useState({ loading: true, error: null, scan: null })
  const [selectedIssue, setSelectedIssue] = useState(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    let active = true
    setSelectedIssue(null)
    setState({ loading: true, error: null, scan: null })
    getScan(id).then((scan) => {
      if (active) setState({ loading: false, error: null, scan })
    }).catch((error) => {
      if (active) setState({ loading: false, error: toUserMessage(error), scan: null })
    })
    return () => { active = false }
  }, [id, retry])

  useEffect(() => {
    if (!ACTIVE_STATUSES.includes(state.scan?.status)) return undefined
    let active = true
    const timer = setInterval(async () => {
      try {
        const scan = await getScan(id)
        if (active) setState({ loading: false, error: null, scan })
      } catch {
        // Keep showing the last known stage through a brief network interruption.
      }
    }, 4000)
    return () => { active = false; clearInterval(timer) }
  }, [id, state.scan?.status])

  if (state.loading) return <div className="cs-page"><div className="cs-card cs-loading">Loading scan results…</div></div>
  if (state.error) return <div className="cs-page"><div className="cs-error-state"><span>{state.error}</span><button className="cs-btn cs-btn-secondary" onClick={() => setRetry(retry + 1)}>Try again</button></div></div>

  const scan = state.scan
  const isActiveScan = ACTIVE_STATUSES.includes(scan.status)
  const isFailedScan = scan.status === 'failed'
  const currentStageIndex = SCAN_STAGES.findIndex(([stage]) => stage === scan.stage)
  const issues = scan.issues || []
  const duration = durationBetween(scan.started_at, scan.finished_at)
  const countSeverity = (severity) => issues.filter((issue) => issue.severity === severity).length
  const score = Math.max(0, Math.min(100, Number(scan.score) || 0))
  const scoreColor = score >= 80 ? '#36b987' : score >= 50 ? '#e8bd4d' : '#e53030'

  return (
    <div className="cs-page">
      <div className="cs-page-heading">
        <div>
          <Link to="/scans" className="cs-repo-link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 18 }}><ArrowLeft size={14} /> Scan history</Link>
          <p className="cs-eyebrow">{shortRepoName(scan.repo_url) || 'Repository'}</p>
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 13 }}>
            <h1 className="cs-title">Scan #{scan.id}</h1>
            <ScanStatusBadge status={scan.status} />
          </div>
          <p className="cs-description">{formatDate(scan.finished_at || scan.started_at)}{duration ? ' · ' + duration : ''}</p>
        </div>
        <Link className="cs-btn" to="/scans/new">New Scan</Link>
      </div>

      {isActiveScan && (
        <section className="cs-card cs-card-pad cs-scan-detail-progress" aria-live="polite">
          <p className="cs-eyebrow">Scan progress</p>
          <div className="cs-scan-progress">
            <div>
              <h2 className="cs-scan-progress-title">{stageLabel(scan.stage)}</h2>
              <p className="cs-scan-progress-meta">
                {scan.stage === 'queued'
                  ? 'Waiting for a worker to start this scan.'
                  : `Your repository is currently in the ${stageLabel(scan.stage).toLowerCase()} stage.`}
              </p>
              <p className="cs-scan-estimate">
                {formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)
                  ? `Approximate completion window: ${formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)}`
                  : 'A time range will appear after the repository workload is known.'}
              </p>
            </div>
          </div>
          <ol className="cs-scan-stages" aria-label="Scan progress">
            {SCAN_STAGES.map(([key, label], index) => {
              const complete = currentStageIndex >= 0 && index < currentStageIndex
              const active = index === currentStageIndex
              return <li className={`cs-scan-stage${complete ? ' is-complete' : ''}${active ? ' is-active' : ''}`} key={key} aria-current={active ? 'step' : undefined}>
                <span className="cs-scan-stage-marker">{complete ? '✓' : index + 1}</span>
                <span>{label}</span>
              </li>
            })}
          </ol>
        </section>
      )}

      {isFailedScan && (
        <div className="cs-alert cs-scan-failure" role="alert">
          {scan.error_message || 'This scan stopped before its results could be saved.'}
        </div>
      )}

      {scan.status === 'completed' && <>
      <div className="cs-result-summary">
        <section className="cs-card cs-result-stat">
          <span className="cs-card-label">Health score</span>
          <strong style={{ color: scoreColor }}>{score}<span style={{ color: 'rgb(var(--ink-500))', fontSize: 13, fontWeight: 500 }}> / 100</span></strong>
        </section>
        <section className="cs-card cs-result-stat">
          <span className="cs-card-label">Total findings</span>
          <strong>{issues.length}</strong>
        </section>
        <section className="cs-card cs-result-stat">
          <span className="cs-card-label">Critical findings</span>
          <strong style={{ color: 'var(--severity-critical)' }}>{countSeverity('critical')}</strong>
        </section>
      </div>

      <div className="cs-severity-grid">
        {SEVERITY_ORDER.map((severity) => (
          <section className="cs-card cs-card-pad" key={severity} style={{ padding: '14px 17px' }}>
            <span className="cs-card-label" style={{ textTransform: 'capitalize' }}>{severity}</span>
            <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700 }}>{countSeverity(severity)}</div>
          </section>
        ))}
      </div>

      <ReportExplorer key={scan.id} scan={scan} onSelect={setSelectedIssue} selectedId={selectedIssue?.id} />
      </>}

      <IssueDetailDrawer issue={selectedIssue} onClose={() => setSelectedIssue(null)} />
    </div>
  )
}
