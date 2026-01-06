import { useState, useEffect } from 'react'
import {
  Activity,
  Lightbulb,
  Users,
  Waypoints,
  FileText,
  TrendingUp,
  BarChart3,
  Calendar,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState } from '@/components/ui/loading-state'
import { StatCard, StatGrid } from '@/components/ui/stat-card'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import {
  getInsightStats,
  getInsightActivity,
  getEntityStats,
  getSynthStats,
  getCases,
} from '@/lib/api'

// ReCog color palette
const COLORS = {
  primary: '#ff6b35',
  secondary: '#5fb3a1',
  accent: '#4a90d9',
  muted: '#6b7280',
  warning: '#f59e0b',
  success: '#10b981',
}

const PIE_COLORS = ['#ff6b35', '#5fb3a1', '#4a90d9', '#f59e0b', '#10b981', '#8b5cf6']

export function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    insights: null,
    entities: null,
    synth: null,
    cases: [],
    activity: [],
  })

  useEffect(() => {
    loadStats()
  }, [])

  async function loadStats() {
    setLoading(true)
    try {
      const [insightStats, entityStats, synthStats, casesData, activityData] = await Promise.all([
        getInsightStats().catch(() => null),
        getEntityStats().catch(() => null),
        getSynthStats().catch(() => null),
        getCases().catch(() => ({ data: { cases: [] } })),
        getInsightActivity(30).catch(() => ({ data: { activity: [] } })),
      ])
      setStats({
        insights: insightStats?.data || insightStats,
        entities: entityStats?.data || entityStats,
        synth: synthStats?.data || synthStats,
        cases: casesData?.data?.cases || casesData?.cases || [],
        activity: activityData?.data?.activity || activityData?.activity || [],
      })
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <LoadingState message="Loading dashboard..." size="lg" />
  }

  // Prepare chart data
  const insightTypeData = prepareInsightTypeData(stats.insights)
  const insightActivityData = prepareActivityData(stats.activity)
  const entityTypeData = prepareEntityTypeData(stats.entities)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Activity className="w-6 h-6 text-orange-light" />
          Dashboard
        </h2>
        <p className="text-muted-foreground">
          Overview of your ReCog analysis data
        </p>
      </div>

      {/* Top Stats */}
      <StatGrid columns={4}>
        <StatCard
          value={stats.insights?.total || 0}
          label="Total Insights"
          color="primary"
          icon={Lightbulb}
        />
        <StatCard
          value={stats.entities?.total?.total || 0}
          label="Entities"
          color="secondary"
          icon={Users}
        />
        <StatCard
          value={stats.synth?.total_patterns || 0}
          label="Patterns"
          color="warning"
          icon={Waypoints}
        />
        <StatCard
          value={stats.cases?.length || 0}
          label="Active Cases"
          color="success"
          icon={FileText}
        />
      </StatGrid>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Insights by Type */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="w-4 h-4 text-orange-light" />
              Insights by Type
            </CardTitle>
            <CardDescription>Distribution of insight categories</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {insightTypeData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={insightTypeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} />
                    <YAxis stroke="#9ca3af" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: '#e5e7eb' }}
                    />
                    <Bar dataKey="value" fill={COLORS.primary} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <ChartPlaceholder message="Extract insights to see type distribution" />
              )}
            </div>
          </CardContent>
        </Card>

        {/* Entity Types */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="w-4 h-4 text-orange-light" />
              Entity Types
            </CardTitle>
            <CardDescription>Breakdown of detected entities</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {entityTypeData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={entityTypeData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) =>
                        `${name} (${(percent * 100).toFixed(0)}%)`
                      }
                      outerRadius={80}
                      dataKey="value"
                    >
                      {entityTypeData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={PIE_COLORS[index % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                      }}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <ChartPlaceholder message="Process documents to see entity breakdown" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 gap-6">
        {/* Activity Over Time */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="w-4 h-4 text-orange-light" />
              Activity Over Time
            </CardTitle>
            <CardDescription>Insights extracted over the past 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {insightActivityData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={insightActivityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} />
                    <YAxis stroke="#9ca3af" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: '#e5e7eb' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="insights"
                      stroke={COLORS.primary}
                      fill={COLORS.primary}
                      fillOpacity={0.3}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <ChartPlaceholder message="Activity data will appear as you process documents" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Cases */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="w-4 h-4 text-orange-light" />
            Recent Cases
          </CardTitle>
          <CardDescription>Your latest investigation cases</CardDescription>
        </CardHeader>
        <CardContent>
          {stats.cases.length > 0 ? (
            <div className="space-y-3">
              {stats.cases.slice(0, 5).map((caseItem) => (
                <div
                  key={caseItem.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-orange-light" />
                    <div>
                      <div className="font-medium">{caseItem.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {caseItem.status || 'Active'}
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {caseItem.insight_count || 0} insights
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="w-10 h-10 mx-auto mb-3 opacity-50" />
              <p>No cases yet. Create a case to start your investigation.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// Chart placeholder for empty state
function ChartPlaceholder({ message }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
      <BarChart3 className="w-12 h-12 mb-3 opacity-30" />
      <p className="text-sm text-center">{message}</p>
    </div>
  )
}

// Data preparation helpers
function prepareInsightTypeData(stats) {
  if (!stats?.by_type) return []
  return Object.entries(stats.by_type).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }))
}

function prepareActivityData(activity) {
  if (!activity || activity.length === 0) return []

  // Format dates for display and ensure data is sorted
  return activity.map(item => ({
    date: formatDateShort(item.date),
    insights: item.count,
  }))
}

function formatDateShort(dateStr) {
  // Convert "2026-01-06" to "Jan 6"
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function prepareEntityTypeData(stats) {
  if (!stats) return []
  // Entity stats structure: { person: { total: X }, email: { total: Y }, ... }
  const types = ['person', 'email', 'phone', 'organisation']
  const data = []
  for (const type of types) {
    if (stats[type]?.total > 0) {
      data.push({
        name: type.charAt(0).toUpperCase() + type.slice(1),
        value: stats[type].total,
      })
    }
  }
  return data
}
