import { X, Sparkles, Wrench } from 'lucide-react'
import { SeverityBadge } from './SeverityBadge'
import { CATEGORY_LABEL } from '../../lib/utils'

export function IssueDetailDrawer({ issue, onClose }) {
  if (!issue) return null

  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="fixed top-0 right-0 h-screen w-full sm:w-[440px] bg-base-850 border-l border-base-600 z-50 flex flex-col shadow-2xl">
        <div className="flex items-start justify-between px-5 py-4 border-b border-base-700">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={issue.severity} />
            <span className="text-xs text-ink-500">{CATEGORY_LABEL[issue.category] || issue.category}</span>
          </div>
          <button onClick={onClose} className="text-ink-500 hover:text-ink-100">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-5">
          <div>
            <h2 className="text-base font-display font-semibold text-ink-100">{issue.title}</h2>
            <p className="text-xs font-mono text-ink-500 mt-1.5">
              {issue.file_path}
              {issue.line ? `:${issue.line}` : ''}
            </p>
          </div>

          <div>
            <h3 className="text-xs font-medium text-ink-500 uppercase tracking-wide mb-1.5">Message</h3>
            <p className="text-sm text-ink-300 leading-relaxed">{issue.message}</p>
          </div>

          {issue.snippet && (
            <div>
              <h3 className="text-xs font-medium text-ink-500 uppercase tracking-wide mb-1.5">Snippet</h3>
              <pre className="bg-base-950 border border-base-700 rounded-md p-3 text-xs font-mono text-ink-300 overflow-x-auto scrollbar-thin">
                {issue.snippet}
              </pre>
            </div>
          )}

          <div>
            <h3 className="text-xs font-medium text-ink-500 uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
              <Sparkles size={12} />
              AI Explanation
            </h3>
            <p className="text-sm text-ink-300 leading-relaxed">
              {issue.ai_explanation || (
                <span className="text-ink-700 italic">AI explanation unavailable</span>
              )}
            </p>
          </div>

          <div>
            <h3 className="text-xs font-medium text-ink-500 uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
              <Wrench size={12} />
              Fix Suggestion
            </h3>
            <p className="text-sm text-ink-300 leading-relaxed">
              {issue.fix_suggestion || (
                <span className="text-ink-700 italic">No fix suggestion available</span>
              )}
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
