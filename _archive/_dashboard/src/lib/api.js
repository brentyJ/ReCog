// API client for ReCog Flask backend

const API_BASE = '/api'

class APIError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.data = data
  }
}

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    const data = await response.json()

    if (!response.ok) {
      throw new APIError(
        data.error || 'Request failed',
        response.status,
        data
      )
    }

    return data
  } catch (error) {
    if (error instanceof APIError) {
      throw error
    }
    throw new APIError('Network error', 0, { error: error.message })
  }
}

// Health & Info
export async function getHealth() {
  return fetchAPI('/health')
}

export async function getInfo() {
  return fetchAPI('/info')
}

// Tier 0 Signal Extraction
export async function analyzeTier0(text) {
  return fetchAPI('/tier0', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

// File Upload & Detection
export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })

  const data = await response.json()
  
  if (!response.ok) {
    throw new APIError(data.error || 'Upload failed', response.status, data)
  }

  return data
}

export async function detectFileFormat(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/detect`, {
    method: 'POST',
    body: formData,
  })

  const data = await response.json()
  
  if (!response.ok) {
    throw new APIError(data.error || 'Detection failed', response.status, data)
  }

  return data
}

// Preflight Sessions
export async function getPreflight(sessionId) {
  return fetchAPI(`/preflight/${sessionId}`)
}

export async function getPreflightItems(sessionId) {
  return fetchAPI(`/preflight/${sessionId}/items`)
}

export async function filterPreflightItems(sessionId, filters) {
  return fetchAPI(`/preflight/${sessionId}/filter`, {
    method: 'POST',
    body: JSON.stringify(filters),
  })
}

export async function excludePreflightItem(sessionId, itemId) {
  return fetchAPI(`/preflight/${sessionId}/exclude/${itemId}`, {
    method: 'POST',
  })
}

export async function includePreflightItem(sessionId, itemId) {
  return fetchAPI(`/preflight/${sessionId}/include/${itemId}`, {
    method: 'POST',
  })
}

export async function confirmPreflight(sessionId) {
  return fetchAPI(`/preflight/${sessionId}/confirm`, {
    method: 'POST',
  })
}

// Entities
export async function getEntities(filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/entities?${params}`)
}

export async function getUnknownEntities() {
  return fetchAPI('/entities/unknown')
}

export async function getEntity(entityId) {
  return fetchAPI(`/entities/${entityId}`)
}

export async function updateEntity(entityId, updates) {
  return fetchAPI(`/entities/${entityId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function getEntityStats() {
  return fetchAPI('/entities/stats')
}

// Entity Graph
export async function getEntityRelationships(entityId) {
  return fetchAPI(`/entities/${entityId}/relationships`)
}

export async function addEntityRelationship(entityId, data) {
  return fetchAPI(`/entities/${entityId}/relationships`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getEntityNetwork(entityId, depth = 2) {
  return fetchAPI(`/entities/${entityId}/network?depth=${depth}`)
}

export async function getEntityTimeline(entityId) {
  return fetchAPI(`/entities/${entityId}/timeline`)
}

export async function getEntitySentiment(entityId) {
  return fetchAPI(`/entities/${entityId}/sentiment`)
}

// Insights
export async function getInsights(filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/insights?${params}`)
}

export async function getInsight(insightId) {
  return fetchAPI(`/insights/${insightId}`)
}

export async function updateInsight(insightId, updates) {
  return fetchAPI(`/insights/${insightId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function deleteInsight(insightId, hard = false) {
  return fetchAPI(`/insights/${insightId}?hard=${hard}`, {
    method: 'DELETE',
  })
}

export async function getInsightStats() {
  return fetchAPI('/insights/stats')
}

// Synthesis
export async function createClusters(data) {
  return fetchAPI('/synth/clusters', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getClusters() {
  return fetchAPI('/synth/clusters')
}

export async function runSynthesis(data) {
  return fetchAPI('/synth/run', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getPatterns(filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/synth/patterns?${params}`)
}

export async function getPattern(patternId) {
  return fetchAPI(`/synth/patterns/${patternId}`)
}

export async function updatePattern(patternId, updates) {
  return fetchAPI(`/synth/patterns/${patternId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function getSynthStats() {
  return fetchAPI('/synth/stats')
}

// Processing Queue
export async function getQueue(filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/queue?${params}`)
}

export async function getQueueStats() {
  return fetchAPI('/queue/stats')
}

export async function getQueueItem(itemId) {
  return fetchAPI(`/queue/${itemId}`)
}

export async function retryQueueItem(itemId) {
  return fetchAPI(`/queue/${itemId}/retry`, {
    method: 'POST',
  })
}

export async function deleteQueueItem(itemId) {
  return fetchAPI(`/queue/${itemId}`, {
    method: 'DELETE',
  })
}

export async function clearQueue() {
  return fetchAPI('/queue/clear', {
    method: 'POST',
  })
}
