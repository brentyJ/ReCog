/**
 * Virtualization utilities for ReCog UI
 *
 * Consistent configs for Virtuoso across all pages
 */

// Standard viewport overscan (pre-render buffer)
export const VIRTUOSO_CONFIG = {
  // How much extra to render above/below viewport
  increaseViewportBy: { top: 200, bottom: 200 },
}

// For grouped lists (timeline with date headers)
export const GROUPED_VIRTUOSO_CONFIG = {
  ...VIRTUOSO_CONFIG,
}

// Scroll restoration helper
export function saveScrollPosition(key, position) {
  sessionStorage.setItem(`scroll_${key}`, JSON.stringify(position))
}

export function loadScrollPosition(key) {
  const saved = sessionStorage.getItem(`scroll_${key}`)
  return saved ? JSON.parse(saved) : null
}

// Helper to group timeline events by date
export function groupEventsByDate(events) {
  const groups = {}
  events.forEach(event => {
    const date = new Date(event.timestamp).toLocaleDateString()
    if (!groups[date]) {
      groups[date] = { date, events: [] }
    }
    groups[date].events.push(event)
  })
  return Object.values(groups)
}
