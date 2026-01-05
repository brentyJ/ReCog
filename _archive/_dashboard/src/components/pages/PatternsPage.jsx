import { useState, useEffect } from 'react'
import { Waypoints, Play, TrendingUp, Users, Calendar, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { getPatterns, getSynthStats, createClusters, runSynthesis } from '@/lib/api'

export function PatternsPage() {
  const [patterns, setPatterns] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [synthesizing, setSynthesizing] = useState(false)
  const [synthConfig, setSynthConfig] = useState({
    strategy: 'auto',
    min_cluster_size: 3,
  })

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [patternsData, statsData] = await Promise.all([
        getPatterns(),
        getSynthStats(),
      ])
      setPatterns(patternsData.patterns || [])
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load patterns:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleRunSynthesis() {
    if (!window.confirm('Run synthesis on available insights? This will use LLM credits.')) {
      return
    }

    setSynthesizing(true)
    try {
      await runSynthesis(synthConfig)
      alert('Synthesis complete! Patterns updated.')
      await loadData()
    } catch (error) {
      alert(`Synthesis failed: ${error.message}`)
    } finally {
      setSynthesizing(false)
    }
  }

  function getStrengthColor(score) {
    if (score >= 8) return 'bg-orange-light'
    if (score >= 5) return 'bg-blue-light'
    return 'bg-muted-foreground'
  }

  function getStrengthWidth(score) {
    return `${(score / 10) * 100}%`
  }

  const strategyIcons = {
    thematic: Sparkles,
    temporal: Calendar,
    entity: Users,
    auto: Waypoints,
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Waypoints className="w-6 h-6 text-orange-light" />
          Patterns
        </h2>
        <p className="text-muted-foreground">
          Higher-order patterns synthesized from insights
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-orange-light">{stats.total_patterns || 0}</div>
              <div className="text-sm text-muted-foreground">Total Patterns</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-[#5fb3a1]">{stats.validated || 0}</div>
              <div className="text-sm text-muted-foreground">Validated</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-blue-light">{stats.pending_clusters || 0}</div>
              <div className="text-sm text-muted-foreground">Pending Clusters</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-orange-mid">{stats.avg_strength?.toFixed(1) || 0}</div>
              <div className="text-sm text-muted-foreground">Avg Strength</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Synthesis Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="w-5 h-5" />
            Run Synthesis
          </CardTitle>
          <CardDescription>
            Generate new patterns from unprocessed insights
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Clustering Strategy</Label>
              <Select
                value={synthConfig.strategy}
                onValueChange={(value) => setSynthConfig({...synthConfig, strategy: value})}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto (Multi-strategy)</SelectItem>
                  <SelectItem value="thematic">Thematic (By themes)</SelectItem>
                  <SelectItem value="temporal">Temporal (By time)</SelectItem>
                  <SelectItem value="entity">Entity (By people)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Min Cluster Size</Label>
              <Select
                value={synthConfig.min_cluster_size.toString()}
                onValueChange={(value) => setSynthConfig({...synthConfig, min_cluster_size: parseInt(value)})}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="2">2 insights</SelectItem>
                  <SelectItem value="3">3 insights (recommended)</SelectItem>
                  <SelectItem value="5">5 insights</SelectItem>
                  <SelectItem value="7">7 insights</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button 
            onClick={handleRunSynthesis} 
            disabled={synthesizing}
            className="w-full gap-2"
          >
            {synthesizing ? (
              <>
                <Play className="w-4 h-4 animate-pulse" />
                Synthesizing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Synthesis
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Patterns List */}
      <Card>
        <CardHeader>
          <CardTitle>Discovered Patterns</CardTitle>
          <CardDescription>
            {patterns.length} patterns synthesized
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">
              Loading patterns...
            </div>
          ) : patterns.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              No patterns yet. Run synthesis to generate patterns from your insights.
            </div>
          ) : (
            <div className="space-y-4">
              {patterns.map((pattern) => {
                const StrategyIcon = strategyIcons[pattern.cluster_strategy] || Waypoints
                return (
                  <div
                    key={pattern.id}
                    className="p-4 rounded-lg border bg-card hover:bg-muted/30 transition-colors"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex-1">
                        <div className="text-lg font-semibold mb-1">
                          {pattern.title || pattern.description?.substring(0, 100)}
                        </div>
                        {pattern.description && (
                          <div className="text-sm text-muted-foreground line-clamp-2">
                            {pattern.description}
                          </div>
                        )}
                      </div>
                      
                      <Badge variant="outline" className="flex-shrink-0">
                        <StrategyIcon className="w-3 h-3 mr-1" />
                        {pattern.cluster_strategy}
                      </Badge>
                    </div>

                    {/* Strength Bar */}
                    <div className="mb-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-muted-foreground">Strength</span>
                        <span className="text-xs font-mono">{pattern.strength_score}/10</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getStrengthColor(pattern.strength_score)} transition-all`}
                          style={{ width: getStrengthWidth(pattern.strength_score) }}
                        />
                      </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary">
                        {pattern.pattern_type || 'correlation'}
                      </Badge>
                      <Badge variant="outline">
                        {pattern.status || 'pending'}
                      </Badge>
                      {pattern.insight_count && (
                        <Badge variant="outline" className="bg-blue-500/10">
                          {pattern.insight_count} insights
                        </Badge>
                      )}
                      {pattern.entities && pattern.entities.length > 0 && (
                        <Badge variant="outline" className="bg-orange-mid/10">
                          <Users className="w-3 h-3 mr-1" />
                          {pattern.entities.length}
                        </Badge>
                      )}
                      {pattern.timespan && (
                        <Badge variant="outline" className="bg-cyan-500/10">
                          <Calendar className="w-3 h-3 mr-1" />
                          {pattern.timespan}
                        </Badge>
                      )}
                    </div>

                    {/* Themes */}
                    {pattern.themes && pattern.themes.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {pattern.themes.slice(0, 5).map((theme, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {theme}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
