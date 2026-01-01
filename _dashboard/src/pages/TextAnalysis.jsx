import { useState } from 'react'
import { Zap, Loader2, Sparkles, User, Calendar, DollarSign, MapPin, Link as LinkIcon } from 'lucide-react'

const ENTITY_ICONS = {
  PERSON: User,
  DATE: Calendar,
  MONEY: DollarSign,
  LOCATION: MapPin,
  URL: LinkIcon,
  EMAIL: LinkIcon,
  PHONE: LinkIcon,
}

export default function TextAnalysis() {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    if (!text.trim()) return

    setLoading(true)
    setError(null)
    
    try {
      const res = await fetch('/api/tier0', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      
      const data = await res.json()
      
      if (data.success) {
        setResult(data.data)
      } else {
        setError(data.error || 'Analysis failed')
      }
    } catch (err) {
      setError(`Connection error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setText('')
    setResult(null)
    setError(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-primary" />
          Text Analysis
        </h2>
        <p className="text-muted-foreground mt-1">
          Zero-cost signal extraction with Tier 0 analysis
        </p>
      </div>

      {/* Input Card */}
      <div className="recog-card">
        <div className="recog-card-header">
          <h3 className="recog-card-title">Input Text</h3>
          <p className="recog-card-description">
            Enter text to extract entities, detect emotions, and analyze sentiment
          </p>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your text here...

Example: Had a great meeting with Sarah on Monday. She mentioned the Q3 budget is around $50,000. Contact her at sarah@example.com or 0412-555-789."
          className="w-full h-40 px-4 py-3 bg-background border border-border rounded-md text-foreground placeholder-muted-foreground font-mono text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary/50"
        />

        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-muted-foreground font-mono">
            {text.length} characters • {text.split(/\s+/).filter(Boolean).length} words
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleClear}
              disabled={!text && !result}
              className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Clear
            </button>
            <button
              onClick={handleAnalyze}
              disabled={!text.trim() || loading}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Analyze
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-md">
          <p className="text-destructive text-sm font-mono">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Emotions */}
          {result.emotions && Object.keys(result.emotions).length > 0 && (
            <div className="recog-card">
              <div className="recog-card-header">
                <h3 className="recog-card-title">Emotional Analysis</h3>
                <p className="recog-card-description">
                  Detected emotional tones in the text
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(result.emotions).map(([emotion, score]) => (
                  <div
                    key={emotion}
                    className="px-3 py-2 bg-primary/10 border border-primary/30 rounded-md"
                  >
                    <div className="text-sm font-medium text-foreground capitalize">
                      {emotion}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-1">
                      {(score * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Entities */}
          {result.entities && result.entities.length > 0 && (
            <div className="recog-card">
              <div className="recog-card-header">
                <h3 className="recog-card-title">Extracted Entities</h3>
                <p className="recog-card-description">
                  {result.entities.length} {result.entities.length === 1 ? 'entity' : 'entities'} detected
                </p>
              </div>
              <div className="space-y-2">
                {result.entities.map((entity, idx) => {
                  const Icon = ENTITY_ICONS[entity.type] || User
                  return (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-3 bg-background border border-border rounded-md hover:border-primary/30 transition-colors"
                    >
                      <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
                        <Icon className="w-4 h-4 text-primary" />
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-foreground font-mono">
                          {entity.value}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {entity.type}
                          {entity.confidence && ` • ${(entity.confidence * 100).toFixed(0)}% confidence`}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Sentiment */}
          {result.sentiment && (
            <div className="recog-card">
              <div className="recog-card-header">
                <h3 className="recog-card-title">Sentiment Analysis</h3>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-success">
                    {(result.sentiment.positive * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">Positive</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-muted-foreground">
                    {(result.sentiment.neutral * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">Neutral</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-destructive">
                    {(result.sentiment.negative * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">Negative</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
