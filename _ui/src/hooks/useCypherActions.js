import { useCallback } from 'react'

// Helper to navigate and close Cypher panel
const navigateTo = (hash) => {
  window.location.hash = hash
  window.dispatchEvent(new CustomEvent('cypher-close'))
}

export function useCypherActions() {
  const executeAction = useCallback(async (actionType, params = {}) => {
    const handlers = {
      // Hash-based navigation (hash value without # - browser adds it)
      navigate_findings: () => navigateTo('findings'),
      navigate_entities: () => navigateTo('entities'),
      navigate_timeline: () => navigateTo('timeline'),
      navigate_insights: () => navigateTo('insights'),
      navigate_preflight: () => navigateTo('preflight'),
      navigate_dashboard: () => navigateTo('dashboard'),
      navigate_upload: () => navigateTo('upload'),
      navigate_cases: () => navigateTo('cases'),
      navigate_patterns: () => navigateTo('patterns'),

      apply_filter: (params) => {
        const filterQuery = encodeURIComponent(params?.filters?.query || '')
        navigateTo(`insights?filter=${filterQuery}`)
      },

      clear_filter: () => navigateTo('insights'),

      entity_remove: () => {
        window.dispatchEvent(new CustomEvent('refresh-entities'))
      },

      retry_last: () => {
        // This would need message history access - handled in context
        console.log('Retry requested')
      },

      // Entity validation actions - these trigger Cypher messages
      validate_entities: () => {
        // Dispatch event to trigger Cypher validation
        window.dispatchEvent(new CustomEvent('cypher-send-message', { detail: { message: 'validate entities' } }))
      },
      confirm_validation: () => {
        window.dispatchEvent(new CustomEvent('cypher-send-message', { detail: { message: 'yes remove them' } }))
      },
      cancel_validation: () => {
        window.dispatchEvent(new CustomEvent('cypher-send-message', { detail: { message: 'no keep all' } }))
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
