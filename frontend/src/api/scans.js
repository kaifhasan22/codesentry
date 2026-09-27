import { client } from './client'

// -----------------------------------------------------------------------
// GENUINE BACKEND GAPS (confirmed against /openapi.json):
//
// 1. There is no GET /api/scans list/history endpoint - only
//    POST /api/scans and GET /api/scans/{scan_id} exist.
// 2. ScanResponse (the GET /api/scans/{id} shape) does not include
//    repo_url - only ScanCreateRequest (the POST body) has it.
//
// Rather than invent a backend endpoint or fake scan data, this records
// the scan IDs + repo URLs *this browser* actually submitted (real data
// it already has) in localStorage, and hydrates each one with the real
// GET /api/scans/{id} response. Nothing about a scan's status, score or
// issues is fabricated - only the repo_url/created_at bookkeeping the
// backend doesn't hand back is kept client-side.
//
// Limitation this implies: "history" only shows scans created through
// this browser, not every scan the backend has ever run. If the backend
// adds a real GET /api/scans endpoint, swap listScans() below to call
// it directly and this workaround can be deleted.
// -----------------------------------------------------------------------

const REGISTRY_KEY = 'codesentry_scan_registry'

function readRegistry() {
  try {
    const raw = localStorage.getItem(REGISTRY_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function writeRegistry(entries) {
  localStorage.setItem(REGISTRY_KEY, JSON.stringify(entries))
}

function recordScanCreated(scanId, repoUrl) {
  const entries = readRegistry()
  entries.unshift({ scan_id: scanId, repo_url: repoUrl, created_at: new Date().toISOString() })
  writeRegistry(entries)
}

export function getRegisteredRepoUrl(scanId) {
  const entry = readRegistry().find((e) => String(e.scan_id) === String(scanId))
  return entry?.repo_url ?? null
}

export async function createScan(repoUrl) {
  const { data } = await client.post('/api/scans', { repo_url: repoUrl })
  recordScanCreated(data.scan_id, repoUrl)
  return data
}

export async function getScan(scanId) {
  const { data } = await client.get(`/api/scans/${scanId}`)
  return data // { id, status, score, error_message, started_at, finished_at, issues[] }
}

// Newest-first history of scans created from this browser, each hydrated
// with its real current state from the backend.
export async function listScans() {
  const registry = readRegistry()
  const hydrated = await Promise.all(
    registry.map(async (entry) => {
      try {
        const detail = await getScan(entry.scan_id)
        return { ...detail, repo_url: entry.repo_url }
      } catch {
        return null // scan no longer exists on the backend; drop it
      }
    })
  )
  return hydrated.filter(Boolean)
}
