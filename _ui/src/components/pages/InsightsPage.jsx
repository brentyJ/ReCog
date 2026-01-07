import { useState, useEffect } from 'react'
import { Virtuoso } from 'react-virtuoso'
import { Lightbulb, Filter, FolderOpen, CheckCircle, Star, Loader2, FileText } from 'lucide-react'
import { DocumentViewerModal } from '@/components/ui/document-viewer-modal'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LoadingState } from '@/components/ui/loading-state'
import { EmptyState } from '@/components/ui/empty-state'
import { StatCard, StatGrid } from '@/components/ui/stat-card'
import {
  getInsights,
  getInsightStats,
  getCases,
  promoteToFinding,
  autoPromoteFindings,
  getCaseFindings,
} from '@/lib/api'
import { VIRTUOSO_CONFIG } from '@/lib/virtualization'

export function InsightsPage() {
  const [insights, setInsights] = useState([])
  const [stats, setStats] = useState(null)
  const [cases, setCases] = useState([])
  const [findings, setFindings] = useState({}) // Map of insight_id -> finding
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState({}) // Track which insights are being promoted
  const [bulkPromoting, setBulkPromoting] = useState(false)
  const [viewingDoc, setViewingDoc] = useState(null)
  const [filters, setFilters] = useState({
    status: '__all__',  // Use placeholder instead of empty string for Radix Select
    min_significance: '',
    insight_type: '__all__',  // Use placeholder instead of empty string for Radix Select
    case_id: '__none__',  // Use placeholder instead of empty string for Radix Select
  })
  const [activeTab, setActiveTab] = useState('all')

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    // When case filter changes, load findings for that case
    if (filters.case_id && filters.case_id !== '__none__') {
      loadFindingsForCase(filters.case_id)
    } else {
      setFindings({})
    }
  }, [filters.case_id])

  async function loadInitialData() {
    setLoading(true)
    try {
      // Clean filters before API call (remove placeholder values)
      const apiFilters = { ...filters }
      Object.keys(apiFilters).forEach(key => {
        if (!apiFilters[key] || (typeof apiFilters[key] === 'string' && apiFilters[key].startsWith('__'))) {
          delete apiFilters[key]
        }
      })
      const [insightsData, statsData, casesData] = await Promise.all([
        getInsights(apiFilters),
        getInsightStats(),
        getCases({ status: 'active' }),
      ])
      setInsights(insightsData.data?.insights || insightsData.insights || [])
      setStats(statsData.data || statsData)
      setCases(casesData.data?.cases || [])
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadFindingsForCase(caseId) {
    try {
      const data = await getCaseFindings(caseId)
      const findingsMap = {}
      const findingsList = data.data?.findings || data.findings || []
      findingsList.forEach(f => {
        findingsMap[f.insight_id] = f
      })
      setFindings(findingsMap)
    } catch (error) {
      console.error('Failed to load findings:', error)
    }
  }

  async function handleApplyFilters() {
    setLoading(true)
    try {
      const apiFilters = { ...filters }
      // Remove empty values and placeholder values
      Object.keys(apiFilters).forEach(key => {
        const val = apiFilters[key]
        if (!val || (typeof val === 'string' && val.startsWith('__'))) {
          delete apiFilters[key]
        }
      })
      const data = await getInsights(apiFilters)
      setInsights(data.data?.insights || data.insights || [])
    } catch (error) {
      console.error('Failed to apply filters:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handlePromote(insightId) {
    if (!filters.case_id || filters.case_id === '__none__') {
      alert('Please select a case first to promote insights')
      return
    }

    setPromoting(prev => ({ ...prev, [insightId]: true }))
    try {
      const result = await promoteToFinding(filters.case_id, insightId)
      const finding = result.data || result
      setFindings(prev => ({ ...prev, [insightId]: finding }))
    } catch (error) {
      console.error('Failed to promote insight:', error)
      alert('Failed to promote: ' + error.message)
    } finally {
      setPromoting(prev => ({ ...prev, [insightId]: false }))
    }
  }

  async function handleBulkPromote() {
    if (!filters.case_id || filters.case_id === '__none__') {
      alert('Please select a case first')
      return
    }

    // Get high-quality insights not yet promoted
    const eligibleInsights = insights.filter(i => 
      !findings[i.id] && 
      (i.significance_score >= 7 || i.confidence >= 0.7)
    )

    if (eligibleInsights.length === 0) {
      alert('No eligible insights to promote (need significance ≥7 or confidence ≥0.7)')
      return
    }

    if (!window.confirm(`Promote ${eligibleInsights.length} high-quality insights to findings?`)) {
      return
    }

    setBulkPromoting(true)
    try {
      const insightIds = eligibleInsights.map(i => i.id)
      const result = await autoPromoteFindings(filters.case_id, insightIds, {
        min_confidence: 0.7,
        min_significance: 0.7,
      })
      
      // Reload findings
      await loadFindingsForCase(filters.case_id)
      
      const data = result.data || result
      alert(`Promoted ${data.promoted_count || 0} insights to findings`)
    } catch (error) {
      console.error('Bulk promote failed:', error)
      alert('Bulk promote failed: ' + error.message)
    } finally {
      setBulkPromoting(false)
    }
  }

  // Defensive: ensure insights is always an array
  const safeInsights = Array.isArray(insights) ? insights : []
  const safeCases = Array.isArray(cases) ? cases : []

  const statusCounts = {
    raw: safeInsights.filter(i => i?.status === 'raw').length,
    refined: safeInsights.filter(i => i?.status === 'refined').length,
    surfaced: safeInsights.filter(i => i?.status === 'surfaced').length,
  }

  const selectedCase = safeCases.find(c => c?.id === filters.case_id)
  const promotedCount = Object.keys(findings || {}).length
  const eligibleForPromotion = safeInsights.filter(i =>
    i && !findings?.[i.id] &&
    ((i.significance_score ?? 0) >= 7 || (i.confidence ?? 0) >= 0.7)
  ).length

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Lightbulb className="w-6 h-6 text-orange-light" />
          Insights
        </h2>
        <p className="text-muted-foreground">
          Browse and manage extracted insights from your documents
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <StatGrid>
          <StatCard value={stats.total_insights || stats.total || 0} label="Total Insights" color="primary" />
          <StatCard value={stats.surfaced || 0} label="Surfaced" color="success" />
          <StatCard value={stats.high_significance || 0} label="High Significance" color="secondary" />
          <StatCard value={stats.patterns_generated || 0} label="In Patterns" color="warning" />
        </StatGrid>
      )}

      {/* Case Selection for Findings */}
      <Card className="border-orange-mid/30 bg-orange-mid/5">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-orange-light" />
            Promote to Case Findings
          </CardTitle>
          <CardDescription>
            Select a case to promote insights as verified findings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3 items-end">
            <div className="flex-1 space-y-2">
              <Label>Target Case</Label>
              <Select
                value={filters.case_id}
                onValueChange={(value) => setFilters({...filters, case_id: value})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a case..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No case selected</SelectItem>
                  {cases.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {filters.case_id && filters.case_id !== '__none__' && (
              <Button
                onClick={handleBulkPromote}
                disabled={bulkPromoting || eligibleForPromotion === 0}
                variant="outline"
                className="gap-2"
              >
                {bulkPromoting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Star className="w-4 h-4" />
                )}
                Auto-Promote ({eligibleForPromotion})
              </Button>
            )}
          </div>

          {selectedCase && (
            <div className="mt-3 p-3 bg-background rounded-md border border-border">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm">{selectedCase.title}</div>
                  {selectedCase.context && (
                    <div className="text-xs text-muted-foreground mt-1 line-clamp-1">
                      {selectedCase.context}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-orange-light">{promotedCount} findings</div>
                  <div className="text-xs text-muted-foreground">from this view</div>
                </div>
              </div>
            </div>
          )}
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={filters.status}
                onValueChange={(value) => setFilters({...filters, status: value})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
                  <SelectItem value="raw">Raw</SelectItem>
                  <SelectItem value="refined">Refined</SelectItem>
                  <SelectItem value="surfaced">Surfaced</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Min Significance</Label>
              <Input
                type="number"
                min="0"
                max="10"
                placeholder="0-10"
                value={filters.min_significance}
                onChange={(e) => setFilters({...filters, min_significance: e.target.value})}
              />
            </div>

            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={filters.insight_type}
                onValueChange={(value) => setFilters({...filters, insight_type: value})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
                  <SelectItem value="observation">Observation</SelectItem>
                  <SelectItem value="correlation">Correlation</SelectItem>
                  <SelectItem value="question">Question</SelectItem>
                  <SelectItem value="conclusion">Conclusion</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button onClick={handleApplyFilters} disabled={loading} className="gap-2">
            <Filter className="w-4 h-4" />
            Apply Filters
          </Button>
        </CardContent>
      </Card>

      {/* Insights by Status */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="all">
            All ({safeInsights.length})
          </TabsTrigger>
          <TabsTrigger value="raw">
            Raw ({statusCounts.raw})
          </TabsTrigger>
          <TabsTrigger value="refined">
            Refined ({statusCounts.refined})
          </TabsTrigger>
          <TabsTrigger value="surfaced">
            Surfaced ({statusCounts.surfaced})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-6">
          <InsightsList
            insights={safeInsights}
            loading={loading}
            findings={findings}
            promoting={promoting}
            caseSelected={!!filters.case_id && filters.case_id !== '__none__'}
            onPromote={handlePromote}
            onViewSource={setViewingDoc}
          />
        </TabsContent>
        <TabsContent value="raw" className="mt-6">
          <InsightsList
            insights={safeInsights.filter(i => i?.status === 'raw')}
            loading={loading}
            findings={findings}
            promoting={promoting}
            caseSelected={!!filters.case_id && filters.case_id !== '__none__'}
            onPromote={handlePromote}
            onViewSource={setViewingDoc}
          />
        </TabsContent>
        <TabsContent value="refined" className="mt-6">
          <InsightsList
            insights={safeInsights.filter(i => i?.status === 'refined')}
            loading={loading}
            findings={findings}
            promoting={promoting}
            caseSelected={!!filters.case_id && filters.case_id !== '__none__'}
            onPromote={handlePromote}
            onViewSource={setViewingDoc}
          />
        </TabsContent>
        <TabsContent value="surfaced" className="mt-6">
          <InsightsList
            insights={safeInsights.filter(i => i?.status === 'surfaced')}
            loading={loading}
            findings={findings}
            promoting={promoting}
            caseSelected={!!filters.case_id && filters.case_id !== '__none__'}
            onPromote={handlePromote}
            onViewSource={setViewingDoc}
          />
        </TabsContent>
      </Tabs>

      {/* Document Viewer Modal */}
      <DocumentViewerModal
        documentId={viewingDoc}
        isOpen={!!viewingDoc}
        onClose={() => setViewingDoc(null)}
      />
    </div>
  )
}

function InsightsList({ insights, loading, findings, promoting, caseSelected, onPromote, onViewSource }) {
  // Defensive: ensure props are safe
  const safeInsights = Array.isArray(insights) ? insights : []
  const safeFindings = findings || {}
  const safePromoting = promoting || {}

  function getSignificanceColor(score) {
    const s = score ?? 0
    if (s >= 8) return 'text-orange-light'
    if (s >= 5) return 'text-blue-light'
    return 'text-muted-foreground'
  }

  function getSignificanceBadge(score) {
    const s = score ?? 0
    if (s >= 8) return { label: 'High', color: 'bg-orange-mid/20 text-orange-light border-orange-mid/30' }
    if (s >= 5) return { label: 'Medium', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' }
    return { label: 'Low', color: 'bg-muted text-muted-foreground border-border' }
  }

  if (loading) {
    return (
      <Card>
        <CardContent>
          <LoadingState message="Loading insights..." size="lg" />
        </CardContent>
      </Card>
    )
  }

  if (safeInsights.length === 0) {
    return (
      <Card>
        <CardContent>
          <EmptyState
            icon={Lightbulb}
            title="No insights found"
            description="Try adjusting your filters or upload documents to extract insights."
          />
        </CardContent>
      </Card>
    )
  }

  return (
    <div style={{ height: 'calc(100vh - 420px)', minHeight: '300px' }}>
      <Virtuoso
        data={safeInsights}
        {...VIRTUOSO_CONFIG}
        itemContent={(index, insight) => {
          if (!insight) return null
          const sigBadge = getSignificanceBadge(insight.significance_score)
          const finding = safeFindings[insight.id]
          const isPromoting = safePromoting[insight.id]

          return (
            <div className="pb-3">
              <Card
                className={`
                  hover:bg-muted/30 transition-colors
                  ${finding ? 'border-[#5fb3a1]/50 bg-[#5fb3a1]/5' : ''}
                `}
              >
                <CardContent className="pt-6">
                  <div className="flex items-start gap-4">
                    <div className={`
                      text-3xl font-bold flex-shrink-0 w-12 text-center
                      ${getSignificanceColor(insight.significance_score)}
                    `}>
                      {insight.significance_score}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="text-lg font-semibold line-clamp-2">
                          {insight.title || insight.claim}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Badge variant="outline" className={sigBadge.color}>
                            {sigBadge.label}
                          </Badge>

                          {/* View Source button */}
                          {insight.source_id && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onViewSource(insight.source_id)}
                              className="gap-1 h-7 text-xs"
                            >
                              <FileText className="w-3 h-3" />
                              Source
                            </Button>
                          )}

                          {/* Finding status / Promote button */}
                          {finding ? (
                            <Badge className="bg-[#5fb3a1]/20 text-[#5fb3a1] border-[#5fb3a1]/30 gap-1">
                              <CheckCircle className="w-3 h-3" />
                              {finding.status === 'verified' ? 'Verified' : 'Finding'}
                            </Badge>
                          ) : caseSelected ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => onPromote(insight.id)}
                              disabled={isPromoting}
                              className="gap-1 h-7 text-xs"
                            >
                              {isPromoting ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Star className="w-3 h-3" />
                              )}
                              Promote
                            </Button>
                          ) : null}
                        </div>
                      </div>

                      {insight.excerpt && (
                        <div className="text-sm text-muted-foreground mb-3 line-clamp-3">
                          {insight.excerpt}
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">
                          {insight.insight_type || 'observation'}
                        </Badge>
                        <Badge variant="outline">
                          {insight.status}
                        </Badge>
                        {insight.case_id && (
                          <Badge variant="outline" className="bg-orange-mid/10 border-orange-mid/30">
                            <FolderOpen className="w-3 h-3 mr-1" />
                            In Case
                          </Badge>
                        )}
                        {insight.themes && insight.themes.length > 0 && (
                          insight.themes.slice(0, 3).map((theme, i) => (
                            <Badge key={i} variant="outline" className="bg-blue-500/10">
                              {theme}
                            </Badge>
                          ))
                        )}
                        {insight.entities && insight.entities.length > 0 && (
                          <Badge variant="outline" className="bg-orange-mid/10">
                            {insight.entities.length} entities
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )
        }}
      />
    </div>
  )
}
