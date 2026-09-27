import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { History, Plus } from 'lucide-react'
import { listScans } from '../api/scans'
import { toUserMessage } from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { SkeletonRow } from '../components/ui/Skeleton'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'
import { formatDate, shortRepoName } from '../lib/utils'

export function ScanHistory() {
  const [state, setState] = useState({ loading: true, error: null, scans: [] })

  async function load() {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const list = await listScans()
      setState({ loading: false, error: null, scans: list })
    } catch (err) {
      setState({ loading: false, error: toUserMessage(err), scans: [] })
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div>
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-xl font-display font-semibold text-ink-100">Scan History</h1>
          <p className="text-sm text-ink-500 mt-1">All repository scans run through CodeSentry.</p>
        </div>
        <Link to="/scans/new">
          <Button>
            <Plus size={16} />
            New Scan
          </Button>
        </Link>
      </div>

      {state.error && <ErrorState message={state.error} onRetry={load} />}

      {!state.error && (
        <Card className="overflow-hidden">
          {state.loading ? (
            <div>
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </div>
          ) : state.scans.length === 0 ? (
            <EmptyState
              icon={History}
              title="No code analyzed yet"
              description="Run your first repository scan to see code health insights."
              action={
                <Link to="/scans/new">
                  <Button>Run your first scan</Button>
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-base-800 text-ink-500 text-xs uppercase tracking-wide">
                    <th className="text-left font-medium px-4 py-2.5">Repository</th>
                    <th className="text-left font-medium px-4 py-2.5">Scan ID</th>
                    <th className="text-left font-medium px-4 py-2.5">Date</th>
                    <th className="text-left font-medium px-4 py-2.5">Status</th>
                    <th className="text-left font-medium px-4 py-2.5">Score</th>
                    <th className="text-left font-medium px-4 py-2.5">Issues</th>
                  </tr>
                </thead>
                <tbody>
                  {state.scans.map((scan) => {
                    const scanId = scan.id ?? scan.scan_id
                    return (
                      <tr
                        key={scanId}
                        className="border-t border-base-700 hover:bg-base-800 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-3">
                          <Link to={`/scans/${scanId}`} className="text-ink-100 font-mono text-xs hover:text-beacon-400">
                            {shortRepoName(scan.repo_url) || '—'}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-ink-500 font-mono text-xs">#{scanId}</td>
                        <td className="px-4 py-3 text-ink-500 text-xs">{formatDate(scan.started_at)}</td>
                        <td className="px-4 py-3">
                          <ScanStatusBadge status={scan.status} />
                        </td>
                        <td className="px-4 py-3 text-ink-300">{scan.score ?? '—'}</td>
                        <td className="px-4 py-3 text-ink-300">{scan.issues?.length ?? '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
