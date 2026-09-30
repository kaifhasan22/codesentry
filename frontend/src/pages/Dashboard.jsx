import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Bug, Plus, ScanLine, ShieldAlert } from 'lucide-react'
import { getScan, listScans } from '../api/scans'
import { toUserMessage } from '../api/client'
import { formatDate, shortRepoName } from '../lib/utils'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'

function Metric({ label, value, icon: Icon, tone }) {
  return (
    <section className="cs-card cs-card-pad cs-stat-card">
      <div className="cs-stat-top">
        <span>{label}</span>
        <span className="cs-stat-icon" style={tone ? { color: tone } : undefined}><Icon size={17} /></span>
      </div>
      <strong className="cs-stat-value">{value}</strong>
    </section>
  )
}

export function Dashboard() {
  const [state, setState] = useState({ loading: true, error: null, latest: null })

  async function load() {
    setState((current) => ({ ...current, loading: true, error: null }))
    try {
      const scans = await listScans()
      if (!scans.length) {
        setState({ loading: false, error: null, latest: null })
        return
      }
      const latest = await getScan(scans[0].id ?? scans[0].scan_id)
      setState({ loading: false, error: null, latest })
    } catch (error) {
      setState({ loading: false, error: toUserMessage(error), latest: null })
    }
  }

  useEffect(() => { load() }, [])

  const issues = state.latest?.issues || []
  const critical = issues.filter((issue) => issue.severity === 'critical').length
  const high = issues.filter((issue) => issue.severity === 'high').length
  const score = Math.max(0, Math.min(100, Number(state.latest?.score) || 0))
  const scoreColor = score >= 80 ? '#36b987' : score >= 50 ? '#e8bd4d' : '#e53030'

  return (
    <div className="cs-page">
      <div className="cs-page-heading">
        <div>
          <p className="cs-eyebrow">Workspace overview</p>
          <h1 className="cs-title">Code Health Dashboard</h1>
          <p className="cs-description">A clear view of the latest analysis from your repositories.</p>
        </div>
        <Link className="cs-btn" to="/scans/new"><Plus size={17} /> New Scan</Link>
      </div>

      {state.loading && <div className="cs-card cs-loading">Loading your scan data…</div>}

      {!state.loading && state.error && (
        <div className="cs-error-state">
          <span>{state.error}</span>
          <button type="button" className="cs-btn cs-btn-secondary" onClick={load}>Try again</button>
        </div>
      )}

      {!state.loading && !state.error && !state.latest && (
        <section className="cs-card cs-empty">
          <span className="cs-empty-icon"><ScanLine size={22} /></span>
          <h2>No repository scans yet</h2>
          <p>Start by scanning a Python repository. Your real results and findings will appear here.</p>
          <Link className="cs-btn" to="/scans/new"><Plus size={16} /> Run your first scan</Link>
        </section>
      )}

      {!state.loading && !state.error && state.latest && (
        <>
          <div className="cs-grid-dashboard">
            <section className="cs-card cs-card-pad cs-score-card">
              <span className="cs-card-label">Latest health score</span>
              <div className="cs-score-ring" style={{ '--score': score + '%', '--score-color': scoreColor }}>
                <div className="cs-score-inner">
                  <strong className="cs-score-value">{score}</strong>
                  <span className="cs-score-scale">out of 100</span>
                </div>
              </div>
              <span className="cs-score-status">{score >= 80 ? 'Healthy' : score >= 50 ? 'Needs attention' : 'At risk'}</span>
              <Link className="cs-repo-link" to={'/scans/' + state.latest.id}>
                {shortRepoName(state.latest.repo_url)}
              </Link>
            </section>

            <div className="cs-stat-grid">
              <Metric label="Total findings" value={issues.length} icon={Bug} />
              <Metric label="Critical findings" value={critical} icon={ShieldAlert} tone="#f04a4a" />
              <Metric label="High severity" value={high} icon={AlertTriangle} tone="#f2994a" />
              <section className="cs-card cs-card-pad cs-stat-card">
                <div className="cs-stat-top"><span>Latest scan</span><ScanStatusBadge status={state.latest.status} /></div>
                <div>
                  <strong className="cs-stat-value" style={{ fontSize: 18 }}>{formatDate(state.latest.finished_at || state.latest.started_at)}</strong>
                  <Link className="cs-repo-link" to={'/scans/' + state.latest.id}>View scan details ↗</Link>
                </div>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
