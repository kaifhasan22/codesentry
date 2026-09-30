import { useMemo, useState } from 'react'
import { ArrowUpDown, Search, SearchX } from 'lucide-react'
import { SEVERITY_ORDER, CATEGORY_LABEL } from '../../lib/utils'
import { DEFAULT_FILTERS, filterIssues } from '../../lib/reportFilters'

const SEVERITY_RANK = Object.fromEntries(SEVERITY_ORDER.map((severity, index) => [severity, index]))

export function IssueTable({ issues, onSelect, selectedId, filters, onFiltersChange, comparisonAvailable = false }) {
  const [sortBy, setSortBy] = useState('priority')
  const update = (name, value) => onFiltersChange({ ...filters, [name]: value })
  const categories = useMemo(() => Array.from(new Set(issues.map((issue) => issue.category))).filter(Boolean), [issues])

  const filtered = useMemo(() => {
    const result = filterIssues(issues, filters)
    return [...result].sort((a, b) => {
      if (sortBy === 'priority') return (b.priority_score ?? 0) - (a.priority_score ?? 0) || (a.file_path || '').localeCompare(b.file_path || '') || (a.line || 0) - (b.line || 0)
      if (sortBy === 'severity') return (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9)
      return (a.file_path || '').localeCompare(b.file_path || '')
    })
  }, [issues, filters, sortBy])

  return (
    <div>
      <div className="cs-toolbar">
        <label style={{ position: 'relative', display: 'flex', flex: 1, minWidth: 220, alignItems: 'center' }}>
          <Search size={15} style={{ position: 'absolute', left: 12, color: 'rgb(var(--ink-500))' }} />
          <input className="cs-input" style={{ paddingLeft: 37, minHeight: 40 }} value={filters.search} onChange={(event) => update('search', event.target.value)} placeholder="Search title, message, or file…" aria-label="Search findings" />
        </label>
        <select className="cs-select" style={{ width: 'auto', minHeight: 40 }} value={filters.severity} onChange={(event) => update('severity', event.target.value)} aria-label="Filter by severity">
          <option value="all">All severities</option>
          {SEVERITY_ORDER.map((severity) => <option value={severity} key={severity}>{severity[0].toUpperCase() + severity.slice(1)}</option>)}
        </select>
        <select className="cs-select" style={{ width: 'auto', minHeight: 40 }} value={filters.category} onChange={(event) => update('category', event.target.value)} aria-label="Filter by category">
          <option value="all">All categories</option>
          {categories.map((category) => <option value={category} key={category}>{CATEGORY_LABEL[category] || category}</option>)}
        </select>
        {comparisonAvailable && <select className="cs-select" value={filters.change} onChange={(e) => update('change', e.target.value)} aria-label="Filter by comparison state">
          <option value="all">All current findings</option><option value="new">New</option><option value="unchanged">Unchanged</option><option value="resolved">Resolved (previous scan)</option>
        </select>}
        <button className="cs-sort" type="button" onClick={() => setSortBy(sortBy === 'priority' ? 'severity' : sortBy === 'severity' ? 'file' : 'priority')}><ArrowUpDown size={14} />{sortBy === 'priority' ? 'Priority' : sortBy === 'severity' ? 'Severity' : 'File path'}</button>
        <button className="cs-sort" type="button" onClick={() => onFiltersChange({ ...DEFAULT_FILTERS })}>Reset filters</button>
      </div>
      <p className="cs-description" role="status" aria-live="polite">{filtered.length} of {issues.length} findings shown{filters.file !== 'all' ? ` · ${filters.file}` : ''}</p>

      {filtered.length === 0
        ? <div className="cs-card cs-empty"><span className="cs-empty-icon"><SearchX size={20} /></span><h2>No matching findings</h2><p>Change your search or filters and try again.</p></div>
        : (
          <div className="cs-issue-table">
            <div className="cs-table-scroll">
              <table className="cs-table">
                <thead><tr><th>Priority</th><th>Severity</th><th>Category</th><th>Finding</th><th>Location</th></tr></thead>
                <tbody>
                  {filtered.map((issue) => (
                    <tr key={issue.id} onClick={() => onSelect(issue)} aria-selected={selectedId === issue.id} style={{ cursor: 'pointer' }}>
                      <td title={issue.priority_reasons?.join('; ')}>{issue.priority?.toUpperCase() || '—'}</td>
                      <td><span className={'cs-severity cs-severity-' + (issue.severity || 'info')}>{issue.severity || 'Info'}</span></td>
                      <td>{CATEGORY_LABEL[issue.category] || issue.category || '—'}</td>
                      <td className="cs-issue-title"><button type="button" className="cs-report-link" onClick={(event) => { event.stopPropagation(); onSelect(issue) }}>{issue.title || issue.message || 'Untitled finding'}</button>{issue.comparison_state && <small className="cs-mono"> · {issue.comparison_state}</small>}</td>
                      <td className="cs-mono">{issue.file_path || '—'}{issue.line ? ':' + issue.line : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
    </div>
  )
}
