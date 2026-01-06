import { useState, useEffect } from 'react'
import {
  FileText,
  Download,
  Search,
  Copy,
  Check,
  ArrowLeft,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DocumentViewer } from '@/components/ui/document-viewer'
import { LoadingState } from '@/components/ui/loading-state'
import { getDocumentText } from '@/lib/api'

export function DocumentViewerPage() {
  // Get document ID from URL hash (e.g., #document/123)
  const [documentId, setDocumentId] = useState(null)
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    function parseHash() {
      const hash = window.location.hash
      const match = hash.match(/document\/(.+)/)
      if (match) {
        setDocumentId(match[1])
      }
    }

    parseHash()
    window.addEventListener('hashchange', parseHash)
    return () => window.removeEventListener('hashchange', parseHash)
  }, [])

  useEffect(() => {
    if (documentId) {
      loadDocument()
    }
  }, [documentId])

  async function loadDocument() {
    setLoading(true)
    setError(null)
    try {
      const data = await getDocumentText(documentId)
      setDocument(data.data || data)
    } catch (err) {
      setError(err.message || 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  async function handleCopy() {
    if (document?.text) {
      await navigator.clipboard.writeText(document.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function handleDownload() {
    if (!document?.text) return

    const blob = new Blob([document.text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = window.document.createElement('a')
    a.href = url
    a.download = document.filename || 'document.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleBack() {
    window.history.back()
  }

  if (!documentId) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <FileText className="w-16 h-16 text-muted-foreground" />
        <div className="text-center">
          <h3 className="text-lg font-semibold text-foreground mb-2">No Document Selected</h3>
          <p className="text-sm text-muted-foreground mb-4">Navigate to a document to view its contents.</p>
          <Button onClick={handleBack}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go Back
          </Button>
        </div>
      </div>
    )
  }

  if (loading) {
    return <LoadingState message="Loading document..." size="lg" />
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <FileText className="w-16 h-16 text-muted-foreground" />
        <div className="text-center">
          <h3 className="text-lg font-semibold text-foreground mb-2">Document Not Found</h3>
          <p className="text-sm text-muted-foreground mb-4">{error}</p>
          <Button onClick={handleBack}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go Back
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card/50">
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="p-2 hover:bg-muted rounded-md transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {document?.filename || 'Document'}
            </h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{document?.line_count || 0} lines</span>
              <span className="text-muted-foreground/50">|</span>
              <span>{document?.char_count || 0} characters</span>
              <span className="text-muted-foreground/50">|</span>
              <span className="px-1.5 py-0.5 bg-orange-mid/10 text-orange-light rounded border border-orange-mid/20">
                {document?.format || 'txt'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 w-64"
            />
          </div>

          {/* Copy */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={copied}
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copy
              </>
            )}
          </Button>

          {/* Download */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
        </div>
      </div>

      {/* Document Viewer */}
      <div className="flex-1 p-4 min-h-0">
        <DocumentViewer
          text={document?.text || ''}
          format={document?.format || 'txt'}
          filename={document?.filename || ''}
        />
      </div>
    </div>
  )
}
