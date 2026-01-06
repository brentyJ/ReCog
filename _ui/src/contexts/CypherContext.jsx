import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { sendCypherMessage, getExtractionStatus } from '@/lib/api'

const CypherContext = createContext(null)

export function CypherProvider({ children, caseId }) {
  const [messages, setMessages] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [extractionStatus, setExtractionStatus] = useState(null)
  const [isOpen, setIsOpen] = useState(false)

  // Track current view from hash
  const [currentView, setCurrentView] = useState(
    window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
  )

  // Listen for hash changes
  useEffect(() => {
    const handleHashChange = () => {
      const newView = window.location.hash.replace('#', '').split('/')[0] || 'dashboard'
      setCurrentView(newView)
    }

    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // Poll extraction status if we have a case
  useEffect(() => {
    if (!caseId) return

    let isMounted = true

    const pollStatus = async () => {
      try {
        const status = await getExtractionStatus(caseId)
        if (!isMounted) return

        const prevStatus = extractionStatus?.status
        setExtractionStatus(status.data || status)

        // If extraction just completed, add Cypher notification
        if (
          (status.data?.status || status.status) === 'complete' &&
          prevStatus === 'processing'
        ) {
          const data = status.data || status
          addCypherMessage(
            `Processing complete. ${data.insights_extracted || 0} insights extracted. ` +
              `${data.entities_identified || 0} entities identified. Review findings?`,
            [
              { text: 'View insights', action: 'navigate_insights', icon: 'Lightbulb' },
              { text: 'Review entities', action: 'navigate_entities', icon: 'Users' },
            ]
          )
        }
      } catch (error) {
        console.error('Failed to poll extraction status:', error)
      }
    }

    // Poll every 3 seconds
    const interval = setInterval(pollStatus, 3000)
    pollStatus() // Initial poll

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [caseId])

  const addUserMessage = useCallback((content) => {
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content,
        timestamp: Date.now(),
      },
    ])
  }, [])

  const addCypherMessage = useCallback((content, suggestions = []) => {
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content,
        suggestions,
        timestamp: Date.now(),
      },
    ])
  }, [])

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim()) return

      addUserMessage(text)
      setIsProcessing(true)

      try {
        const context = {
          current_view: currentView,
          processing_status: extractionStatus?.status || 'idle',
          extraction_progress: extractionStatus,
        }

        const response = await sendCypherMessage(text, caseId, context)

        // Handle both wrapped and unwrapped response formats
        const data = response.data || response
        addCypherMessage(data.reply, data.suggestions)

        // Execute UI updates
        if (data.ui_updates?.refresh) {
          data.ui_updates.refresh.forEach((component) => {
            window.dispatchEvent(new CustomEvent(`refresh-${component}`))
          })
        }

        // Navigate if requested (hash-based)
        if (data.ui_updates?.navigate) {
          window.location.hash = `#${data.ui_updates.navigate}`
        }

        // Dispatch entity refresh if entity was modified
        if (data.actions?.some((a) => a.type === 'entity_remove')) {
          window.dispatchEvent(new CustomEvent('refresh-entities'))
        }

        return data
      } catch (error) {
        console.error('Cypher message failed:', error)
        addCypherMessage('Communication error. Request failed to process.', [
          { text: 'Retry', action: 'retry_last' },
        ])
      } finally {
        setIsProcessing(false)
      }
    },
    [caseId, currentView, extractionStatus, addUserMessage, addCypherMessage]
  )

  const clearHistory = useCallback(() => {
    setMessages([])
  }, [])

  const value = {
    messages,
    isProcessing,
    extractionStatus,
    sendMessage,
    clearHistory,
    isOpen,
    setIsOpen,
    currentView,
    caseId,
  }

  return <CypherContext.Provider value={value}>{children}</CypherContext.Provider>
}

export function useCypher() {
  const context = useContext(CypherContext)
  if (!context) {
    throw new Error('useCypher must be used within CypherProvider')
  }
  return context
}

export default CypherContext
