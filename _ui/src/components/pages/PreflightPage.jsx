import { useState, useEffect } from 'react'
import { Virtuoso } from 'react-virtuoso'
import { Clipboard, Check, Filter, Loader2, FolderOpen, CheckSquare, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingState } from '@/components/ui/loading-state'
import { EmptyState } from '@/components/ui/empty-state'
import {
  getPreflightItems,
  getPreflight,
  filterPreflightItems,
  excludePreflightItem,
  includePreflightItem,
  confirmPreflight,
  getCase,
  getDocumentText,
  extractWithCase,
} from '@/lib/api'
import { VIRTUOSO_CONFIG } from '@/lib/virtualization'

export function PreflightPage() {
  const [sessionId, setSessionId] = useState(null)
  const [caseId, setCaseId] = useState(null)
  const [caseData, setCaseData] = useState(null)
  const [items, setItems] = useState([])
  const [sessionData, setSessionData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [processedCount, setProcessedCount] = useState(0)
  const [filters, setFilters] = useState({
    min_words: '',
    date_from: '',
    date_to: '',
    keywords: '',
  })

  useEffect(() => {
    function loadFromHash() {
      // Get session ID from URL hash or localStorage
      const hash = window.location.hash
      const hashMatch = hash.match(/preflight\/(\d+)/)

      let sid = null
      if (hashMatch) {
        sid = hashMatch[1]
      } else {
        sid = localStorage.getItem('current_preflight_session')
      }

      if (sid) {
        setSessionId(sid)
        loadSession(sid)
        loadItems(sid)

        // Check for linked case
        const linkedCaseId = sessionStorage.getItem(`preflight_case_${sid}`)
        if (linkedCaseId) {
          setCaseId(linkedCaseId)
          loadCase(linkedCaseId)
        }
      } else {
        setSessionId(null)
        setSessionData(null)
        setItems([])
      }
    }

    // Load on mount
    loadFromHash()

    // Re-load when hash changes (e.g., navigating to different session)
    window.addEventListener('hashchange', loadFromHash)
    return () => window.removeEventListener('hashchange', loadFromHash)
  }, [])

  async function loadSession(sid) {
    try {
      const data = await getPreflight(sid)
      const session = data.data || data
      setSessionData(session)
      
      // If session has case_id from backend, use that (more reliable than sessionStorage)
      if (session.case_id && !caseId) {
        setCaseId(session.case_id)
        loadCase(session.case_id)
      }
    } catch (error) {
      console.error('Failed to load session:', error)
    }
  }

  async function loadItems(sid) {
    setLoading(true)
    try {
      const data = await getPreflightItems(sid)
      setItems(data.data?.items || data.items || [])
    } catch (error) {
      console.error('Failed to load items:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadCase(cid) {
    try {
      const data = await getCase(cid)
      setCaseData(data.data || data)
    } catch (error) {
      console.error('Failed to load case:', error)
    }
  }

  async function handleToggleItem(itemId, currentlyIncluded) {
    try {
      if (currentlyIncluded) {
        await excludePreflightItem(sessionId, itemId)
      } else {
        await includePreflightItem(sessionId, itemId)
      }
      await loadItems(sessionId)
    } catch (error) {
      console.error('Failed to toggle item:', error)
    }
  }

  async function handleSelectAll() {
    setLoading(true)
    try {
      // Include all items that are currently excluded
      const excludedItems = items.filter(i => !i.included)
      for (const item of excludedItems) {
        await includePreflightItem(sessionId, item.id)
      }
      await loadItems(sessionId)
    } catch (error) {
      console.error('Failed to select all:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleDeselectAll() {
    setLoading(true)
    try {
      // Exclude all items that are currently included
      const includedItems = items.filter(i => i.included)
      for (const item of includedItems) {
        await excludePreflightItem(sessionId, item.id)
      }
      await loadItems(sessionId)
    } catch (error) {
      console.error('Failed to deselect all:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleApplyFilters() {
    setLoading(true)
    try {
      const filterData = {}
      if (filters.min_words) filterData.min_words = parseInt(filters.min_words)
      if (filters.date_from) filterData.date_from = filters.date_from
      if (filters.date_to) filterData.date_to = filters.date_to
      if (filters.keywords) filterData.keywords = filters.keywords.split(',').map(k => k.trim())
      
      await filterPreflightItems(sessionId, filterData)
      await loadItems(sessionId)
    } catch (error) {
      console.error('Failed to apply filters:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm() {
    const includedItems = items.filter(i => i.included)

    if (!window.confirm(
      `Process ${includedItems.length} items?` +
      (caseData ? ` Context from "${caseData.title}" will be injected.` : '') +
      '\n\nThis will use LLM credits.'
    )) {
      return
    }

    setProcessing(true)
    setProcessedCount(0)

    // Dispatch extraction started event for Cypher
    window.dispatchEvent(new CustomEvent('recog-extraction-start', {
      detail: {
        caseId,
        total: includedItems.length,
        caseName: caseData?.title,
      }
    }))

    try {
      // First confirm the preflight session
      await confirmPreflight(sessionId)

      // Extract insights from each included item
      let successCount = 0
      let errorCount = 0
      let skippedCount = 0

      for (let i = 0; i < includedItems.length; i++) {
        const item = includedItems[i]
        setProcessedCount(i + 1)

        // Dispatch progress event for Cypher
        window.dispatchEvent(new CustomEvent('recog-extraction-progress', {
          detail: {
            current: i + 1,
            total: includedItems.length,
            currentDoc: item.title || item.source_name || 'Item ' + (i + 1),
          }
        }))

        try {
          // Fetch the document text
          const docResponse = await getDocumentText(item.id)
          const text = docResponse.data?.text

          if (!text || text.trim().length < 50) {
            console.warn(`Skipping item ${item.id}: insufficient text`)
            skippedCount++
            continue
          }

          // Extract insights with optional case context
          await extractWithCase(
            text,
            item.source_type || 'document',
            caseId || null,
            {
              source_id: `preflight_item_${item.id}`,
              save: true,
              check_similarity: true,
            }
          )

          successCount++
        } catch (itemError) {
          console.error(`Failed to extract from item ${item.id}:`, itemError)
          errorCount++
        }
      }

      // Clear the session storage
      sessionStorage.removeItem(`preflight_case_${sessionId}`)

      // Clear this session from the upload_files localStorage to prevent stale data
      // Note: sessionId from URL is always a string, but localStorage might have numbers
      try {
        const sessionIdStr = String(sessionId)
        const savedUploads = localStorage.getItem('upload_files')
        if (savedUploads) {
          const uploads = JSON.parse(savedUploads)
          // Remove files belonging to this session (compare as strings to avoid type mismatch)
          const filteredUploads = uploads.filter(f => String(f.sessionId) !== sessionIdStr)
          localStorage.setItem('upload_files', JSON.stringify(filteredUploads))
          console.log(`Cleared session ${sessionIdStr} from localStorage. Remaining: ${filteredUploads.length} files`)
        }
        // Also clear from preflight_sessions if present
        const savedSessions = localStorage.getItem('preflight_sessions')
        if (savedSessions) {
          const sessions = JSON.parse(savedSessions)
          const filteredSessions = sessions.filter(s => String(s) !== sessionIdStr)
          localStorage.setItem('preflight_sessions', JSON.stringify(filteredSessions))
        }
        // Clear current_preflight_session if it matches
        const currentSession = localStorage.getItem('current_preflight_session')
        if (currentSession && String(currentSession) === sessionIdStr) {
          localStorage.removeItem('current_preflight_session')
        }
      } catch (e) {
        console.warn('Failed to clear localStorage:', e)
      }

      // Dispatch extraction complete event for Cypher
      window.dispatchEvent(new CustomEvent('recog-extraction-complete', {
        detail: {
          caseId,
          successCount,
          errorCount,
          skippedCount,
          total: includedItems.length,
        }
      }))

      // Navigation happens after a short delay to allow Cypher to show completion
      // Cypher will display the completion message with suggestions
      setTimeout(() => {
        if (caseData) {
          window.location.hash = ''  // Back to dashboard
        } else {
          window.location.hash = 'insights'
        }
      }, 1500)
      
    } catch (error) {
      console.error('Processing failed:', error)
    } finally {
      setProcessing(false)
    }
  }

  const includedCount = items.filter(item => item.included).length
  const totalWords = items
    .filter(item => item.included)
    .reduce((sum, item) => sum + (item.word_count || 0), 0)
  const estimatedCost = (totalWords / 1000) * 0.002 // rough estimate

  if (!sessionId) {
    return (
      <div className="max-w-4xl mx-auto">
        <Card>
          <CardContent className="pt-12 pb-12 text-center text-muted-foreground">
            No active preflight session. Upload a file first.
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Clipboard className="w-6 h-6 text-orange-light" />
          Preflight Review
        </h2>
        <p className="text-muted-foreground">
          Review and filter items before LLM processing
        </p>
      </div>

      {/* Case Context Banner */}
      {caseData && (
        <Card className="border-orange-mid/50 bg-orange-mid/10">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-start gap-3">
              <FolderOpen className="w-5 h-5 text-orange-light mt-0.5" />
              <div className="flex-1">
                <div className="font-semibold text-orange-light">
                  Linked to Case: {caseData.title}
                </div>
                {caseData.context && (
                  <div className="text-sm text-muted-foreground mt-1">
                    {caseData.context}
                  </div>
                )}
                {caseData.focus_areas?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {caseData.focus_areas.map((area, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {area}
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-2">
                  Case context will be injected into extraction prompts for more relevant insights.
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-2xl font-bold text-orange-light">{items.length}</div>
              <div className="text-sm text-muted-foreground">Total Items</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[#5fb3a1]">{includedCount}</div>
              <div className="text-sm text-muted-foreground">Included</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-light">
                {totalWords.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">Words to Process</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-light">
                ${estimatedCost.toFixed(3)}
              </div>
              <div className="text-sm text-muted-foreground">Est. Cost</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="w-5 h-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label>Min Words</Label>
              <Input
                type="number"
                placeholder="e.g., 50"
                value={filters.min_words}
                onChange={(e) => setFilters({...filters, min_words: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label>Date From</Label>
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilters({...filters, date_from: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label>Date To</Label>
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilters({...filters, date_to: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <Label>Keywords</Label>
              <Input
                placeholder="word1, word2"
                value={filters.keywords}
                onChange={(e) => setFilters({...filters, keywords: e.target.value})}
              />
            </div>
          </div>
          <Button onClick={handleApplyFilters} disabled={loading} className="gap-2">
            <Filter className="w-4 h-4" />
            Apply Filters
          </Button>
        </CardContent>
      </Card>

      {/* Items List */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Items for Review</CardTitle>
              <CardDescription>
                Toggle items on/off before processing
              </CardDescription>
            </div>
            {items.length > 0 && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAll}
                  disabled={loading || items.every(i => i.included)}
                  className="gap-1.5"
                >
                  <CheckSquare className="w-4 h-4" />
                  Select All
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDeselectAll}
                  disabled={loading || items.every(i => !i.included)}
                  className="gap-1.5"
                >
                  <Square className="w-4 h-4" />
                  Deselect All
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <LoadingState message="Loading items..." size="lg" />
          ) : items.length === 0 ? (
            <EmptyState
              icon={Clipboard}
              title="No items in this session"
              description="Upload a file first to see items for review."
            />
          ) : (
            <div style={{ height: 'calc(100vh - 550px)', minHeight: '300px' }}>
              <Virtuoso
                data={items}
                {...VIRTUOSO_CONFIG}
                itemContent={(index, item) => (
                  <div className="pb-2">
                    <div
                      className={`
                        p-4 rounded-lg border transition-all
                        ${item.included
                          ? 'bg-card border-orange-mid/30'
                          : 'bg-muted/30 border-border opacity-60'
                        }
                      `}
                    >
                      <div className="flex items-start gap-3">
                        <button
                          onClick={() => handleToggleItem(item.id, item.included)}
                          className={`
                            mt-1 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0
                            ${item.included
                              ? 'bg-orange-mid border-orange-mid text-background'
                              : 'border-muted-foreground hover:border-orange-mid'
                            }
                          `}
                        >
                          {item.included && <Check className="w-3 h-3" />}
                        </button>

                        <div className="flex-1 min-w-0">
                          <div className="font-semibold mb-1">{item.title || `Item ${item.id}`}</div>
                          <div className="text-sm text-muted-foreground line-clamp-2 mb-2">
                            {item.preview || item.text?.substring(0, 200)}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {item.word_count && (
                              <Badge variant="secondary">
                                {item.word_count} words
                              </Badge>
                            )}
                            {item.entities_count > 0 && (
                              <Badge variant="secondary">
                                {item.entities_count} entities
                              </Badge>
                            )}
                            {item.flags?.has_questions && (
                              <Badge variant="outline" className="border-blue-500/50 text-blue-400">
                                Has questions
                              </Badge>
                            )}
                            {item.flags?.has_decisions && (
                              <Badge variant="outline" className="border-green-500/50 text-green-400">
                                Has decisions
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirm */}
      {includedCount > 0 && (
        <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
          <div>
            <div className="font-semibold">
              Ready to process {includedCount} items
              {caseData && (
                <span className="text-orange-light ml-2">
                  → {caseData.title}
                </span>
              )}
            </div>
            <div className="text-sm text-muted-foreground">
              Est. cost: ${estimatedCost.toFixed(3)} • ~{totalWords.toLocaleString()} words
              {caseData && ' • Case context will be injected'}
            </div>
          </div>
          <Button 
            onClick={handleConfirm} 
            disabled={processing}
            size="lg"
            className="gap-2"
          >
            {processing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Extracting {processedCount}/{items.filter(i => i.included).length}...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Confirm & Process
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
