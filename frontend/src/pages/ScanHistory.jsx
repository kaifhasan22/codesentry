import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { History, Plus, ScanLine } from 'lucide-react'
import { listScans } from '../api/scans'
import { toUserMessage } from '../api/client'
import { formatDate, shortRepoName } from '../lib/utils'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { formatEstimatedRange, stageLabel } from '../lib/scanProgress'

export function ScanHistory() {
  const [state, setState] = useState({ loading: true, error: null, scans: [] })

  async function load({ quiet = false } = {}) {
    setState((current) => ({ ...current, loading: quiet ? current.loading : true, error: null }))
    try {
      const scans = await listScans()
      setState({ loading: false, error: null, scans })
    } catch (error) {
      setState({ loading: false, error: toUserMessage(error), scans: [] })
    }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!state.scans.some((scan) => ['queued', 'running'].includes(scan.status))) return undefined
    const timer = setInterval(() => load({ quiet: true }), 5000)
    return () => clearInterval(timer)
  }, [state.scans])

  return (
    <div className="cs-page">
      <div className="cs-page-heading">
        <div>
          <p className="cs-eyebrow">Your workspace</p>
          <h1 className="cs-title">Scan History</h1>
          <p className="cs-description">Every repository analysis run through CodeSentry.</p>
        </div>
        <Link className="cs-btn" to="/scans/new"><Plus size={17} /> New Scan</Link>
      </div>

      {state.error && <div className="cs-error-state"><span>{state.error}</span><button className="cs-btn cs-btn-secondary" onClick={load}>Try again</button></div>}
      {!state.error && state.loading && <section className="cs-card cs-loading">Loading scan history…</section>}
      {!state.error && !state.loading && state.scans.length === 0 && (
        <section className="cs-card cs-empty">
          <span className="cs-empty-icon"><History size={22} /></span>
          <h2>No scans in your history</h2>
          <p>Run your first repository scan and it will appear here with its status, score, and findings.</p>
          <Link className="cs-btn" to="/scans/new"><Plus size={16} /> Start a scan</Link>
        </section>
      )}
      {!state.error && !state.loading && state.scans.length > 0 && (
        <section className="cs-card cs-history-wrap">
          <div className="cs-table-scroll">
            <table className="cs-table">
              <thead>
                <tr><th>Repository</th><th>Scan ID</th><th>Date</th><th>Status</th><th>Score</th><th>Findings</th></tr>
              </thead>
              <tbody>
                {state.scans.map((scan) => {
                  const scanId = scan.id ?? scan.scan_id
                  return (
                    <tr key={scanId}>
                      <td><Link to={'/scans/' + scanId}>{shortRepoName(scan.repo_url) || 'Repository'}</Link></td>
                      <td className="muted">#{scanId}</td>
                      <td className="muted">{formatDate(scan.finished_at || scan.started_at || scan.created_at)}</td>
                      <td>
                        <ScanStatusBadge status={scan.status} />
                        {['queued', 'running'].includes(scan.status) && <div className="cs-history-stage">
                          {stageLabel(scan.stage)}
                          {formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)
                            ? ` · ~${formatEstimatedRange(scan.estimated_min_seconds, scan.estimated_max_seconds)}`
                            : ''}
                        </div>}
                      </td>
                      <td>{scan.score ?? '—'}</td>
                      <td>{scan.issue_count ?? scan.issues?.length ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {!state.loading && !state.error && state.scans.length > 0 && (
        <p className="cs-help" style={{ marginTop: 13 }}><ScanLine size={13} style={{ verticalAlign: '-2px', marginRight: 5 }} />Showing scans returned by your backend account.</p>
      )}
    </div>
  )
}
