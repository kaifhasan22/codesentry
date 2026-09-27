import { useState } from 'react'
import { Github } from 'lucide-react'
import { Button } from '../ui/Button'

const GITHUB_URL_PATTERN = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+(\.git)?\/?$/

export function ScanForm({ onSubmit, loading }) {
  const [url, setUrl] = useState('')
  const [validationError, setValidationError] = useState(null)

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = url.trim()

    if (!trimmed) {
      setValidationError('Enter a GitHub repository URL.')
      return
    }
    if (!GITHUB_URL_PATTERN.test(trimmed)) {
      setValidationError('Enter a valid GitHub repository URL, e.g. https://github.com/psf/requests.git')
      return
    }
    setValidationError(null)
    onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="repo-url" className="block text-sm font-medium text-ink-300 mb-1.5">
          GitHub Repository URL
        </label>
        <div className="relative">
          <Github size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-700" />
          <input
            id="repo-url"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/psf/requests.git"
            className="w-full bg-base-800 border border-base-600 rounded-md pl-9 pr-3 py-2.5 text-sm font-mono text-ink-100 placeholder:text-ink-700 focus:border-beacon-500 focus:ring-1 focus:ring-beacon-500 outline-none transition-colors"
            disabled={loading}
          />
        </div>
        {validationError && <p className="text-sm text-severity-critical mt-1.5">{validationError}</p>}
      </div>

      <Button type="submit" loading={loading} className="w-full sm:w-auto">
        Run Analysis
      </Button>
    </form>
  )
}
