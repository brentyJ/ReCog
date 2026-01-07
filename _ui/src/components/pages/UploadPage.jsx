import { useState, useRef, useEffect, useMemo } from 'react'
import { FileUp, Upload, File, CheckCircle, AlertCircle, Loader2, FolderOpen, Plus, Check, CheckSquare, Square, Trash2, ChevronDown, ChevronRight, Package } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { uploadFile, uploadFilesBatch, detectFileFormat, getCases, createCase } from '@/lib/api'

export function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState(() => {
    // Restore files from localStorage on mount
    const saved = localStorage.getItem('upload_files')
    return saved ? JSON.parse(saved) : []
  })
  const [uploading, setUploading] = useState(false)
  const [cases, setCases] = useState([])
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [loadingCases, setLoadingCases] = useState(true)
  const [showQuickCreate, setShowQuickCreate] = useState(false)
  const [quickCaseTitle, setQuickCaseTitle] = useState('')
  const [creatingCase, setCreatingCase] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState(new Set())
  const [expandedSessions, setExpandedSessions] = useState(new Set())
  const [inputKey, setInputKey] = useState(0)
  const fileInputRef = useRef(null)

  // Group files by session for display
  const groupedUploads = useMemo(() => {
    const groups = []
    const sessionMap = new Map()

    for (const file of files) {
      if (!file.sessionId) {
        // Files without sessionId (errors) shown individually
        groups.push({ type: 'single', file })
        continue
      }

      if (!sessionMap.has(file.sessionId)) {
        sessionMap.set(file.sessionId, { batch: null, children: [] })
      }
      const group = sessionMap.get(file.sessionId)

      if (file.isBatch) {
        group.batch = file
      } else {
        group.children.push(file)
      }
    }

    // Convert session groups to display items
    for (const [sessionId, group] of sessionMap) {
      if (group.batch) {
        // Batch upload - show as collapsible group
        groups.push({
          type: 'batch',
          sessionId,
          batch: group.batch,
          children: group.children,
        })
      } else if (group.children.length === 1) {
        // Single file upload
        groups.push({ type: 'single', file: group.children[0] })
      } else {
        // Multiple files without batch header (shouldn't happen, but handle it)
        for (const file of group.children) {
          groups.push({ type: 'single', file })
        }
      }
    }

    return groups
  }, [files])

  // Get unique session IDs for selection
  const uniqueSessionIds = useMemo(() => {
    const ids = new Set()
    for (const group of groupedUploads) {
      if (group.type === 'batch' && group.batch.status === 'success') {
        ids.add(group.sessionId)
      } else if (group.type === 'single' && group.file.status === 'success' && group.file.sessionId) {
        ids.add(group.file.sessionId)
      }
    }
    return ids
  }, [groupedUploads])

  const allSelected = uniqueSessionIds.size > 0 && [...uniqueSessionIds].every(id => selectedFiles.has(id))
  const someSelected = selectedFiles.size > 0

  function toggleSessionExpanded(sessionId) {
    setExpandedSessions(prev => {
      const next = new Set(prev)
      if (next.has(sessionId)) {
        next.delete(sessionId)
      } else {
        next.add(sessionId)
      }
      return next
    })
  }

  function toggleFileSelection(sessionId) {
    setSelectedFiles(prev => {
      const next = new Set(prev)
      if (next.has(sessionId)) {
        next.delete(sessionId)
      } else {
        next.add(sessionId)
      }
      return next
    })
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedFiles(new Set())
    } else {
      setSelectedFiles(new Set(uniqueSessionIds))
    }
  }

  function handleReviewSelected() {
    const selectedList = Array.from(selectedFiles)
    if (selectedList.length === 0) return

    // Store all selected sessions for multi-session review
    localStorage.setItem('preflight_sessions', JSON.stringify(selectedList))
    localStorage.setItem('current_preflight_session', selectedList[0])

    // Store case IDs if any
    for (const file of files) {
      if (selectedFiles.has(file.sessionId) && file.caseId) {
        sessionStorage.setItem(`preflight_case_${file.sessionId}`, file.caseId)
      }
    }

    window.location.hash = `preflight/${selectedList[0]}`
  }

  function clearUploads() {
    setFiles([])
    setSelectedFiles(new Set())
    setExpandedSessions(new Set())
    setInputKey(k => k + 1)  // Force file input to remount
    localStorage.removeItem('upload_files')
  }

  // Persist files to localStorage when they change
  useEffect(() => {
    localStorage.setItem('upload_files', JSON.stringify(files))
  }, [files])

  // Sync with localStorage when page becomes visible or storage changes
  useEffect(() => {
    function syncFromLocalStorage() {
      const saved = localStorage.getItem('upload_files')
      const parsed = saved ? JSON.parse(saved) : []
      // Always set from localStorage - React will skip if unchanged
      setFiles(parsed)
    }

    // Listen for storage events (from other tabs/pages)
    function handleStorageChange(e) {
      if (e.key === 'upload_files') {
        syncFromLocalStorage()
      }
    }

    // Sync when page becomes visible (user navigates back)
    function handleVisibilityChange() {
      if (document.visibilityState === 'visible') {
        syncFromLocalStorage()
      }
    }

    // Sync when hash changes (user navigates via hash)
    function handleHashChange() {
      if (window.location.hash === '#upload' || window.location.hash === '') {
        // Small delay to ensure localStorage is updated first
        setTimeout(syncFromLocalStorage, 50)
      }
    }

    window.addEventListener('storage', handleStorageChange)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('hashchange', handleHashChange)

    // Also sync on mount (in case localStorage was modified while unmounted)
    syncFromLocalStorage()

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('hashchange', handleHashChange)
    }
  }, []) // Empty deps - we want this to run once and set up listeners

  // Load cases on mount
  useEffect(() => {
    async function loadCases() {
      try {
        const response = await getCases({ status: 'active' })
        setCases(response.data?.cases || [])
      } catch (err) {
        console.error('Failed to load cases:', err)
      } finally {
        setLoadingCases(false)
      }
    }
    loadCases()
  }, [])

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setDragging(false)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    setDragging(false)
    
    const droppedFiles = Array.from(e.dataTransfer.files)
    await processFiles(droppedFiles)
  }

  const handleFileSelect = async (e) => {
    const selectedFiles = Array.from(e.target.files)
    if (selectedFiles.length === 0) return
    await processFiles(selectedFiles)
    // Reset input so same files can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  async function processFiles(fileList) {
    setUploading(true)

    try {
      // Use batch upload to create ONE session for all files
      const upload = await uploadFilesBatch(fileList, selectedCaseId || null)
      const uploadData = upload.data || upload

      // Create file entries for each uploaded file
      const newFiles = []
      const fileResults = uploadData.file_results || []

      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i]
        const result = fileResults[i] || {}

        newFiles.push({
          name: file.name,
          size: file.size,
          type: file.type,
          format: result.supported ? 'supported' : 'unsupported',
          // All files share the same session ID
          sessionId: uploadData.preflight_session_id,
          caseId: selectedCaseId || null,
          status: result.supported !== false ? 'success' : 'error',
          items: result.items || 0,
          words: 0, // Not tracked per-file in batch
          error: result.error || result.message,
        })
      }

      // Add a summary entry for the batch
      if (fileList.length > 1) {
        newFiles.unshift({
          name: `Batch Upload (${fileList.length} files)`,
          size: fileList.reduce((sum, f) => sum + f.size, 0),
          type: 'batch',
          format: 'batch',
          sessionId: uploadData.preflight_session_id,
          caseId: selectedCaseId || null,
          status: 'success',
          items: uploadData.items || 0,
          words: uploadData.words || 0,
          isBatch: true,
        })
      }

      setFiles(prev => [...prev, ...newFiles])
    } catch (error) {
      // If batch upload fails, add error entries for all files
      const newFiles = fileList.map(file => ({
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'error',
        error: error.message,
      }))
      setFiles(prev => [...prev, ...newFiles])
    }

    setUploading(false)
  }

  async function handleQuickCreateCase() {
    if (!quickCaseTitle.trim()) return
    
    setCreatingCase(true)
    try {
      const response = await createCase({ title: quickCaseTitle.trim() })
      const newCase = response.data
      setCases(prev => [newCase, ...prev])
      setSelectedCaseId(newCase.id)
      setQuickCaseTitle('')
      setShowQuickCreate(false)
    } catch (err) {
      console.error('Failed to create case:', err)
      alert('Failed to create case: ' + err.message)
    } finally {
      setCreatingCase(false)
    }
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const selectedCase = cases.find(c => c.id === selectedCaseId)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <FileUp className="w-6 h-6 text-orange-light" />
          Upload Files
        </h2>
        <p className="text-muted-foreground">
          Upload documents for batch processing. Supported: text, PDF, Excel, email, chat exports.
        </p>
      </div>

      {/* Case Selector */}
      <Card className="border-orange-mid/30 bg-orange-mid/5">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-orange-light" />
            Assign to Case (Optional)
          </CardTitle>
          <CardDescription>
            Link documents to a case for context-aware extraction
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              disabled={loadingCases}
              className="flex-1 px-3 py-2 bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-orange-mid/50 focus:border-orange-mid"
            >
              <option value="">No case (standalone upload)</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
            
            <Button
              variant="outline"
              size="icon"
              onClick={() => setShowQuickCreate(!showQuickCreate)}
              title="Create new case"
            >
              <Plus className="w-4 h-4" />
            </Button>
          </div>

          {/* Quick Create Case */}
          {showQuickCreate && (
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                value={quickCaseTitle}
                onChange={(e) => setQuickCaseTitle(e.target.value)}
                placeholder="New case title..."
                className="flex-1 px-3 py-2 bg-background border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-orange-mid/50"
                onKeyDown={(e) => e.key === 'Enter' && handleQuickCreateCase()}
              />
              <Button
                onClick={handleQuickCreateCase}
                disabled={!quickCaseTitle.trim() || creatingCase}
                size="sm"
              >
                {creatingCase ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Create'
                )}
              </Button>
            </div>
          )}

          {/* Selected Case Info */}
          {selectedCase && (
            <div className="mt-3 p-3 bg-background rounded-md border border-border">
              <div className="font-medium text-sm">{selectedCase.title}</div>
              {selectedCase.context && (
                <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {selectedCase.context}
                </div>
              )}
              {selectedCase.focus_areas?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {selectedCase.focus_areas.map((area, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {area}
                    </Badge>
                  ))}
                </div>
              )}
              <div className="text-xs text-muted-foreground mt-2">
                {selectedCase.document_count || 0} docs • {selectedCase.findings_count || 0} findings
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Drop Zone */}
      <Card
        className={`border-2 border-dashed transition-colors ${
          dragging 
            ? 'border-orange-light bg-orange-mid/5' 
            : 'border-border hover:border-orange-mid/50'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <CardContent className="pt-12 pb-12">
          <div className="flex flex-col items-center gap-4 text-center">
            <div className={`
              w-16 h-16 rounded-full flex items-center justify-center
              ${dragging ? 'bg-orange-mid/20' : 'bg-muted'}
            `}>
              <Upload className={`w-8 h-8 ${dragging ? 'text-orange-light' : 'text-muted-foreground'}`} />
            </div>
            
            <div>
              <div className="text-lg font-semibold mb-1">
                {dragging ? 'Drop files here' : 'Drag & drop files here'}
              </div>
              <div className="text-sm text-muted-foreground">
                or click to browse
              </div>
              {selectedCase && (
                <div className="text-sm text-orange-light mt-2">
                  → Will be added to "{selectedCase.title}"
                </div>
              )}
            </div>

            <Button 
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <File className="w-4 h-4" />
                  Select Files
                </>
              )}
            </Button>

            <input
              key={inputKey}
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileSelect}
              accept=".txt,.md,.json,.pdf,.csv,.xlsx,.xls,.xlsm,.eml,.msg"
            />

            <div className="text-xs text-muted-foreground">
              Supported: TXT, MD, JSON, PDF, CSV, Excel, Email, Chat exports
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Uploaded Files */}
      {groupedUploads.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle>Uploaded Files</CardTitle>
                <CardDescription>
                  {uniqueSessionIds.size} session{uniqueSessionIds.size !== 1 ? 's' : ''} ready for review
                  {someSelected && ` • ${selectedFiles.size} selected`}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                {uniqueSessionIds.size > 0 && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleSelectAll}
                      className="gap-1.5"
                    >
                      {allSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                      {allSelected ? 'Deselect All' : 'Select All'}
                    </Button>
                    {someSelected && (
                      <Button
                        size="sm"
                        onClick={handleReviewSelected}
                        className="gap-1.5"
                      >
                        <CheckCircle className="w-4 h-4" />
                        Review Selected ({selectedFiles.size})
                      </Button>
                    )}
                  </>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearUploads}
                  className="gap-1.5 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                  Clear
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {groupedUploads.map((group, i) => {
                if (group.type === 'batch') {
                  const { batch, children, sessionId } = group
                  const isExpanded = expandedSessions.has(sessionId)
                  const isSelected = selectedFiles.has(sessionId)

                  return (
                    <div
                      key={sessionId}
                      className={`
                        rounded-lg border-2 overflow-hidden transition-all
                        ${isSelected
                          ? 'border-orange-mid/50 bg-orange-mid/5'
                          : 'border-border bg-card'
                        }
                      `}
                    >
                      {/* Batch Header */}
                      <div
                        className={`
                          flex items-center gap-3 p-4
                          ${isSelected ? 'bg-orange-mid/10' : 'bg-muted/30'}
                        `}
                      >
                        {/* Checkbox */}
                        <button
                          onClick={() => toggleFileSelection(sessionId)}
                          className={`
                            w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0
                            ${isSelected
                              ? 'bg-orange-mid border-orange-mid text-background'
                              : 'border-muted-foreground hover:border-orange-mid'
                            }
                          `}
                        >
                          {isSelected && <Check className="w-3 h-3" />}
                        </button>

                        {/* Expand/Collapse Button */}
                        <button
                          onClick={() => toggleSessionExpanded(sessionId)}
                          className="p-1 hover:bg-background/50 rounded transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-5 h-5 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="w-5 h-5 text-muted-foreground" />
                          )}
                        </button>

                        {/* Batch Icon */}
                        <div className="w-10 h-10 rounded-lg bg-orange-mid/20 flex items-center justify-center flex-shrink-0">
                          <Package className="w-5 h-5 text-orange-light" />
                        </div>

                        {/* Batch Info */}
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold flex items-center gap-2">
                            Batch Upload
                            <Badge variant="secondary" className="text-xs">
                              {children.length} files
                            </Badge>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {formatFileSize(batch.size)}
                            {batch.items > 0 && ` • ${batch.items} items`}
                            {batch.words > 0 && ` • ${batch.words.toLocaleString()} words`}
                          </div>
                          {batch.caseId && (
                            <div className="text-xs text-orange-light mt-0.5">
                              → {cases.find(c => c.id === batch.caseId)?.title || 'Case'}
                            </div>
                          )}
                        </div>

                        {/* Review Button */}
                        <Button
                          size="sm"
                          onClick={() => {
                            localStorage.setItem('current_preflight_session', sessionId)
                            if (batch.caseId) {
                              sessionStorage.setItem(`preflight_case_${sessionId}`, batch.caseId)
                            }
                            window.location.hash = `preflight/${sessionId}`
                          }}
                        >
                          Review
                        </Button>
                      </div>

                      {/* Collapsible Children */}
                      {isExpanded && children.length > 0 && (
                        <div className="border-t border-border/50 bg-background/50">
                          <div className="px-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Files in this session
                          </div>
                          <div className="px-4 pb-3 space-y-1">
                            {children.map((file, j) => (
                              <div
                                key={j}
                                className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/30"
                              >
                                <div className={`
                                  w-6 h-6 rounded flex items-center justify-center flex-shrink-0
                                  ${file.status === 'success' ? 'bg-[#5fb3a1]/20' : 'bg-destructive/20'}
                                `}>
                                  {file.status === 'success' ? (
                                    <CheckCircle className="w-3.5 h-3.5 text-[#5fb3a1]" />
                                  ) : (
                                    <AlertCircle className="w-3.5 h-3.5 text-destructive" />
                                  )}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm truncate">{file.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {formatFileSize(file.size)}
                                  </div>
                                </div>
                                {file.error && (
                                  <span className="text-xs text-destructive">{file.error}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                }

                // Single file (non-batch)
                const { file } = group
                const isSelected = file.sessionId && selectedFiles.has(file.sessionId)

                return (
                  <div
                    key={i}
                    className={`
                      flex items-center gap-3 p-3 rounded-lg border transition-all
                      ${isSelected
                        ? 'bg-orange-mid/10 border-orange-mid/30'
                        : 'bg-card'
                      }
                    `}
                  >
                    {/* Checkbox for successful uploads */}
                    {file.status === 'success' && file.sessionId ? (
                      <button
                        onClick={() => toggleFileSelection(file.sessionId)}
                        className={`
                          w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0
                          ${isSelected
                            ? 'bg-orange-mid border-orange-mid text-background'
                            : 'border-muted-foreground hover:border-orange-mid'
                          }
                        `}
                      >
                        {isSelected && <Check className="w-3 h-3" />}
                      </button>
                    ) : (
                      <div className={`
                        w-10 h-10 rounded flex items-center justify-center flex-shrink-0
                        ${file.status === 'success' ? 'bg-[#5fb3a1]/20' : 'bg-destructive/20'}
                      `}>
                        {file.status === 'success' ? (
                          <CheckCircle className="w-5 h-5 text-[#5fb3a1]" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-destructive" />
                        )}
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{file.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {formatFileSize(file.size)}
                        {file.format && ` • ${file.format}`}
                        {file.items > 0 && ` • ${file.items} items`}
                        {file.words > 0 && ` • ${file.words.toLocaleString()} words`}
                      </div>
                      {file.caseId && (
                        <div className="text-xs text-orange-light mt-0.5">
                          → {cases.find(c => c.id === file.caseId)?.title || 'Case'}
                        </div>
                      )}
                      {file.error && (
                        <div className="text-sm text-destructive mt-1">{file.error}</div>
                      )}
                    </div>

                    {file.status === 'success' && file.sessionId && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          localStorage.setItem('current_preflight_session', file.sessionId)
                          if (file.caseId) {
                            sessionStorage.setItem(`preflight_case_${file.sessionId}`, file.caseId)
                          }
                          window.location.hash = `preflight/${file.sessionId}`
                        }}
                      >
                        Review
                      </Button>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Supported Formats */}
      <Card>
        <CardHeader>
          <CardTitle>Supported File Formats</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: 'Text', formats: '.txt, .md' },
              { label: 'Documents', formats: '.pdf' },
              { label: 'Data', formats: '.csv, .xlsx, .xls' },
              { label: 'Email', formats: '.eml, .msg' },
              { label: 'Structured', formats: '.json' },
              { label: 'Chat Exports', formats: 'WhatsApp, ChatGPT' },
            ].map((format, i) => (
              <div key={i} className="p-3 rounded-lg border bg-muted/30">
                <div className="font-semibold text-sm mb-1">{format.label}</div>
                <div className="text-xs text-muted-foreground">{format.formats}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
