import { useState, useEffect } from 'react'
import { Users, Search, Check, X, Trash2, RefreshCw, Filter } from 'lucide-react'

const STATUS_STYLES = {
  CONFIRMED: 'status-confirmed',
  PENDING: 'status-pending',
  UNKNOWN: 'status-unknown',
}

const ENTITY_TYPES = ['ALL', 'PERSON', 'DATE', 'MONEY', 'LOCATION', 'EMAIL', 'PHONE', 'URL']

export default function EntityRegistry() {
  const [entities, setEntities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const fetchEntities = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const res = await fetch('/api/entities')
      const data = await res.json()
      
      if (data.success) {
        setEntities(data.entities || [])
      } else {
        setError(data.error || 'Failed to load entities')
      }
    } catch (err) {
      setError(`Connection error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEntities()
  }, [])

  const handleConfirm = async (entityId) => {
    try {
      const res = await fetch('/api/entities/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: entityId }),
      })
      
      const data = await res.json()
      if (data.success) {
        fetchEntities() // Refresh list
      }
    } catch (err) {
      console.error('Failed to confirm entity:', err)
    }
  }

  const handleDelete = async (entityId) => {
    if (!confirm('Delete this entity? This cannot be undone.')) return
    
    try {
      const res = await fetch(`/api/entities/${entityId}`, {
        method: 'DELETE',
      })
      
      const data = await res.json()
      if (data.success) {
        fetchEntities() // Refresh list
      }
    } catch (err) {
      console.error('Failed to delete entity:', err)
    }
  }

  // Filter entities
  const filteredEntities = entities.filter((entity) => {
    const matchesSearch = entity.value.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         entity.type.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesType = typeFilter === 'ALL' || entity.type === typeFilter
    const matchesStatus = statusFilter === 'ALL' || 
                         (statusFilter === 'CONFIRMED' && entity.confirmed) ||
                         (statusFilter === 'PENDING' && !entity.confirmed)
    
    return matchesSearch && matchesType && matchesStatus
  })

  // Stats
  const stats = {
    total: entities.length,
    confirmed: entities.filter(e => e.confirmed).length,
    pending: entities.filter(e => !e.confirmed).length,
    types: [...new Set(entities.map(e => e.type))].length,
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Users className="w-6 h-6 text-primary" />
            Entity Registry
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage and confirm extracted entities
          </p>
        </div>
        <button
          onClick={fetchEntities}
          disabled={loading}
          className="px-4 py-2 bg-secondary border border-border rounded-md text-sm font-medium hover:bg-secondary/80 disabled:opacity-50 flex items-center gap-2 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="recog-card">
          <div className="text-3xl font-bold text-foreground font-mono">
            {stats.total}
          </div>
          <div className="text-sm text-muted-foreground mt-1">Total Entities</div>
        </div>
        <div className="recog-card">
          <div className="text-3xl font-bold text-success font-mono">
            {stats.confirmed}
          </div>
          <div className="text-sm text-muted-foreground mt-1">Confirmed</div>
        </div>
        <div className="recog-card">
          <div className="text-3xl font-bold text-warning font-mono">
            {stats.pending}
          </div>
          <div className="text-sm text-muted-foreground mt-1">Pending</div>
        </div>
        <div className="recog-card">
          <div className="text-3xl font-bold text-primary font-mono">
            {stats.types}
          </div>
          <div className="text-sm text-muted-foreground mt-1">Entity Types</div>
        </div>
      </div>

      {/* Filters */}
      <div className="recog-card">
        <div className="flex items-center gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search entities..."
              className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {ENTITY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type === 'ALL' ? 'All Types' : type}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="ALL">All Status</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="PENDING">Pending</option>
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-md">
          <p className="text-destructive text-sm font-mono">{error}</p>
        </div>
      )}

      {/* Entity Table */}
      {loading ? (
        <div className="recog-card flex items-center justify-center py-12">
          <RefreshCw className="w-6 h-6 text-primary animate-spin" />
          <span className="ml-3 text-muted-foreground">Loading entities...</span>
        </div>
      ) : filteredEntities.length === 0 ? (
        <div className="recog-card text-center py-12">
          <Users className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">
            {entities.length === 0 ? 'No entities found' : 'No entities match your filters'}
          </p>
        </div>
      ) : (
        <div className="recog-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Type</th>
                  <th>Context</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntities.map((entity) => (
                  <tr key={entity.id}>
                    <td>
                      <div className="font-mono font-medium text-foreground">
                        {entity.value}
                      </div>
                    </td>
                    <td>
                      <div className="inline-flex px-2 py-1 rounded-md bg-secondary text-xs font-medium text-muted-foreground border border-border">
                        {entity.type}
                      </div>
                    </td>
                    <td>
                      <div className="text-muted-foreground text-xs max-w-xs truncate">
                        {entity.context || '—'}
                      </div>
                    </td>
                    <td>
                      <div className="font-mono text-sm text-muted-foreground">
                        {entity.confidence ? `${(entity.confidence * 100).toFixed(0)}%` : '—'}
                      </div>
                    </td>
                    <td>
                      <span className={`inline-flex px-2 py-1 rounded-md text-xs font-medium ${
                        entity.confirmed ? 'status-confirmed' : 'status-pending'
                      }`}>
                        {entity.confirmed ? 'CONFIRMED' : 'PENDING'}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-2">
                        {!entity.confirmed && (
                          <button
                            onClick={() => handleConfirm(entity.id)}
                            className="p-1.5 hover:bg-success/10 rounded-md text-success transition-colors"
                            title="Confirm entity"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(entity.id)}
                          className="p-1.5 hover:bg-destructive/10 rounded-md text-destructive transition-colors"
                          title="Delete entity"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Results count */}
          <div className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
            Showing {filteredEntities.length} of {entities.length} entities
          </div>
        </div>
      )}
    </div>
  )
}
