import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DocumentViewer } from './document-viewer'
import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getDocumentText } from '@/lib/api'

export function DocumentViewerModal({ documentId, isOpen, onClose, highlightText = null }) {
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isOpen && documentId) {
      loadDocument()
    }
  }, [isOpen, documentId])

  async function loadDocument() {
    setLoading(true)
    setError(null)
    try {
      const data = await getDocumentText(documentId)
      setDocument(data.data || data)
    } catch (err) {
      console.error('Failed to load document:', err)
      setError(err.message || 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl h-[80vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center justify-between">
            <span>{document?.filename || 'Document'}</span>
            {document && (
              <div className="flex items-center gap-3 text-xs text-muted-foreground font-normal">
                <span>{document.line_count || 0} lines</span>
                <span className="px-1.5 py-0.5 bg-orange-mid/10 text-orange-light rounded border border-orange-mid/20">
                  {document.format || 'txt'}
                </span>
              </div>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              {error}
            </div>
          ) : document ? (
            <DocumentViewer
              text={document.text}
              format={document.format}
              filename={document.filename}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No document loaded
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
