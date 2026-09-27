import { client } from './client'

export async function createScan(repoUrl) {
  const { data } = await client.post('/api/scans', {
    repo_url: repoUrl,
  })

  return data
}

export async function getScan(scanId) {
  const { data } = await client.get(`/api/scans/${scanId}`)
  return data
}

export async function listScans() {
  const page = await listScansPage()
  return Array.isArray(page) ? page : page.items
}

export async function listScansPage(params = {}) {
  const { data } = await client.get('/api/scans', { params })
  return data
}
