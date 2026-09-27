import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { createScan, getScan } from '../api/scans'
import { toUserMessage } from '../api/client'
import { Card } from '../components/ui/Card'
import { ScanForm } from '../components/scans/ScanForm'
import { ScanStatusBadge } from '../components/scans/ScanStatusBadge'

const POLL_INTERVAL_MS = 2500
const TERMINAL_STATUSES = ['completed', 'failed']

export function NewScan() {
  const [submitting, setSubmitting] = useState(false)
  const [scan, setScan] = useState(null) // { scan_id/id, status }
  const [error, setError] = useState(null)
  const pollRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    return () => clearInterval(pollRef.current)
  }, [])

  async function handleSubmit(repoUrl) {
    setSubmitting(true)
    setError(null)
    setScan(null)
    try {
      const created = await createScan(repoUrl)
      setScan(created)
      startPolling(created.scan_id ?? created.id, repoUrl)
    } catch (err) {
      setError(toUserMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  function startPolling(scanId, repoUrl) {
    pollRef.current = setInterval(async () => {
      try {
        const latest = await getScan(scanId)
        setScan(latest)
        if (TERMINAL_STATUSES.includes(latest.status)) {
          clearInterval(pollRef.current)
          if (latest.status === 'completed') {
            // GET /api/scans/{id} doesn't return repo_url, so it's passed
            // along here rather than re-fetched or invented.
            navigate(`/scans/${scanId}`, { state: { repo_url: repoUrl } })
          }
        }
      } catch (err) {
        clearInterval(pollRef.current)
        setError(toUserMessage(err))
      }
    }, POLL_INTERVAL_MS)
  }

  const status = scan?.status

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-display font-semibold text-ink-100">New Scan</h1>
      <p className="text-sm text-ink-500 mt-1 mb-8">
        Paste a Python GitHub repository URL to run a full code health analysis.
      </p>

      <Card className="p-6">
        <ScanForm onSubmit={handleSubmit} loading={submitting} />
      </Card>

      {error && (
        <div className="mt-4 flex items-start gap-2 text-sm text-severity-critical bg-severity-critical/10 border border-severity-critical/20 rounded-md px-3 py-2.5">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {scan && !error && (
        <Card className="mt-4 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-ink-500">Scan #{scan.scan_id ?? scan.id}</p>
              <p className="text-xs text-ink-700 mt-0.5">
                {status === 'completed'
                  ? 'Analysis complete — redirecting to results...'
                  : 'This runs asynchronously; the page updates automatically.'}
              </p>
            </div>
            <ScanStatusBadge status={status} />
          </div>
          {status === 'failed' && scan.error_message && (
            <p className="text-sm text-severity-critical mt-3 border-t border-base-700 pt-3">
              {scan.error_message}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
