import { useMemo, useState } from 'react'
import { Search, ArrowUpDown } from 'lucide-react'
import { SeverityBadge } from './SeverityBadge'
import { EmptyState } from '../ui/EmptyState'
import { SEVERITY_ORDER, CATEGORY_LABEL } from '../../lib/utils'
import { SearchX } from 'lucide-react'

const SEVERITY_RANK = Object.fromEntries(SEVERITY_ORDER.map((s, i) => [s, i]))

export function IssueTable({ issues, onSelect, selectedId }) {
  const [severityFilter, setSeverityFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('severity')

  const categories = useMemo(
    () => Array.from(new Set(issues.map((i) => i.category))).filter(Boolean),
    [issues]
  )

  const filtered = useMemo(() => {
    let result = issues
    if (severityFilter !== 'all') result = result.filter((i) => i.severity === severityFilter)
    if (categoryFilter !== 'all') result = result.filter((i) => i.category === categoryFilter)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(
        (i) =>
          i.title?.toLowerCase().includes(q) ||
          i.message?.toLowerCase().includes(q) ||
          i.file_path?.toLowerCase().includes(q)
      )
    }
    return [...result].sort((a, b) => {
      if (sortBy === 'severity') return (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9)
      if (sortBy === 'file') return (a.file_path || '').localeCompare(b.file_path || '')
      return 0
    })
  }, [issues, severityFilter, categoryFilter, search, sortBy])

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-700" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, message, or file..."
            className="w-full bg-base-800 border border-base-600 rounded-md pl-8 pr-3 py-1.5 text-sm text-ink-100 placeholder:text-ink-700 focus:border-beacon-500 focus:ring-1 focus:ring-beacon-500 outline-none"
          />
        </div>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-base-800 border border-base-600 rounded-md px-2.5 py-1.5 text-sm text-ink-300 outline-none focus:border-beacon-500"
        >
          <option value="all">All severities</option>
          {SEVERITY_ORDER.map((s) => (
            <option key={s} value={s}>
              {s[0].toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-base-800 border border-base-600 rounded-md px-2.5 py-1.5 text-sm text-ink-300 outline-none focus:border-beacon-500"
        >
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c] || c}
            </option>
          ))}
        </select>

        <button
          onClick={() => setSortBy(sortBy === 'severity' ? 'file' : 'severity')}
          className="flex items-center gap-1.5 bg-base-800 border border-base-600 rounded-md px-2.5 py-1.5 text-sm text-ink-300 hover:text-ink-100"
        >
          <ArrowUpDown size={13} />
          {sortBy === 'severity' ? 'Severity' : 'File path'}
        </button>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={SearchX} title="No matching issues" />
      ) : (
        <div className="border border-base-600 rounded-card overflow-hidden">
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-base-800 text-ink-500 text-xs uppercase tracking-wide">
                  <th className="text-left font-medium px-4 py-2.5">Severity</th>
                  <th className="text-left font-medium px-4 py-2.5">Category</th>
                  <th className="text-left font-medium px-4 py-2.5">Title</th>
                  <th className="text-left font-medium px-4 py-2.5">Location</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((issue) => (
                  <tr
                    key={issue.id}
                    onClick={() => onSelect(issue)}
                    className={`cursor-pointer border-t border-base-700 hover:bg-base-800 transition-colors ${
                      selectedId === issue.id ? 'bg-base-800' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <SeverityBadge severity={issue.severity} />
                    </td>
                    <td className="px-4 py-3 text-ink-300">{CATEGORY_LABEL[issue.category] || issue.category}</td>
                    <td className="px-4 py-3 text-ink-100 max-w-xs truncate">{issue.title}</td>
                    <td className="px-4 py-3 text-ink-500 font-mono text-xs">
                      {issue.file_path}
                      {issue.line ? `:${issue.line}` : ''}
                    </td>
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
