import { useState, useEffect } from 'react'
import { Lightbulb, Filter, TrendingUp, AlertCircle } from 'lucide-react'
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
import { getInsights, getInsightStats } from '@/lib/api'

export function InsightsPage() {
  const [insights, setInsights] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    status: '',
    min_significance: '',
    insight_type: '',
  })
  const [activeTab, setActiveTab] = useState('all')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [insightsData, statsData] = await Promise.all([
        getInsights(filters),
        getInsightStats(),
      ])
      setInsights(insightsData.insights || [])
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load insights:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleApplyFilters() {
    await loadData()
  }

  function getSignificanceColor(score) {
    if (score >= 8) return 'text-orange-light'
    if (score >= 5) return 'text-blue-light'
    return 'text-muted-foreground'
  }

  function getSignificanceBadge(score) {
    if (score >= 8) return { label: 'High', color: 'bg-orange-mid/20 text-orange-light border-orange-mid/30' }
    if (score >= 5) return { label: 'Medium', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' }
    return { label: 'Low', color: 'bg-muted text-muted-foreground border-border' }
  }

  const statusCounts = {
    raw: insights.filter(i => i.status === 'raw').length,
    refined: insights.filter(i => i.status === 'refined').length,
    surfaced: insights.filter(i => i.status === 'surfaced').length,
  }

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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-orange-light">{stats.total_insights}</div>
              <div className="text-sm text-muted-foreground">Total Insights</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-[#5fb3a1]">{stats.surfaced || 0}</div>
              <div className="text-sm text-muted-foreground">Surfaced</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-blue-light">{stats.high_significance || 0}</div>
              <div className="text-sm text-muted-foreground">High Significance</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-orange-mid">{stats.patterns_generated || 0}</div>
              <div className="text-sm text-muted-foreground">In Patterns</div>
            </CardContent>
          </Card>
        </div>
      )}

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
                  <SelectItem value="">All</SelectItem>
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
                  <SelectItem value="">All</SelectItem>
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
            All ({insights.length})
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
          <InsightsList insights={insights} loading={loading} />
        </TabsContent>
        <TabsContent value="raw" className="mt-6">
          <InsightsList 
            insights={insights.filter(i => i.status === 'raw')} 
            loading={loading} 
          />
        </TabsContent>
        <TabsContent value="refined" className="mt-6">
          <InsightsList 
            insights={insights.filter(i => i.status === 'refined')} 
            loading={loading} 
          />
        </TabsContent>
        <TabsContent value="surfaced" className="mt-6">
          <InsightsList 
            insights={insights.filter(i => i.status === 'surfaced')} 
            loading={loading} 
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function InsightsList({ insights, loading }) {
  function getSignificanceColor(score) {
    if (score >= 8) return 'text-orange-light'
    if (score >= 5) return 'text-blue-light'
    return 'text-muted-foreground'
  }

  function getSignificanceBadge(score) {
    if (score >= 8) return { label: 'High', color: 'bg-orange-mid/20 text-orange-light border-orange-mid/30' }
    if (score >= 5) return { label: 'Medium', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' }
    return { label: 'Low', color: 'bg-muted text-muted-foreground border-border' }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-12 pb-12 text-center text-muted-foreground">
          Loading insights...
        </CardContent>
      </Card>
    )
  }

  if (insights.length === 0) {
    return (
      <Card>
        <CardContent className="pt-12 pb-12 text-center text-muted-foreground">
          No insights found
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {insights.map((insight) => {
        const sigBadge = getSignificanceBadge(insight.significance_score)
        return (
          <Card key={insight.id} className="hover:bg-muted/30 transition-colors">
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
                    <Badge variant="outline" className={sigBadge.color}>
                      {sigBadge.label}
                    </Badge>
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
        )
      })}
    </div>
  )
}
