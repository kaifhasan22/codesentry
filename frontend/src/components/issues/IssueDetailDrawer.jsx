import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Sparkles, Wrench, Maximize2, Minimize2 } from 'lucide-react'
import { CATEGORY_LABEL } from '../../lib/utils'

export function IssueDetailDrawer({ issue, onClose }) {
  const [expanded, setExpanded] = useState(false)
  const drawerRef = useRef(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  const open = Boolean(issue)

  useEffect(() => {
    if (!open) return
    setExpanded(false)
    const body = document.body
    const root = document.getElementById('root')
    const previousFocus = document.activeElement
    const scrollY = window.scrollY
    const scrollX = window.scrollX
    const savedStyle = body.getAttribute('style')
    const wasInert = root?.inert
    const gutter = window.innerWidth - document.documentElement.clientWidth
    const padding = parseFloat(getComputedStyle(body).paddingRight) || 0
    Object.assign(body.style, { position: 'fixed', top: `-${scrollY}px`, left: `-${scrollX}px`, width: '100%', overflow: 'hidden', paddingRight: `${padding + gutter}px` })
    if (root) root.inert = true
    drawerRef.current?.focus({ preventScroll: true })
    const handleKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current()
      }
      if (event.key !== 'Tab') return
      const focusable = [...drawerRef.current.querySelectorAll('button, a[href], input, select, textarea, [tabindex="0"]')].filter((element) => !element.disabled)
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === drawerRef.current)) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === drawerRef.current)) {
        event.preventDefault()
        first?.focus()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      if (savedStyle === null) body.removeAttribute('style')
      else body.setAttribute('style', savedStyle)
      if (root) root.inert = wasInert
      window.scrollTo({ left: scrollX, top: scrollY, behavior: 'instant' })
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
    }
  }, [open])

  if (!issue) return null
  const severity = issue.severity || 'info'

  return createPortal(
    <>
      <button type="button" className="cs-drawer-overlay" tabIndex={-1} onClick={onClose} aria-label="Close finding details" />
      <aside ref={drawerRef} tabIndex={-1} className={`cs-drawer${expanded ? ' cs-drawer-expanded' : ''}`} role="dialog" aria-modal="true" aria-labelledby="issue-detail-title">
        <div className="cs-drawer-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className={'cs-severity cs-severity-' + severity}>{severity}</span>
            <span className="cs-mono">{CATEGORY_LABEL[issue.category] || issue.category || 'Finding'}</span>
          </div>
          <div className="cs-drawer-actions">
            <button type="button" className="cs-drawer-resize" onClick={() => setExpanded(!expanded)} aria-expanded={expanded} aria-label={expanded ? 'Restore details size' : 'Expand details'}>
              {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}{expanded ? 'Restore' : 'Expand'}
            </button>
          <button type="button" className="cs-drawer-close" onClick={onClose} aria-label="Close details"><X size={17} /></button>
          </div>
        </div>
        <div className="cs-drawer-body">
          <h2 id="issue-detail-title" style={{ margin: 0, fontSize: 21, lineHeight: 1.3 }}>{issue.title || 'Code finding'}</h2>
          {issue.comparison_state === 'resolved' && <p className="cs-description">Resolved finding · details from scan #{issue.source_scan_id}</p>}
          <p className="cs-mono" style={{ marginTop: 9 }}>{issue.file_path || 'File unavailable'}{issue.line ? ':' + issue.line : ''}</p>
          <section className="cs-detail-section"><h3>Message</h3><p>{issue.message || 'No message was provided.'}</p></section>
          {issue.priority && <section className="cs-detail-section"><h3>Priority {issue.priority.toUpperCase()}</h3><p>Review priority · {issue.priority_score} points</p><ul>{issue.priority_reasons?.map((reason) => <li key={reason}>{reason}</li>)}</ul></section>}
          {issue.snippet && <section className="cs-detail-section"><h3>Snippet</h3><pre className="cs-detail-code">{issue.snippet}</pre></section>}
          <section className="cs-detail-section"><h3><Sparkles size={13} /> AI explanation</h3><p>{issue.ai_explanation || <span style={{ color: 'rgb(var(--ink-500))' }}>AI explanation unavailable.</span>}</p></section>
          <section className="cs-detail-section"><h3><Wrench size={13} /> Suggested fix</h3><p>{issue.fix_suggestion || <span style={{ color: 'rgb(var(--ink-500))' }}>No fix suggestion available.</span>}</p></section>
        </div>
      </aside>
    </>,
    document.body
  )
}
