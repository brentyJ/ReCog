import { useState, useEffect } from 'react'
import { Clipboard, Check, X, Filter, Loader2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  getPreflightItems, 
  filterPreflightItems, 
  excludePreflightItem, 
  includePreflightItem, 
  confirmPreflight 
} from '@/lib/api'

export function PreflightPage() {
  const [sessionId, setSessionId] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [filters, setFilters] = useState({
    min_words: '',
    date_from: '',
    date_to: '',
    keywords: '',
  })

  useEffect(() => {
    // In real app, get session ID from URL params or context
    const storedSessionId = localStorage.getItem('current_preflight_session')
    if (storedSessionId) {
      setSessionId(storedSessionId)
      loadItems(storedSessionId)
    }
  }, [])

  async function loadItems(sid) {
    setLoading(true)
    try {
      const data = await getPreflightItems(sid)
      setItems(data.items || [])
    } catch (error) {
      console.error('Failed to load items:', error)
    } finally {
      setLoading(false)
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
    if (!window.confirm('Process all included items? This will use LLM credits.')) {
      return
    }

    setProcessing(true)
    try {
      await confirmPreflight(sessionId)
      alert('Processing started! Check the Insights page for results.')
    } catch (error) {
      alert(`Failed to start processing: ${error.message}`)
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
          <CardTitle>Items for Review</CardTitle>
          <CardDescription>
            Toggle items on/off before processing
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
              Loading items...
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              No items in this session
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => (
                <div
                  key={item.id}
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
                        {item.entity_count > 0 && (
                          <Badge variant="secondary">
                            {item.entity_count} entities
                          </Badge>
                        )}
                        {item.unknown_entities > 0 && (
                          <Badge variant="outline" className="border-orange-mid text-orange-light">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            {item.unknown_entities} unknown
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirm */}
      {includedCount > 0 && (
        <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
          <div>
            <div className="font-semibold">Ready to process {includedCount} items</div>
            <div className="text-sm text-muted-foreground">
              Est. cost: ${estimatedCost.toFixed(3)} • ~{totalWords.toLocaleString()} words
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
                Processing...
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
