import { useState } from 'react'
import { Github, ArrowRight } from 'lucide-react'

import { isSupportedGithubUrl } from '../../lib/githubUrl'

export function ScanForm({ onSubmit, loading }) {
  const [url, setUrl] = useState('')
  const [validationError, setValidationError] = useState(null)

  function handleSubmit(event) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) {
      setValidationError('Enter a GitHub repository URL.')
      return
    }
    if (!isSupportedGithubUrl(trimmed)) {
      setValidationError('Enter a valid GitHub repository URL, such as https://github.com/psf/requests.')
      return
    }
    setValidationError(null)
    onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit}>
      <label className="cs-field" htmlFor="repo-url">GitHub repository URL</label>
      <div className="cs-input-with-icon">
        <Github className="cs-input-icon" size={18} />
        <input
          id="repo-url"
          className="cs-input"
          type="url"
          autoComplete="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://github.com/psf/requests"
          disabled={loading}
          aria-invalid={Boolean(validationError)}
          aria-describedby={validationError ? 'repo-url-error' : 'repo-url-help'}
        />
      </div>
      {validationError
        ? <p id="repo-url-error" className="cs-help" style={{ color: 'var(--severity-critical)' }}>{validationError}</p>
        : <p id="repo-url-help" className="cs-help">Paste the repository URL. CodeSentry will analyze it and add the results to your scan history.</p>}
      <button type="submit" disabled={loading} className="cs-btn" style={{ marginTop: 22 }}>
        {loading ? 'Analyzing…' : 'Run analysis'} {!loading && <ArrowRight size={16} />}
      </button>
    </form>
  )
}
