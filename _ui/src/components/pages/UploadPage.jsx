import { useState, useRef } from 'react'
import { FileUp, Upload, File, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { uploadFile, detectFileFormat } from '@/lib/api'

export function UploadPage() {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

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
        
        // Upload file
        const upload = await uploadFile(file)
        
        newFiles.push({
          name: file.name,
          size: file.size,
          type: file.type,
          format: detection.format,
          sessionId: upload.session_id,
          status: 'success',
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

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

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
            <CardTitle>Uploaded Files</CardTitle>
            <CardDescription>
              {files.length} file{files.length !== 1 ? 's' : ''} uploaded
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {files.map((file, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg border bg-card">
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
                  
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{file.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {formatFileSize(file.size)}
                      {file.format && ` • ${file.format}`}
                    </div>
                    {file.error && (
                      <div className="text-sm text-destructive mt-1">{file.error}</div>
                    )}
                  </div>

                  {file.status === 'success' && file.sessionId && (
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => {
                        // Navigate to preflight page (we'll implement this)
                        console.log('Navigate to preflight:', file.sessionId)
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
