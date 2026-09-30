export const DEFAULT_FILTERS = Object.freeze({ search: '', severity: 'all', category: 'all', priority: 'all', file: 'all', change: 'all' })

export function filterIssues(issues, filters = DEFAULT_FILTERS) {
  const query = filters.search.trim().toLowerCase()
  return issues.filter((issue) =>
    (filters.severity === 'all' || issue.severity === filters.severity) &&
    (filters.category === 'all' || issue.category === filters.category) &&
    (filters.priority === 'all' || issue.priority === filters.priority) &&
    (filters.file === 'all' || issue.file_path === filters.file) &&
    (filters.change === 'all' || issue.comparison_state === filters.change) &&
    (!query || [issue.title, issue.message, issue.file_path].some((value) => value?.toLowerCase().includes(query)))
  )
}

export function hotspotFilters(file) {
  return { ...DEFAULT_FILTERS, file }
}

export function comparisonIssues(issues, comparison, change) {
  if (!comparison?.available) return issues
  if (change === 'resolved') return comparison.resolved_issues.map((i) => ({ ...i, comparison_state: 'resolved', source_scan_id: comparison.baseline_scan_id }))
  const newIds = new Set(comparison.new_issue_ids)
  return issues.map((i) => ({ ...i, comparison_state: newIds.has(i.id) ? 'new' : 'unchanged' }))
}
