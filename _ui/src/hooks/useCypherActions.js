import { useCallback } from 'react'

export function useCypherActions() {
  const executeAction = useCallback(async (actionType, params = {}) => {
    const handlers = {
      // Hash-based navigation
      navigate_findings: () => {
        window.location.hash = '#findings'
      },
      navigate_entities: () => {
        window.location.hash = '#entities'
      },
      navigate_timeline: () => {
        window.location.hash = '#timeline'
      },
      navigate_insights: () => {
        window.location.hash = '#insights'
      },
      navigate_preflight: () => {
        window.location.hash = '#preflight'
      },
      navigate_dashboard: () => {
        window.location.hash = '#dashboard'
      },
      navigate_upload: () => {
        window.location.hash = '#upload'
      },
      navigate_cases: () => {
        window.location.hash = '#cases'
      },
      navigate_patterns: () => {
        window.location.hash = '#patterns'
      },

      apply_filter: (params) => {
        const filterQuery = encodeURIComponent(params?.filters?.query || '')
        window.location.hash = `#insights?filter=${filterQuery}`
      },

      clear_filter: () => {
        window.location.hash = '#insights'
      },

      entity_remove: () => {
        window.dispatchEvent(new CustomEvent('refresh-entities'))
      },

      retry_last: () => {
        // This would need message history access - handled in context
        console.log('Retry requested')
      },
    }

    const handler = handlers[actionType]
    if (!handler) {
      console.warn(`Unknown action type: ${actionType}`)
      return
    }

    await handler(params)
  }, [])

  const refreshComponents = useCallback((componentNames) => {
    componentNames.forEach((name) => {
      window.dispatchEvent(new CustomEvent(`refresh-${name}`))
    })
  }, [])

  return { executeAction, refreshComponents }
}
