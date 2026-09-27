import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bug, ShieldAlert, AlertTriangle, ScanLine, Plus } from 'lucide-react'
import { listScans } from '../api/scans'
import { toUserMessage } from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { SkeletonCard } from '../components/ui/Skeleton'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { StatCard } from '../components/dashboard/StatCard'
import { HealthScoreGauge } from '../components/dashboard/HealthScoreGauge'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { shortRepoName } from '../lib/utils'

export function Dashboard() {
  const [state, setState] = useState({ loading: true, error: null, latest: null, hasAnyScans: null })

  async function load() {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const list = await listScans()
      if (list.length === 0) {
        setState({ loading: false, error: null, latest: null, hasAnyScans: false })
        return
      }
      setState({ loading: false, error: null, latest: list[0], hasAnyScans: true })
    } catch (err) {
      setState({ loading: false, error: toUserMessage(err), latest: null, hasAnyScans: null })
    }
  }

  useEffect(() => {
    load()
  }, [])

  const issues = state.latest?.issues || []
  const totalIssues = issues.length
  const critical = issues.filter((i) => i.severity === 'critical').length
  const high = issues.filter((i) => i.severity === 'high').length

  return (
    <div>
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-xl font-display font-semibold text-ink-100">Code Health Dashboard</h1>
          <p className="text-sm text-ink-500 mt-1">
            Overview of your most recent repository scan and its findings.
          </p>
        </div>
        <Link to="/scans/new">
          <Button>
            <Plus size={16} />
            New Scan
          </Button>
        </Link>
      </div>

      {state.loading && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {!state.loading && state.error && <ErrorState message={state.error} onRetry={load} />}

      {!state.loading && !state.error && state.hasAnyScans === false && (
        <Card>
          <EmptyState
            icon={ScanLine}
            title="No code analyzed yet"
            description="Run your first repository scan to see code health insights."
            action={
              <Link to="/scans/new">
                <Button>Run your first scan</Button>
              </Link>
            }
          />
        </Card>
      )}

      {!state.loading && !state.error && state.latest && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="p-6 flex flex-col items-center justify-center lg:col-span-1">
            <span className="text-sm text-ink-500 font-medium mb-4">Latest Health Score</span>
            <HealthScoreGauge score={state.latest.score ?? 0} />
            <Link
              to={`/scans/${state.latest.id}`}
              className="text-xs text-beacon-400 hover:text-beacon-300 mt-4"
            >
              {shortRepoName(state.latest.repo_url)}
            </Link>
          </Card>

          <div className="lg:col-span-2 grid grid-cols-2 gap-4">
            <StatCard label="Total Issues" value={totalIssues} icon={Bug} accentClass="text-ink-300" />
            <StatCard
              label="Critical Issues"
              value={critical}
              icon={ShieldAlert}
              accentClass="text-severity-critical"
            />
            <StatCard
              label="High Severity"
              value={high}
              icon={AlertTriangle}
              accentClass="text-severity-high"
            />
            <Card className="p-5 flex flex-col justify-between">
              <span className="text-sm text-ink-500 font-medium">Last Scan Status</span>
              <div className="mt-3">
                <ScanStatusBadge status={state.latest.status} />
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
