import { useState, useRef, useEffect } from 'react'
import { FileUp, Upload, File, CheckCircle, AlertCircle, Loader2, FolderOpen, Plus, Check, CheckSquare, Square, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { uploadFile, detectFileFormat, getCases, createCase } from '@/lib/api'

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
  const fileInputRef = useRef(null)

  // Get successful uploads with session IDs
  const successfulFiles = files.filter(f => f.status === 'success' && f.sessionId)
  const allSelected = successfulFiles.length > 0 && successfulFiles.every(f => selectedFiles.has(f.sessionId))
  const someSelected = selectedFiles.size > 0

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
      setSelectedFiles(new Set(successfulFiles.map(f => f.sessionId)))
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
    localStorage.removeItem('upload_files')
  }

  // Persist files to localStorage when they change
  useEffect(() => {
    localStorage.setItem('upload_files', JSON.stringify(files))
  }, [files])

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
    await processFiles(selectedFiles)
  }

  async function processFiles(fileList) {
    setUploading(true)
    
    const newFiles = []
    for (const file of fileList) {
      try {
        // Detect format first
        const detection = await detectFileFormat(file)
        
        // Upload file with case_id for context injection
        const upload = await uploadFile(file, selectedCaseId || null)
        
        newFiles.push({
          name: file.name,
          size: file.size,
          type: file.type,
          format: detection.data?.file_type || 'unknown',
          sessionId: upload.data?.preflight_session_id,
          caseId: selectedCaseId || null,
          status: 'success',
          items: upload.data?.items || 0,
          words: upload.data?.words || 0,
        })
      } catch (error) {
        newFiles.push({
          name: file.name,
          size: file.size,
          type: file.type,
          status: 'error',
          error: error.message,
        })
      }
    }
    
    setFiles(prev => [...prev, ...newFiles])
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
      {files.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle>Uploaded Files</CardTitle>
                <CardDescription>
                  {files.length} file{files.length !== 1 ? 's' : ''} uploaded
                  {someSelected && ` • ${selectedFiles.size} selected`}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                {successfulFiles.length > 0 && (
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
            <div className="space-y-2">
              {files.map((file, i) => (
                <div
                  key={i}
                  className={`
                    flex items-center gap-3 p-3 rounded-lg border transition-all
                    ${file.sessionId && selectedFiles.has(file.sessionId)
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
                        ${selectedFiles.has(file.sessionId)
                          ? 'bg-orange-mid border-orange-mid text-background'
                          : 'border-muted-foreground hover:border-orange-mid'
                        }
                      `}
                    >
                      {selectedFiles.has(file.sessionId) && <Check className="w-3 h-3" />}
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
              ))}
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
