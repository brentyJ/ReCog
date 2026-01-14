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
export async function uploadFile(file, caseId = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (caseId) {
    formData.append('case_id', caseId)
  }

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

// Batch upload multiple files into a single preflight session
export async function uploadFilesBatch(files, caseId = null) {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  if (caseId) {
    formData.append('case_id', caseId)
  }

  const response = await fetch(`${API_BASE}/upload/batch`, {
    method: 'POST',
    body: formData,
  })

  const data = await response.json()

  if (!response.ok) {
    throw new APIError(data.error || 'Batch upload failed', response.status, data)
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

export async function rejectEntity(entityId, reason = 'not_a_name') {
  return fetchAPI(`/entities/${entityId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason, delete_entity: true }),
  })
}

export async function getEntityStats() {
  return fetchAPI('/entities/stats')
}

export async function validateEntities(batchSize = 50) {
  return fetchAPI('/entities/validate', {
    method: 'POST',
    body: JSON.stringify({ batch_size: batchSize }),
  })
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

export async function getInsightActivity(days = 30) {
  return fetchAPI(`/insights/activity?days=${days}`)
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

// Cases
export async function getCases(filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/cases?${params}`)
}

export async function getCase(caseId) {
  return fetchAPI(`/cases/${caseId}`)
}

export async function createCase(data) {
  return fetchAPI('/cases', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateCase(caseId, updates) {
  return fetchAPI(`/cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function deleteCase(caseId) {
  return fetchAPI(`/cases/${caseId}`, {
    method: 'DELETE',
  })
}

export async function getCaseDocuments(caseId) {
  return fetchAPI(`/cases/${caseId}/documents`)
}

export async function addCaseDocument(caseId, documentId, impactNotes = '') {
  return fetchAPI(`/cases/${caseId}/documents`, {
    method: 'POST',
    body: JSON.stringify({ document_id: documentId, impact_notes: impactNotes }),
  })
}

export async function removeCaseDocument(caseId, documentId) {
  return fetchAPI(`/cases/${caseId}/documents/${documentId}`, {
    method: 'DELETE',
  })
}

// Document Text Retrieval
export async function getDocumentText(documentId) {
  return fetchAPI(`/documents/${documentId}/text`)
}

export async function getCaseStats(caseId) {
  return fetchAPI(`/cases/${caseId}/stats`)
}

export async function getCaseContext(caseId) {
  return fetchAPI(`/cases/${caseId}/context`)
}

// Findings
export async function promoteToFinding(caseId, insightId, data = {}) {
  return fetchAPI('/findings', {
    method: 'POST',
    body: JSON.stringify({ case_id: caseId, insight_id: insightId, ...data }),
  })
}

export async function getCaseFindings(caseId, filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/cases/${caseId}/findings?${params}`)
}

export async function getFinding(findingId) {
  return fetchAPI(`/findings/${findingId}`)
}

export async function updateFinding(findingId, updates) {
  return fetchAPI(`/findings/${findingId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function addFindingNote(findingId, note) {
  return fetchAPI(`/findings/${findingId}/note`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export async function deleteFinding(findingId) {
  return fetchAPI(`/findings/${findingId}`, {
    method: 'DELETE',
  })
}

export async function autoPromoteFindings(caseId, insightIds, options = {}) {
  return fetchAPI(`/cases/${caseId}/findings/auto-promote`, {
    method: 'POST',
    body: JSON.stringify({ insight_ids: insightIds, ...options }),
  })
}

export async function getFindingsStats(caseId) {
  return fetchAPI(`/cases/${caseId}/findings/stats`)
}

// Case Timeline
export async function getCaseTimeline(caseId, filters = {}) {
  const params = new URLSearchParams(filters)
  return fetchAPI(`/cases/${caseId}/timeline?${params}`)
}

export async function addTimelineNote(caseId, note) {
  return fetchAPI(`/cases/${caseId}/timeline`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export async function annotateTimelineEvent(eventId, annotation) {
  return fetchAPI(`/timeline/${eventId}/annotate`, {
    method: 'POST',
    body: JSON.stringify({ annotation }),
  })
}

export async function getTimelineSummary(caseId) {
  return fetchAPI(`/cases/${caseId}/timeline/summary`)
}

export async function getCaseActivity(caseId, limit = 10) {
  return fetchAPI(`/cases/${caseId}/activity?limit=${limit}`)
}

// Extraction with Case
export async function extractWithCase(text, sourceType, caseId, options = {}) {
  return fetchAPI('/extract', {
    method: 'POST',
    body: JSON.stringify({
      text,
      source_type: sourceType,
      case_id: caseId,
      ...options,
    }),
  })
}

// =============================================================================
// CYPHER - Conversational Analysis Interface
// =============================================================================

export async function sendCypherMessage(message, caseId, context = {}) {
  return fetchAPI('/cypher/message', {
    method: 'POST',
    body: JSON.stringify({
      message,
      case_id: caseId,
      context,
    }),
  })
}

export async function getExtractionStatus(caseId) {
  return fetchAPI(`/extraction/status/${caseId}`)
}

export async function getGlobalExtractionStatus() {
  return fetchAPI('/extraction/status')
}

// =============================================================================
// CASE PROGRESS & COST ESTIMATION (v0.8)
// =============================================================================

export async function getCaseProgress(caseId) {
  return fetchAPI(`/cases/${caseId}/progress`)
}

export async function getCaseCostEstimate(caseId, model = null) {
  const params = model ? `?model=${model}` : ''
  return fetchAPI(`/cases/${caseId}/estimate${params}`)
}

export async function startCaseProcessing(caseId, confirmCost = false) {
  return fetchAPI(`/cases/${caseId}/start-processing`, {
    method: 'POST',
    body: JSON.stringify({ confirm_cost: confirmCost }),
  })
}

// =============================================================================
// PROVIDER MANAGEMENT
// =============================================================================

export async function getProviders() {
  return fetchAPI('/providers')
}

export async function getProvider(providerName) {
  return fetchAPI(`/providers/${providerName}`)
}

export async function configureProvider(providerName, apiKey, verify = true) {
  return fetchAPI(`/providers/${providerName}`, {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey, verify }),
  })
}

export async function removeProvider(providerName) {
  return fetchAPI(`/providers/${providerName}`, {
    method: 'DELETE',
  })
}

export async function verifyProvider(providerName) {
  return fetchAPI(`/providers/${providerName}/verify`, {
    method: 'POST',
  })
}

export async function getProvidersStatus() {
  return fetchAPI('/providers/status')
}
