import test from 'node:test'
import assert from 'node:assert/strict'
import { comparisonIssues, DEFAULT_FILTERS, filterIssues, hotspotFilters } from '../src/lib/reportFilters.js'

const issues = [
  { id: 1, title: 'Unsafe call', message: 'Pickle input', severity: 'high', category: 'security', priority: 'p2', file_path: 'app.py' },
  { id: 2, title: 'Complex function', severity: 'high', category: 'complexity', priority: 'p3', file_path: 'app.py' },
  { id: 3, title: 'Long signature', severity: 'low', category: 'style', priority: 'p4', file_path: 'other.py' },
]

test('search, severity, category, priority, and file compose with AND', () => {
  const filters = { ...DEFAULT_FILTERS, search: ' PICKLE ', severity: 'high', category: 'security', priority: 'p2', file: 'app.py' }
  assert.deepEqual(filterIssues(issues, filters).map((i) => i.id), [1])
  assert.deepEqual(filterIssues(issues, { ...filters, priority: 'p4' }), [])
  assert.equal(filterIssues(issues, { ...DEFAULT_FILTERS, search: 'app.PY' }).length, 2)
})

test('reset restores all results and hotspot clears other filters', () => {
  assert.equal(filterIssues(issues, { ...DEFAULT_FILTERS }).length, 3)
  assert.deepEqual(hotspotFilters('other.py'), { ...DEFAULT_FILTERS, file: 'other.py' })
  assert.deepEqual(filterIssues(issues, hotspotFilters('other.py')).map((i) => i.id), [3])
})

test('comparison uses current IDs for new/unchanged and previous details for resolved', () => {
  const comparison = { available: true, new_issue_ids: [3], resolved_issues: [{ ...issues[0], id: 99 }] }
  const current = comparisonIssues(issues, comparison, 'new')
  assert.deepEqual(filterIssues(current, { ...DEFAULT_FILTERS, change: 'new' }).map((i) => i.id), [3])
  assert.equal(filterIssues(current, { ...DEFAULT_FILTERS, change: 'unchanged' }).length, 2)
  assert.deepEqual(filterIssues(comparisonIssues(issues, comparison, 'resolved'), { ...DEFAULT_FILTERS, change: 'resolved', file: 'app.py' }).map((i) => i.id), [99])
  assert.equal(comparisonIssues(issues, null, 'all'), issues)
})
