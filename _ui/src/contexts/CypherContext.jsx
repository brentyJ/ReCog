import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { sendCypherMessage, getExtractionStatus, getGlobalExtractionStatus } from '@/lib/api'

const CypherContext = createContext(null)

export function CypherProvider({ children, caseId: propCaseId }) {
  const [messages, setMessages] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [extractionStatus, setExtractionStatus] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  const [activeCaseId, setActiveCaseId] = useState(propCaseId)
  const [lastUserMessage, setLastUserMessage] = useState(null)
  const prevExtractionRef = useRef({ current: 0, status: 'idle', currentDoc: null })
  // Track if events are driving progress (prevents polling from duplicating messages)
  const eventDrivenRef = useRef(false)
  const [currentView, setCurrentView] = useState(
    window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
  )
  const [pendingValidation, setPendingValidation] = useState(null)

  useEffect(() => {
    const handleHashChange = () => {
      const newView = window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
      setCurrentView(newView)
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  const addCypherMessageInternal = useCallback((content, suggestions = []) => {
    setMessages((prev) => [...prev, { role: 'assistant', content, suggestions, timestamp: Date.now() }])
  }, [])

  // Handle extraction events from PreflightPage
  useEffect(() => {
    const handleExtractionStart = (e) => {
      const { caseId, total, caseName } = e.detail
      eventDrivenRef.current = true // Mark as event-driven to prevent polling duplicates
      setActiveCaseId(caseId)
      setExtractionStatus({ status: 'processing', current: 0, total, current_doc: null })

      // Auto-open Cypher when extraction starts
      setIsOpen(true)

      const msg = caseName
        ? `Processing started for "${caseName}". ${total} document${total !== 1 ? 's' : ''} queued.`
        : `Processing started. ${total} document${total !== 1 ? 's' : ''} queued.`
      addCypherMessageInternal(msg, [])
      prevExtractionRef.current = { current: 0, status: 'processing', currentDoc: null }
    }

    const handleExtractionProgress = (e) => {
      const { current, total, currentDoc } = e.detail
      const remaining = total - current
      const prevState = prevExtractionRef.current

      if (current > prevState.current && prevState.currentDoc) {
        const truncatedName = prevState.currentDoc.length > 35
          ? prevState.currentDoc.substring(0, 32) + '...'
          : prevState.currentDoc
        addCypherMessageInternal(`Processed: ${truncatedName}. ${remaining + 1} remaining.`, [])
      }

      setExtractionStatus({ status: 'processing', current, total, current_doc: currentDoc })
      prevExtractionRef.current = { current, status: 'processing', currentDoc }
    }

    const handleExtractionComplete = (e) => {
      const { successCount, errorCount, skippedCount = 0, total } = e.detail
      const lastDoc = prevExtractionRef.current.currentDoc

      if (lastDoc) {
        const truncatedName = lastDoc.length > 35
          ? lastDoc.substring(0, 32) + '...'
          : lastDoc
        addCypherMessageInternal(`Processed: ${truncatedName}. 0 remaining.`, [])
      }

      setExtractionStatus({
        status: 'complete',
        current: total,
        total,
        current_doc: null,
        insights_extracted: successCount,
        failed: errorCount,
        skipped: skippedCount
      })

      let msg
      if (errorCount > 0 || skippedCount > 0) {
        const parts = [`${successCount} succeeded`]
        if (errorCount > 0) parts.push(`${errorCount} failed`)
        if (skippedCount > 0) parts.push(`${skippedCount} skipped`)
        msg = `Processing complete. ${parts.join(', ')}. Review results?`
      } else {
        msg = `Processing complete. ${successCount} document${successCount !== 1 ? 's' : ''} extracted. Review findings?`
      }

      addCypherMessageInternal(msg, [
        { text: 'View insights', action: 'navigate_insights', icon: 'Lightbulb' },
        { text: 'Review entities', action: 'navigate_entities', icon: 'Users' },
      ])

      prevExtractionRef.current = { current: total, status: 'complete', currentDoc: null }
      // Reset event-driven flag after a delay to allow polling to sync state
      setTimeout(() => { eventDrivenRef.current = false }, 3000)
    }

    window.addEventListener('recog-extraction-start', handleExtractionStart)
    window.addEventListener('recog-extraction-progress', handleExtractionProgress)
    window.addEventListener('recog-extraction-complete', handleExtractionComplete)
    return () => {
      window.removeEventListener('recog-extraction-start', handleExtractionStart)
      window.removeEventListener('recog-extraction-progress', handleExtractionProgress)
      window.removeEventListener('recog-extraction-complete', handleExtractionComplete)
    }
  }, [addCypherMessageInternal])

  // Poll extraction status - either case-specific or global
  useEffect(() => {
    let isMounted = true
    let intervalId = null
    const caseId = activeCaseId || propCaseId

    const pollStatus = async () => {
      try {
        const response = caseId
          ? await getExtractionStatus(caseId)
          : await getGlobalExtractionStatus()

        if (!isMounted) return

        const data = response.data || response
        const prevState = prevExtractionRef.current

        // Skip polling updates entirely when events are driving progress
        // This prevents polling from overwriting event-driven status with stale backend data
        if (eventDrivenRef.current) {
          // Only update if backend confirms processing/complete (sync state)
          if (data.status === 'processing' || data.status === 'complete') {
            // Don't overwrite - events are more real-time than polling
          }
          return
        }

        if (prevState.status === 'idle' || data.status !== extractionStatus?.status) {
          // Only send messages from polling if NOT event-driven (prevents duplicates)
          if (data.status === 'processing' && prevState.status !== 'processing') {
            setIsOpen(true)
            addCypherMessageInternal(
              `Processing started. ${data.total} document${data.total !== 1 ? 's' : ''} queued.`,
              []
            )
          }

          if (data.status === 'complete' && prevState.status === 'processing') {
            addCypherMessageInternal(
              `Processing complete. ${data.insights_extracted || 0} insights extracted. ` +
              `${data.entities_identified || 0} entities identified. Review findings?`,
              [
                { text: 'View insights', action: 'navigate_insights', icon: 'Lightbulb' },
                { text: 'Review entities', action: 'navigate_entities', icon: 'Users' }
              ]
            )
          }

          setExtractionStatus(data)
          prevExtractionRef.current = {
            current: data.current || 0,
            status: data.status || 'idle',
            currentDoc: data.current_doc || null
          }

          if (!caseId && data.active_case_id) {
            setActiveCaseId(data.active_case_id)
          }
        }
      } catch (error) {
        console.error('Failed to poll extraction status:', error)
      }
    }

    const setupPolling = () => {
      if (intervalId) clearInterval(intervalId)
      const rate = extractionStatus?.status === 'processing' ? 2000 : 5000
      intervalId = setInterval(pollStatus, rate)
    }

    pollStatus()
    setupPolling()

    return () => {
      isMounted = false
      if (intervalId) clearInterval(intervalId)
    }
  }, [activeCaseId, propCaseId, extractionStatus?.status, addCypherMessageInternal])

  const addUserMessage = useCallback((content) => {
    setMessages((prev) => [...prev, { role: 'user', content, timestamp: Date.now() }])
  }, [])

  const addCypherMessage = addCypherMessageInternal

  const sendMessage = useCallback(
    async (text, isRetry = false) => {
      if (!text.trim()) return

      // Store for retry (only on fresh messages, not retries)
      if (!isRetry) {
        setLastUserMessage(text)
        addUserMessage(text)
      }

      setIsProcessing(true)
      try {
        const context = {
          current_view: currentView,
          processing_status: extractionStatus?.status || 'idle',
          extraction_progress: extractionStatus,
          pending_validation: pendingValidation,
          original_message: text
        }
        const caseId = activeCaseId || propCaseId
        const response = await sendCypherMessage(text, caseId, context)
        const data = response.data || response
        addCypherMessage(data.reply, data.suggestions)

        if (data.ui_updates?.refresh) {
          data.ui_updates.refresh.forEach((c) =>
            window.dispatchEvent(new CustomEvent(`refresh-${c}`))
          )
        }
        if (data.ui_updates?.navigate) {
          window.location.hash = `#${data.ui_updates.navigate}`
        }
        if (data.actions?.some((a) => a.type === 'entity_remove')) {
          window.dispatchEvent(new CustomEvent('refresh-entities'))
        }
        // Handle pending validation state
        if ('pending_validation' in (data.ui_updates || {})) {
          setPendingValidation(data.ui_updates.pending_validation)
        }
        if (data.actions?.some((a) => a.type === 'entities_removed')) {
          window.dispatchEvent(new CustomEvent('refresh-entities'))
        }

        return data
      } catch (error) {
        console.error('Cypher message failed:', error)

        // Determine error type for better messaging
        let errorMsg = 'Communication error. Request failed to process.'
        if (error.message?.includes('fetch') || error.message?.includes('network')) {
          errorMsg = 'Network error. Check your connection.'
        } else if (error.message?.includes('500') || error.message?.includes('server')) {
          errorMsg = 'Server error. The backend may be down.'
        } else if (error.message?.includes('timeout')) {
          errorMsg = 'Request timed out. Try again.'
        }

        addCypherMessage(errorMsg, [
          { text: 'Retry', action: 'retry_last', icon: 'RefreshCw' }
        ])
      } finally {
        setIsProcessing(false)
      }
    },
    [activeCaseId, propCaseId, currentView, extractionStatus, addUserMessage, addCypherMessage]
  )

  const retryLast = useCallback(() => {
    if (lastUserMessage && !isProcessing) {
      // Remove the error message before retrying
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1]
        if (lastMsg?.role === 'assistant' && lastMsg.content.includes('error')) {
          return prev.slice(0, -1)
        }
        return prev
      })
      sendMessage(lastUserMessage, true)
    }
  }, [lastUserMessage, isProcessing, sendMessage])

  // Listen for external Cypher message triggers (e.g., from action buttons)
  useEffect(() => {
    const handleCypherMessage = (e) => {
      const { message } = e.detail || {}
      if (message) {
        setIsOpen(true) // Open Cypher panel
        sendMessage(message)
      }
    }
    const handleCypherClose = () => setIsOpen(false)

    window.addEventListener('cypher-send-message', handleCypherMessage)
    window.addEventListener('cypher-close', handleCypherClose)
    return () => {
      window.removeEventListener('cypher-send-message', handleCypherMessage)
      window.removeEventListener('cypher-close', handleCypherClose)
    }
  }, [sendMessage])

  const clearHistory = useCallback(() => setMessages([]), [])

  const value = {
    messages,
    isProcessing,
    extractionStatus,
    sendMessage,
    retryLast,
    clearHistory,
    isOpen,
    setIsOpen,
    currentView,
    caseId: activeCaseId || propCaseId,
    addCypherMessage
  }

  return <CypherContext.Provider value={value}>{children}</CypherContext.Provider>
}

export function useCypher() {
  const context = useContext(CypherContext)
  if (!context) throw new Error('useCypher must be used within CypherProvider')
  return context
}

export default CypherContext
