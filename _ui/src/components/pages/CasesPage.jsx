import { useState, useEffect } from 'react'
import {
  Plus,
  FolderOpen,
  FileText,
  Lightbulb,
  Clock,
  ChevronRight,
  Trash2,
  MoreVertical,
  Target,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react'
import { LoadingState } from '@/components/ui/loading-state'
import { EmptyState } from '@/components/ui/empty-state'
import { StatusBadge } from '@/components/ui/status-badge'
import { getCases, createCase, deleteCase, getCaseTimeline, getCaseFindings, updateFinding } from '../../lib/api'

// Case Card Component
function CaseCard({ caseData, onSelect, onDelete }) {
  const [showMenu, setShowMenu] = useState(false)

  return (
    <div
      className="group relative bg-card border border-border rounded-lg p-5 hover:border-orange-mid/50 transition-all cursor-pointer"
      onClick={() => onSelect(caseData)}
    >
      {/* Status Badge */}
      <div className="absolute top-4 right-4">
        <StatusBadge status={caseData.status} />
      </div>

      {/* Title */}
      <h3 className="text-lg font-semibold text-foreground pr-20 mb-2">
        {caseData.title}
      </h3>

      {/* Context */}
      {caseData.context && (
        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
          {caseData.context}
        </p>
      )}

      {/* Focus Areas */}
      {caseData.focus_areas && caseData.focus_areas.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {caseData.focus_areas.slice(0, 4).map((area, i) => (
            <span 
              key={i}
              className="px-2 py-0.5 bg-orange-mid/10 text-orange-light text-xs rounded border border-orange-mid/20"
            >
              {area}
            </span>
          ))}
          {caseData.focus_areas.length > 4 && (
            <span className="px-2 py-0.5 text-muted-foreground text-xs">
              +{caseData.focus_areas.length - 4} more
            </span>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <FileText className="w-3.5 h-3.5" />
          <span>{caseData.document_count || 0} docs</span>
        </div>
        <div className="flex items-center gap-1">
          <Lightbulb className="w-3.5 h-3.5" />
          <span>{caseData.findings_count || 0} findings</span>
        </div>
        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          <span>{new Date(caseData.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Action Menu */}
      <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation()
            setShowMenu(!showMenu)
          }}
          className="p-1.5 rounded hover:bg-muted transition-colors"
        >
          <MoreVertical className="w-4 h-4 text-muted-foreground" />
        </button>
        
        {showMenu && (
          <div className="absolute right-0 bottom-8 bg-card border border-border rounded-md shadow-lg py-1 min-w-[120px] z-10">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(caseData.id)
                setShowMenu(false)
              }}
              className="w-full px-3 py-1.5 text-left text-sm text-destructive hover:bg-destructive/10 flex items-center gap-2"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Chevron */}
      <ChevronRight className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  )
}

// Create Case Modal
function CreateCaseModal({ isOpen, onClose, onCreate }) {
  const [title, setTitle] = useState('')
  const [context, setContext] = useState('')
  const [focusAreas, setFocusAreas] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim()) return

    setIsSubmitting(true)
    setError(null)

    try {
      const focusAreasArray = focusAreas
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0)

      await onCreate({
        title: title.trim(),
        context: context.trim() || null,
        focus_areas: focusAreasArray.length > 0 ? focusAreasArray : null,
      })

      // Reset form
      setTitle('')
      setContext('')
      setFocusAreas('')
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to create case')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-card border border-border rounded-lg w-full max-w-lg mx-4 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-6 border-b border-border">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-orange-light" />
            Create New Case
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-md text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Case Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Q3 Revenue Investigation"
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-orange-mid/50 focus:border-orange-mid"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Context / Assignment
            </label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="What question are you trying to answer? What's the goal of this investigation?"
              rows={3}
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-orange-mid/50 focus:border-orange-mid resize-none"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              This context will guide the AI's extraction and analysis.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              <Target className="w-4 h-4 inline mr-1" />
              Focus Areas
            </label>
            <input
              type="text"
              value={focusAreas}
              onChange={(e) => setFocusAreas(e.target.value)}
              placeholder="pricing, competition, customer churn"
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-orange-mid/50 focus:border-orange-mid"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Comma-separated topics to prioritize during analysis.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || isSubmitting}
              className="px-4 py-2 bg-orange-mid text-background rounded-md text-sm font-medium hover:bg-orange-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-background/30 border-t-background rounded-full animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Create Case
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Case Detail View
function CaseDetail({ caseData, onBack }) {
  const [timeline, setTimeline] = useState([])
  const [findings, setFindings] = useState([])
  const [loadingTimeline, setLoadingTimeline] = useState(true)
  const [loadingFindings, setLoadingFindings] = useState(true)
  const [updatingFinding, setUpdatingFinding] = useState({})
  const [activeTab, setActiveTab] = useState('findings')

  useEffect(() => {
    loadTimeline()
    loadFindings()
  }, [caseData.id])

  async function loadTimeline() {
    try {
      const response = await getCaseTimeline(caseData.id)
      setTimeline(response.data?.events || [])
    } catch (err) {
      console.error('Failed to load timeline:', err)
    } finally {
      setLoadingTimeline(false)
    }
  }

  async function loadFindings() {
    try {
      const response = await getCaseFindings(caseData.id)
      setFindings(response.data?.findings || [])
    } catch (err) {
      console.error('Failed to load findings:', err)
    } finally {
      setLoadingFindings(false)
    }
  }

  async function handleUpdateFindingStatus(findingId, newStatus) {
    setUpdatingFinding(prev => ({ ...prev, [findingId]: true }))
    try {
      await updateFinding(findingId, { status: newStatus })
      setFindings(prev => prev.map(f =>
        f.id === findingId ? { ...f, status: newStatus } : f
      ))
    } catch (err) {
      console.error('Failed to update finding:', err)
      alert('Failed to update finding: ' + err.message)
    } finally {
      setUpdatingFinding(prev => ({ ...prev, [findingId]: false }))
    }
  }

  const eventIcons = {
    case_created: FolderOpen,
    doc_added: FileText,
    insights_extracted: Lightbulb,
    finding_verified: Target,
    finding_added: Lightbulb,
  }

  const verifiedCount = findings.filter(f => f.status === 'verified').length
  const needsVerificationCount = findings.filter(f => f.status === 'needs_verification').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={onBack}
            className="text-sm text-muted-foreground hover:text-foreground mb-2 flex items-center gap-1"
          >
            ← Back to Cases
          </button>
          <h2 className="text-2xl font-bold text-foreground">{caseData.title}</h2>
          {caseData.context && (
            <p className="text-muted-foreground mt-1">{caseData.context}</p>
          )}
        </div>
        <span className={`px-3 py-1 rounded text-sm font-medium ${
          caseData.status === 'active'
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-zinc-500/20 text-zinc-400'
        }`}>
          {caseData.status}
        </span>
      </div>

      {/* Focus Areas */}
      {caseData.focus_areas && caseData.focus_areas.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {caseData.focus_areas.map((area, i) => (
            <span
              key={i}
              className="px-3 py-1 bg-orange-mid/10 text-orange-light text-sm rounded-full border border-orange-mid/20"
            >
              {area}
            </span>
          ))}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-3xl font-bold text-foreground">{caseData.document_count || 0}</div>
          <div className="text-sm text-muted-foreground">Documents</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-3xl font-bold text-foreground">{findings.length}</div>
          <div className="text-sm text-muted-foreground">Findings</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-3xl font-bold text-emerald-400">{verifiedCount}</div>
          <div className="text-sm text-muted-foreground">Verified</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-3xl font-bold text-amber-400">{needsVerificationCount}</div>
          <div className="text-sm text-muted-foreground">To Review</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        <button
          onClick={() => setActiveTab('findings')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'findings'
              ? 'border-orange-light text-orange-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Lightbulb className="w-4 h-4 inline mr-2" />
          Findings ({findings.length})
        </button>
        <button
          onClick={() => setActiveTab('timeline')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'timeline'
              ? 'border-orange-light text-orange-light'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Clock className="w-4 h-4 inline mr-2" />
          Timeline ({timeline.length})
        </button>
      </div>

      {/* Findings Tab */}
      {activeTab === 'findings' && (
        <div className="bg-card border border-border rounded-lg p-6">
          {loadingFindings ? (
            <LoadingState message="Loading findings..." />
          ) : findings.length === 0 ? (
            <EmptyState
              icon={Lightbulb}
              title="No findings yet"
              description="Upload documents and extract insights, then promote them to findings."
            />
          ) : (
            <div className="space-y-3">
              {findings.map((finding) => (
                <div
                  key={finding.id}
                  className={`p-4 rounded-lg border transition-all ${
                    finding.status === 'verified'
                      ? 'border-emerald-500/30 bg-emerald-500/5'
                      : finding.status === 'rejected'
                      ? 'border-red-500/30 bg-red-500/5 opacity-60'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="font-medium text-foreground">
                          {finding.insight?.title || finding.insight?.claim || 'Untitled Finding'}
                        </div>
                        <StatusBadge status={finding.status} />
                      </div>

                      {finding.insight?.excerpt && (
                        <div className="text-sm text-muted-foreground mb-3 line-clamp-2">
                          {finding.insight.excerpt}
                        </div>
                      )}

                      {finding.tags && finding.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-3">
                          {finding.tags.map((tag, i) => (
                            <span key={i} className="px-2 py-0.5 bg-muted text-xs rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}

                      {finding.user_notes && (
                        <div className="text-sm text-orange-light italic mb-3">
                          Note: {finding.user_notes}
                        </div>
                      )}

                      <div className="flex items-center justify-between">
                        <div className="text-xs text-muted-foreground">
                          Added {new Date(finding.created_at).toLocaleDateString()}
                          {finding.verified_at && (
                            <> • Verified {new Date(finding.verified_at).toLocaleDateString()}</>
                          )}
                        </div>

                        {finding.status !== 'rejected' && (
                          <div className="flex gap-2">
                            {finding.status !== 'verified' && (
                              <button
                                onClick={() => handleUpdateFindingStatus(finding.id, 'verified')}
                                disabled={updatingFinding[finding.id]}
                                className="px-3 py-1 text-xs bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30 transition-colors flex items-center gap-1 disabled:opacity-50"
                              >
                                {updatingFinding[finding.id] ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <CheckCircle className="w-3 h-3" />
                                )}
                                Verify
                              </button>
                            )}
                            <button
                              onClick={() => handleUpdateFindingStatus(finding.id, 'rejected')}
                              disabled={updatingFinding[finding.id]}
                              className="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors flex items-center gap-1 disabled:opacity-50"
                            >
                              <XCircle className="w-3 h-3" />
                              Reject
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Timeline Tab */}
      {activeTab === 'timeline' && (
        <div className="bg-card border border-border rounded-lg p-6">
          {loadingTimeline ? (
            <LoadingState message="Loading timeline..." />
          ) : timeline.length === 0 ? (
            <EmptyState
              icon={Clock}
              title="No events yet"
              description="Timeline events will appear as you work with this case."
            />
          ) : (
            <div className="space-y-4">
              {timeline.map((event) => {
                const Icon = eventIcons[event.event_type] || Clock
                return (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex-shrink-0 w-8 h-8 bg-orange-mid/10 rounded-full flex items-center justify-center">
                      <Icon className="w-4 h-4 text-orange-light" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground">{event.description}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(event.timestamp).toLocaleString()}
                      </div>
                      {event.human_annotation && (
                        <div className="mt-1 text-xs text-orange-light italic">
                          Note: {event.human_annotation}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Main Cases Page
export function CasesPage() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedCase, setSelectedCase] = useState(null)
  const [filter, setFilter] = useState('active')

  const loadCases = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getCases({ status: filter !== 'all' ? filter : undefined })
      setCases(response.data?.cases || [])
    } catch (err) {
      setError(err.message || 'Failed to load cases')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCases()
  }, [filter])

  const handleCreateCase = async (data) => {
    const response = await createCase(data)
    setCases(prev => [response.data, ...prev])
  }

  const handleDeleteCase = async (caseId) => {
    if (!confirm('Are you sure you want to delete this case? This cannot be undone.')) {
      return
    }
    try {
      await deleteCase(caseId)
      setCases(prev => prev.filter(c => c.id !== caseId))
    } catch (err) {
      alert('Failed to delete case: ' + err.message)
    }
  }

  // Detail View
  if (selectedCase) {
    return (
      <CaseDetail 
        caseData={selectedCase} 
        onBack={() => setSelectedCase(null)} 
      />
    )
  }

  // List View
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Cases</h2>
          <p className="text-muted-foreground">Organize your document intelligence investigations</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-orange-mid text-background rounded-md text-sm font-medium hover:bg-orange-light transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Case
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {['active', 'archived', 'all'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              filter === f
                ? 'bg-orange-mid/15 text-orange-light border border-orange-mid/30'
                : 'text-muted-foreground hover:text-foreground border border-transparent'
            }`}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-md text-destructive">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <LoadingState message="Loading cases..." size="lg" />
      )}

      {/* Empty State */}
      {!loading && cases.length === 0 && (
        <EmptyState
          icon={FolderOpen}
          title="No cases yet"
          description="Create a case to start organizing your document analysis"
          variant="dashed"
          action={
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-orange-mid text-background rounded-md text-sm font-medium hover:bg-orange-light transition-colors inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Your First Case
            </button>
          }
        />
      )}

      {/* Case Grid */}
      {!loading && cases.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <CaseCard
              key={c.id}
              caseData={c}
              onSelect={setSelectedCase}
              onDelete={handleDeleteCase}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      <CreateCaseModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateCase}
      />
    </div>
  )
}
