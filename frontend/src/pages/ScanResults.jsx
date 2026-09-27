import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { getScan } from '../api/scans'
import { toUserMessage } from '../api/client'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { HealthScoreGauge } from '../components/dashboard/HealthScoreGauge'
import { SeverityChart } from '../components/charts/SeverityChart'
import { CategoryChart } from '../components/charts/CategoryChart'
import { IssueTable } from '../components/issues/IssueTable'
import { IssueDetailDrawer } from '../components/issues/IssueDetailDrawer'
import { formatDate, durationBetween, shortRepoName } from '../lib/utils'

export function ScanResults() {
  const { id } = useParams()
  const [state, setState] = useState({ loading: true, error: null, scan: null })
  const [selectedIssue, setSelectedIssue] = useState(null)

  async function load() {
    setState({ loading: true, error: null, scan: null })
    try {
      const scan = await getScan(id)
      setState({ loading: false, error: null, scan })
    } catch (err) {
      setState({ loading: false, error: toUserMessage(err), scan: null })
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (state.loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48 lg:col-span-2" />
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (state.error) {
    return <ErrorState message={state.error} onRetry={load} />
  }

  const scan = state.scan
  const issues = scan.issues || []
  const duration = durationBetween(scan.started_at, scan.finished_at)

  return (
    <div>
      <div className="mb-6">
        <p className="text-sm text-ink-500 font-mono">
          {shortRepoName(scan.repo_url) || 'Repository unknown'}
        </p>
        <div className="flex items-center gap-3 mt-1">
          <h1 className="text-xl font-display font-semibold text-ink-100">Scan #{scan.id}</h1>
          <ScanStatusBadge status={scan.status} />
        </div>
        <p className="text-xs text-ink-500 mt-1">
          {formatDate(scan.finished_at || scan.started_at)}
          {duration && ` · ${duration}`}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card className="p-6 flex flex-col items-center justify-center">
          <span className="text-sm text-ink-500 font-medium mb-4">Health Score</span>
          <HealthScoreGauge score={scan.score ?? 0} />
        </Card>

        <Card className="p-5 lg:col-span-2">
          <h3 className="text-sm font-medium text-ink-300 mb-2">Issues by Severity</h3>
          <SeverityChart issues={issues} />
        </Card>
      </div>

      {issues.length > 0 && (
        <Card className="p-5 mb-6">
          <h3 className="text-sm font-medium text-ink-300 mb-2">Issues by Category</h3>
          <CategoryChart issues={issues} />
        </Card>
      )}

      <div>
        <h3 className="text-sm font-medium text-ink-300 mb-3">Findings</h3>
        {issues.length === 0 ? (
          <Card>
            <EmptyState
              icon={CheckCircle2}
              title="No issues detected"
              description="This repository passed the configured checks."
            />
          </Card>
        ) : (
          <IssueTable issues={issues} onSelect={setSelectedIssue} selectedId={selectedIssue?.id} />
        )}
      </div>

      <IssueDetailDrawer issue={selectedIssue} onClose={() => setSelectedIssue(null)} />
    </div>
  )
}
