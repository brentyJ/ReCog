/**
 * CaseTerminal - Real-time analysis monitor for case processing (v0.8)
 *
 * Displays:
 * - Progress bar showing current stage
 * - Top insights discovered so far
 * - Live log stream of discoveries
 *
 * Polls /api/cases/<id>/progress every 2 seconds during processing.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal, Zap, TrendingUp, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { getCaseProgress } from '@/lib/api'

// Stage display names
const STAGE_LABELS = {
  idle: 'Idle',
  tier0: 'Initial Scan',
  extraction: 'Extracting Insights',
  synthesis: 'Synthesizing Patterns',
  critique: 'Validating',
}

// Status colors
const STATUS_COLORS = {
  pending: 'text-muted-foreground',
  running: 'text-teal-400',
  complete: 'text-emerald-400',
  failed: 'text-red-400',
}

export default function CaseTerminal({ caseId, caseState }) {
  const [logs, setLogs] = useState([])
  const [topInsights, setTopInsights] = useState([])
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const terminalRef = useRef(null)
  const pollInterval = useRef(null)
  const seenInsights = useRef(new Set())

  // Add log entry
  const addLog = useCallback((log) => {
    setLogs(prev => {
      // Prevent duplicates
      if (prev.some(l => l.id === log.id)) return prev
      const newLogs = [...prev, log]
      // Cap at 200 entries
      return newLogs.slice(-200)
    })

    // Auto-scroll to bottom
    setTimeout(() => {
      if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight
      }
    }, 50)
  }, [])

  // Poll for progress
  const pollProgress = useCallback(async () => {
    if (!caseId) return

    try {
      const response = await getCaseProgress(caseId)
      if (response.success && response.data) {
        setProgress(response.data)
        setError(null)

        // Add log if new insight discovered
        if (response.data.recent_insight) {
          const insightId = `insight-${response.data.recent_insight.substring(0, 50)}`
          if (!seenInsights.current.has(insightId)) {
            seenInsights.current.add(insightId)
            addLog({
              id: insightId,
              type: 'insight',
              content: response.data.recent_insight,
              timestamp: new Date(),
            })
          }
        }

        // Update top insights
        if (response.data.top_insights?.length > 0) {
          setTopInsights(response.data.top_insights)
        }

        // Stop polling if complete or failed
        if (response.data.status === 'complete' || response.data.status === 'failed') {
          if (pollInterval.current) {
            clearInterval(pollInterval.current)
            pollInterval.current = null
          }

          // Add completion log
          if (response.data.status === 'complete') {
            addLog({
              id: `complete-${Date.now()}`,
              type: 'success',
              content: `${STAGE_LABELS[response.data.stage] || response.data.stage} complete`,
              timestamp: new Date(),
            })
          } else if (response.data.status === 'failed') {
            addLog({
              id: `failed-${Date.now()}`,
              type: 'error',
              content: response.data.error_message || 'Processing failed',
              timestamp: new Date(),
            })
          }
        }
      }
    } catch (err) {
      console.error('Progress polling error:', err)
      setError(err.message)
    }
  }, [caseId, addLog])

  // Start/stop polling based on case state
  useEffect(() => {
    if (!caseId) return

    // Clear previous interval
    if (pollInterval.current) {
      clearInterval(pollInterval.current)
    }

    // Start polling if in processing state
    const isProcessing = caseState === 'scanning' || caseState === 'processing'

    if (isProcessing) {
      // Initial poll
      pollProgress()
      // Poll every 2 seconds during processing
      pollInterval.current = setInterval(pollProgress, 2000)
    } else {
      // Single poll for non-processing states
      pollProgress()
    }

    return () => {
      if (pollInterval.current) {
        clearInterval(pollInterval.current)
      }
    }
  }, [caseId, caseState, pollProgress])

  // Log icon helper
  const getLogIcon = (type) => {
    switch(type) {
      case 'insight':
        return <Zap className="text-yellow-400 flex-shrink-0" size={14} />
      case 'pattern':
        return <TrendingUp className="text-teal-400 flex-shrink-0" size={14} />
      case 'success':
        return <CheckCircle className="text-emerald-400 flex-shrink-0" size={14} />
      case 'error':
        return <AlertCircle className="text-red-400 flex-shrink-0" size={14} />
      default:
        return <Terminal className="text-muted-foreground flex-shrink-0" size={14} />
    }
  }

  // Significance color
  const getSignificanceColor = (sig) => {
    switch(sig?.toLowerCase()) {
      case 'high': return 'text-red-400 border-red-400/30'
      case 'medium': return 'text-yellow-400 border-yellow-400/30'
      case 'low': return 'text-blue-400 border-blue-400/30'
      default: return 'text-muted-foreground border-border'
    }
  }

  return (
    <div className="h-full flex flex-col bg-black/90 rounded-lg border border-teal-500/30 overflow-hidden">
      {/* Terminal Header */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-teal-500/30 bg-teal-950/50">
        <Terminal size={16} className="text-teal-400" />
        <span className="font-mono text-sm text-teal-400">ANALYSIS MONITOR</span>

        {progress && (
          <Badge
            variant="outline"
            className={`ml-auto font-mono text-xs ${STATUS_COLORS[progress.status]}`}
          >
            {progress.status === 'running' && (
              <Loader2 size={10} className="mr-1 animate-spin" />
            )}
            {STAGE_LABELS[progress.stage] || progress.stage}
            {progress.progress > 0 && ` ${Math.round(progress.progress * 100)}%`}
          </Badge>
        )}
      </div>

      {/* Top Insights Panel */}
      {topInsights.length > 0 && (
        <div className="p-3 border-b border-teal-500/30 bg-teal-950/20 space-y-2">
          <div className="text-xs text-teal-400 font-mono uppercase tracking-wide">
            Top Findings
          </div>
          {topInsights.slice(0, 3).map((insight, i) => (
            <div
              key={insight.id || i}
              className="flex items-start gap-2 text-sm p-2 rounded bg-black/50
                         border border-teal-500/20 hover:border-teal-500/40
                         transition-all group cursor-default"
            >
              <Zap size={14} className="text-yellow-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1 font-mono text-xs text-gray-300 group-hover:text-white line-clamp-2">
                {insight.content}
              </div>
              <span className={`text-[10px] uppercase font-mono px-1.5 py-0.5 rounded border ${getSignificanceColor(insight.significance)}`}>
                {insight.significance || 'LOW'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Log Stream */}
      <div
        ref={terminalRef}
        className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs"
      >
        {error && (
          <div className="text-red-400 text-center py-2 flex items-center justify-center gap-2">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {logs.length === 0 && !error && (
          <div className="text-muted-foreground text-center py-8 space-y-2">
            <Terminal size={24} className="mx-auto opacity-50" />
            <div>Waiting for analysis...</div>
            {caseState === 'clarifying' && (
              <div className="text-xs text-teal-400/70">
                Clarify entities to continue
              </div>
            )}
          </div>
        )}

        {logs.map((log) => (
          <div key={log.id} className="flex items-start gap-2 text-gray-300 py-0.5">
            <span className="text-gray-600 w-16 flex-shrink-0">
              {log.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            {getLogIcon(log.type)}
            <span className="flex-1 break-words">{log.content}</span>
          </div>
        ))}
      </div>

      {/* Progress Bar Footer */}
      {progress && progress.status === 'running' && (
        <div className="px-3 py-2 border-t border-teal-500/30 bg-teal-950/20">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-teal-400 font-mono truncate flex-1">
              {progress.current_item || 'Processing...'}
            </span>
            <span className="text-xs text-gray-500 font-mono">
              {progress.completed_items || 0}/{progress.total_items || '?'}
            </span>
          </div>
          <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-teal-500 to-yellow-400 transition-all duration-500"
              style={{ width: `${(progress.progress || 0) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Complete State */}
      {progress && progress.status === 'complete' && (
        <div className="px-3 py-2 border-t border-emerald-500/30 bg-emerald-950/20 flex items-center gap-2">
          <CheckCircle size={14} className="text-emerald-400" />
          <span className="text-xs text-emerald-400 font-mono">
            Analysis complete
          </span>
          {progress.completed_items > 0 && (
            <span className="text-xs text-gray-500 font-mono ml-auto">
              {progress.completed_items} items processed
            </span>
          )}
        </div>
      )}
    </div>
  )
}
