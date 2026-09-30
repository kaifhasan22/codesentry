import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, ScanLine } from 'lucide-react'
import { createScan, getScan } from '../api/scans'
import { toUserMessage } from '../api/client'
import { ScanForm } from '../components/scans/ScanForm'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { formatEstimatedRange } from '../lib/scanProgress'

const POLL_INTERVAL_MS = 2500
const TERMINAL_STATUSES = ['completed', 'failed']
const SCAN_STAGES = [
  ['repository_preparation', 'Prepare repository'],
  ['static_analysis', 'Static analysis'],
  ['ai_review', 'AI review'],
  ['finalization', 'Finalize results'],
]

function stageDescription(stage) {
  return ({
    queued: 'Waiting for a worker to start the scan.',
    repository_preparation: 'Preparing the repository and checking its Python workload.',
    static_analysis: 'Checking complexity, security, dead code, and style.',
    ai_review: 'Applying optional AI review to prioritized findings.',
    finalization: 'Saving findings and calculating the health score.',
    complete: 'Analysis complete. Opening your findings…',
    failed: 'The analysis could not be completed.',
  })[stage] || 'Analysis is running. This page will update automatically.'
}

export function NewScan() {
  const [submitting, setSubmitting] = useState(false)
  const [scan, setScan] = useState(null)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => () => clearInterval(pollRef.current), [])

  async function handleSubmit(repoUrl) {
    setSubmitting(true)
    setError(null)
    setScan(null)
    try {
      const created = await createScan(repoUrl)
      setScan(created)
      const scanId = created.scan_id ?? created.id
      pollRef.current = setInterval(async () => {
        try {
          const latest = await getScan(scanId)
          setScan(latest)
          if (TERMINAL_STATUSES.includes(latest.status)) {
            clearInterval(pollRef.current)
            if (latest.status === 'completed') navigate('/scans/' + scanId)
          }
        } catch (pollError) {
          clearInterval(pollRef.current)
          setError(toUserMessage(pollError))
        }
      }, POLL_INTERVAL_MS)
    } catch (submitError) {
      setError(toUserMessage(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="cs-page">
      <div className="cs-page-heading">
        <div>
          <p className="cs-eyebrow">Repository analysis</p>
          <h1 className="cs-title">New Scan</h1>
          <p className="cs-description">Connect a public Python repository and review its code health.</p>
        </div>
      </div>

      <section className="cs-card cs-card-pad cs-form-card">
        <ScanForm onSubmit={handleSubmit} loading={submitting || (scan && !TERMINAL_STATUSES.includes(scan.status))} />
      </section>

      {error && <div className="cs-alert"><AlertCircle size={17} /> <span>{error}</span></div>}

      {scan && !error && (
        <section className="cs-card cs-card-pad cs-form-card" style={{ marginTop: 16 }}>
          <div className="cs-scan-progress">
            <div>
              <p className="cs-eyebrow">Scan #{scan.scan_id ?? scan.id}</p>
              <p className="cs-scan-progress-title">{scan.repo_url || 'Repository scan'}</p>
              <p className="cs-scan-progress-meta">
                {scan.status === 'failed' ? (scan.error_message || 'The analysis could not be completed.') : stageDescription(scan.stage || scan.status)}
              </p>
              {scan.status !== 'failed' && scan.status !== 'completed' && (
                <p className="cs-scan-estimate" aria-live="polite">
                  {formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)
                    ? `Approximate completion window: ${formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)}`
                    : scan.status === 'queued'
                      ? 'A time range will appear after the worker starts.'
                      : 'Estimating from the repository workload…'}
                </p>
              )}
            </div>
            <ScanStatusBadge status={scan.status} />
          </div>
          {scan.status !== 'failed' && (
            <ol className="cs-scan-stages" aria-label="Scan progress">
              {SCAN_STAGES.map(([key, label], index) => {
                const currentIndex = SCAN_STAGES.findIndex(([stage]) => stage === scan.stage)
                const complete = scan.status === 'completed' || (currentIndex >= 0 && index < currentIndex)
                const active = scan.status !== 'completed' && index === currentIndex
                return <li className={`cs-scan-stage${complete ? ' is-complete' : ''}${active ? ' is-active' : ''}`} key={key} aria-current={active ? 'step' : undefined}>
                  <span className="cs-scan-stage-marker">{complete ? '✓' : index + 1}</span>
                  <span>{label}</span>
                </li>
              })}
            </ol>
          )}
          {scan.status === 'failed' && <div className="cs-alert"><AlertCircle size={17} /> {scan.error_message || 'The scan failed.'}</div>}
        </section>
      )}

      <p className="cs-help" style={{ marginTop: 18 }}><ScanLine size={14} style={{ verticalAlign: '-2px', marginRight: 6 }} />Scan results are fetched from your CodeSentry backend.</p>
    </div>
  )
}
