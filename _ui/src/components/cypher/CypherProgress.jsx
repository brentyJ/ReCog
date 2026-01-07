import { useState, useEffect, useRef } from 'react'
import { FileText, Loader2, Clock, CheckCircle2 } from 'lucide-react'

export function CypherProgress({ extractionStatus }) {
  const [startTime, setStartTime] = useState(null)
  const [eta, setEta] = useState(null)
  const prevCurrentRef = useRef(0)

  // Track start time and calculate ETA
  useEffect(() => {
    if (!extractionStatus) return

    const { status, current, total } = extractionStatus

    if (status === 'processing' && !startTime) {
      setStartTime(Date.now())
    }

    if (status === 'complete' || status === 'idle') {
      setStartTime(null)
      setEta(null)
      prevCurrentRef.current = 0
      return
    }

    // Calculate ETA when we have progress
    if (startTime && current > 0 && current !== prevCurrentRef.current) {
      const elapsed = Date.now() - startTime
      const avgTimePerDoc = elapsed / current
      const remaining = total - current
      const etaMs = remaining * avgTimePerDoc
      setEta(Math.ceil(etaMs / 1000)) // Convert to seconds
      prevCurrentRef.current = current
    }
  }, [extractionStatus, startTime])

  if (!extractionStatus || extractionStatus.status === 'idle') {
    return null
  }

  const { status, current, total, current_doc } = extractionStatus
  const isProcessing = status === 'processing' || status === 'pending'
  const isComplete = status === 'complete'
  const progress = total > 0 ? Math.round((current / total) * 100) : 0
  const remaining = total - current

  // Truncate document name for display
  const displayDoc = current_doc
    ? current_doc.length > 32
      ? current_doc.substring(0, 29) + '...'
      : current_doc
    : null

  // Format ETA
  const formatEta = (seconds) => {
    if (!seconds || seconds < 0) return null
    if (seconds < 60) return `~${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return secs > 0 ? `~${mins}m ${secs}s` : `~${mins}m`
  }

  if (!isProcessing && !isComplete) {
    return null
  }

  // Completed state
  if (isComplete) {
    const { insights_extracted, failed, skipped } = extractionStatus
    return (
      <div className="bg-card border border-green-500/30 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 text-green-400 mb-2">
          <CheckCircle2 className="w-4 h-4" />
          <span className="font-mono text-sm font-medium">Complete</span>
        </div>
        <div className="text-xs text-muted-foreground font-mono">
          {insights_extracted || total} documents processed
          {failed > 0 && <span className="text-red-400 ml-2">({failed} failed)</span>}
          {skipped > 0 && <span className="text-yellow-400 ml-2">({skipped} skipped)</span>}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card border border-teal-400/30 rounded-lg p-4 mb-4">
      {/* Header with count and ETA */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-teal-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="font-mono text-sm font-medium">Processing</span>
        </div>
        <div className="flex items-center gap-3">
          {eta && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
              <Clock className="w-3 h-3" />
              <span>{formatEta(eta)}</span>
            </div>
          )}
          <span className="font-mono text-sm text-teal-400 font-medium">
            {current}/{total}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2.5 bg-muted rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-gradient-to-r from-teal-500 to-teal-400 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Current document and remaining */}
      <div className="flex items-center justify-between">
        {displayDoc ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono flex-1 min-w-0">
            <FileText className="w-3 h-3 flex-shrink-0" />
            <span className="truncate">{displayDoc}</span>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground font-mono">
            Initializing...
          </div>
        )}
        <div className="text-xs font-mono text-muted-foreground ml-2 flex-shrink-0">
          {remaining} remaining
        </div>
      </div>
    </div>
  )
}
