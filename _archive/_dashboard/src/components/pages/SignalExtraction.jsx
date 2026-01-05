import { useState } from 'react'
import { Zap, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { analyzeTier0 } from '@/lib/api'

export function SignalExtraction() {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleAnalyze() {
    if (!text.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const data = await analyzeTier0(text)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const emotionColors = {
    joy: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    sadness: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    anger: 'bg-red-500/20 text-red-400 border-red-500/30',
    fear: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    love: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    surprise: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Zap className="w-6 h-6 text-orange-light" />
          <span className="text-glow-orange">Tier 0 Signal Extraction</span>
        </h2>
        <p className="text-muted-foreground">
          Extract emotions, entities, and temporal references without LLM costs
        </p>
      </div>

      {/* Input */}
      <Card className="terminal-corners">
        <CardHeader>
          <CardTitle>Input Text</CardTitle>
          <CardDescription>
            Paste or type the text you want to analyze. No personally identifiable information is sent to external services.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            placeholder="Enter text to analyze..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="min-h-[200px] font-mono text-sm"
          />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {text.length} characters, ~{Math.ceil(text.split(/\s+/).length)} words
            </span>
            <Button 
              onClick={handleAnalyze} 
              disabled={!text.trim() || loading}
              className="gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Analyze (Free)
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-destructive terminal-corners">
          <CardContent className="pt-6">
            <div className="flex items-start gap-2 text-destructive">
              <AlertCircle className="w-5 h-5 mt-0.5" />
              <div>
                <div className="font-semibold">Analysis Failed</div>
                <div className="text-sm">{error}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Emotions */}
          {result.emotions && result.emotions.length > 0 && (
            <Card className="terminal-corners glow-orange-hover">
              <CardHeader>
                <CardTitle>Emotions Detected</CardTitle>
                <CardDescription>
                  {result.emotions.length} emotional signals identified
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {result.emotions.map((emotion, i) => (
                    <Badge 
                      key={i} 
                      variant="outline"
                      className={emotionColors[emotion.category?.toLowerCase()] || 'bg-muted text-muted-foreground'}
                    >
                      {emotion.category} ({emotion.confidence?.toFixed(2) || 'N/A'})
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Entities */}
          {result.entities && result.entities.length > 0 && (
            <Card className="terminal-corners glow-blue-hover">
              <CardHeader>
                <CardTitle>Entities Detected</CardTitle>
                <CardDescription>
                  {result.entities.length} entities found (names, emails, phones, etc.)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {result.entities.map((entity, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <Badge variant="secondary" className="w-20 justify-center">
                        {entity.entity_type}
                      </Badge>
                      <span className="font-mono text-orange-light">{entity.raw_value}</span>
                      {entity.normalized_value && entity.normalized_value !== entity.raw_value && (
                        <span className="text-muted-foreground">
                          → {entity.normalized_value}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Temporal References */}
          {result.temporal && result.temporal.length > 0 && (
            <Card className="terminal-corners glow-blue-hover">
              <CardHeader>
                <CardTitle>Temporal References</CardTitle>
                <CardDescription>
                  {result.temporal.length} time-related mentions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {result.temporal.map((temp, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <Badge variant="secondary" className="w-20 justify-center">
                        {temp.type}
                      </Badge>
                      <span className="font-mono text-blue-light">{temp.expression}</span>
                      {temp.normalized && (
                        <span className="text-muted-foreground">
                          → {temp.normalized}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Structural Analysis */}
          {result.structure && (
            <Card className="terminal-corners">
              <CardHeader>
                <CardTitle>Structural Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-2xl font-bold text-orange-light">
                      {result.structure.word_count}
                    </div>
                    <div className="text-sm text-muted-foreground">Words</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-light">
                      {result.structure.sentence_count}
                    </div>
                    <div className="text-sm text-muted-foreground">Sentences</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-light">
                      {result.structure.avg_sentence_length?.toFixed(1)}
                    </div>
                    <div className="text-sm text-muted-foreground">Avg Words/Sentence</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-light">
                      {result.structure.complexity_score?.toFixed(2)}
                    </div>
                    <div className="text-sm text-muted-foreground">Complexity</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
