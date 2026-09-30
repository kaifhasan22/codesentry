import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getScanComparison } from '../../api/scans'
import { toUserMessage } from '../../api/client'
import { SEVERITY_ORDER } from '../../lib/utils'
import { comparisonIssues, DEFAULT_FILTERS, hotspotFilters } from '../../lib/reportFilters'
import { IssueTable } from './IssueTable'

const delta = (value) => value == null ? 'Unavailable' : value > 0 ? `+${value}` : String(value)

export function ReportExplorer({ scan, onSelect, selectedId }) {
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS })
  const [comparison, setComparison] = useState(null)
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const [showAllFiles, setShowAllFiles] = useState(false)
  const [showAllIssues, setShowAllIssues] = useState(false)
  const findingsRef = useRef(null)
  useEffect(() => {
    let active = true
    setComparison(null)
    setError(null)
    getScanComparison(scan.id).then((data) => { if (active) setComparison(data) }).catch((e) => { if (active) setError(toUserMessage(e)) })
    return () => { active = false }
  }, [scan.id, attempt])

  const currentIssues = scan.issues || []
  const topIssues = (scan.top_issue_ids || []).map((id) => currentIssues.find((i) => i.id === id)).filter(Boolean)
  const visibleIssues = useMemo(() => comparisonIssues(currentIssues, comparison, filters.change), [currentIssues, comparison, filters.change])
  const hotspots = scan.hotspots || []
  const navigateFindings = (next) => {
    setFilters(next)
    findingsRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
    findingsRef.current?.focus({ preventScroll: true })
  }

  return <div className="cs-report">
    <div className="cs-report-grid">
      <section className="cs-card cs-report-summary" aria-labelledby="top-issues-title">
        <h2 id="top-issues-title">Top Issues</h2>
        <p className="cs-description">Ranked by severity, evidence, and context. Select an issue for details.</p>
        {topIssues.length === 0 && <p>No current findings to prioritize.</p>}
        <div className="cs-report-list">
        {(showAllIssues ? topIssues : topIssues.slice(0, 3)).map((issue) => <button key={issue.id} className="cs-report-item" type="button" onClick={() => onSelect(issue)}>
          <span><strong>{issue.priority?.toUpperCase()}</strong> · {issue.title}</span>
          <small className="cs-mono">{issue.file_path}:{issue.line || '—'} · {issue.severity}</small>
        </button>)}
        </div>
        {topIssues.length > 3 && <button type="button" className="cs-sort" aria-expanded={showAllIssues} onClick={() => setShowAllIssues(!showAllIssues)}>{showAllIssues ? 'Show less' : `Show all ${topIssues.length} issues`}</button>}
      </section>
      <section className="cs-card cs-report-summary" aria-labelledby="hotspots-title">
        <h2 id="hotspots-title">File hotspots</h2>
        <p className="cs-description">Files with the most significant findings. Selecting a file clears other filters.</p>
        {hotspots.length === 0 && <p>No file hotspots in this scan.</p>}
        <div className="cs-report-list">
        {(showAllFiles ? hotspots : hotspots.slice(0, 3)).map((hotspot) => <button key={hotspot.file_path} className="cs-report-item" type="button" onClick={() => navigateFindings(hotspotFilters(hotspot.file_path))}>
          <span className="cs-mono">{hotspot.file_path}</span>
          <small>{hotspot.finding_count} findings · {SEVERITY_ORDER.filter((s) => hotspot.severity_counts[s] > 0).map((s) => `${hotspot.severity_counts[s]} ${s}`).join(' · ')}</small>
        </button>)}
        </div>
        {hotspots.length > 3 && <button type="button" className="cs-sort" aria-expanded={showAllFiles} onClick={() => setShowAllFiles(!showAllFiles)}>{showAllFiles ? 'Show less' : `Show all ${hotspots.length} files`}</button>}
      </section>
    </div>

    <section className="cs-card cs-card-pad cs-report-comparison" aria-labelledby="comparison-title">
      <h2 id="comparison-title">Scan comparison</h2>
      {error ? <div role="alert">{error} <button className="cs-sort" onClick={() => setAttempt(attempt + 1)}>Retry comparison</button></div>
        : !comparison ? <p role="status">Loading previous scan…</p>
          : !comparison.available ? <p>{comparison.reason}</p>
            : <>
              <p>Compared with <Link className="cs-repo-link" to={`/scans/${comparison.baseline_scan_id}`}>scan #{comparison.baseline_scan_id}</Link>, the previous completed scan of this repository.</p>
              {comparison.current_commit && comparison.baseline_commit && <p className="cs-mono">{comparison.current_commit === comparison.baseline_commit ? `Same commit: ${comparison.current_commit.slice(0, 12)}` : `${comparison.baseline_commit.slice(0, 12)} → ${comparison.current_commit.slice(0, 12)}`}</p>}
              <div className="cs-report-deltas">
                <span>Health score change: <strong>{delta(comparison.score_delta)}</strong> <small>(positive means improved)</small></span>
                <span>Total finding change: <strong>{delta(comparison.total_delta)}</strong></span>
              </div>
              <p className="cs-description">{SEVERITY_ORDER.map((s) => `${s}: ${delta(comparison.severity_delta[s])}`).join(' · ')}</p>
              <div className="cs-toolbar">
                {['new', 'resolved', 'unchanged'].map((change) => <button key={change} type="button" className="cs-sort" onClick={() => navigateFindings({ ...DEFAULT_FILTERS, change })}>{comparison[`${change}_count`]} {change}</button>)}
              </div>
              <p className="cs-description">Unchanged means the finding identity matched; severity and other details may still have changed. Resolved means no longer detected, not necessarily fixed.</p>
              {comparison.warnings.map((warning) => <p key={warning} className="cs-description">{warning}</p>)}
            </>}
    </section>

    <section ref={findingsRef} className="cs-findings" tabIndex={-1} aria-labelledby="findings-title">
      <div className="cs-findings-heading"><h2 id="findings-title">{filters.change === 'resolved' ? 'Resolved findings' : 'Findings'}</h2><span>{currentIssues.length} current total</span></div>
      {filters.change === 'resolved' && <p className="cs-description">Showing findings from scan #{comparison?.baseline_scan_id} that were not detected in this scan. Details belong to that earlier scan.</p>}
      <IssueTable issues={visibleIssues} onSelect={onSelect} selectedId={selectedId} filters={filters} onFiltersChange={setFilters} comparisonAvailable={Boolean(comparison?.available)} />
    </section>
  </div>
}
