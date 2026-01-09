import { useState, useRef, useEffect } from 'react'
import { X, Send, Trash2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useCypher } from '@/contexts/CypherContext'
import { CypherMessage } from './CypherMessage'
import { CypherProgress } from './CypherProgress'
import { CypherTyping } from './CypherTyping'

// Contextual empty state based on current view
function EmptyState({ currentView, assistantMode }) {
  const hints = {
    entities: {
      title: 'Entity Management',
      examples: ['"Webb isn\'t a person"', '"Mark Sarah as family"', '"Who appears most?"'],
    },
    insights: {
      title: 'Insights Browser',
      examples: ['"Show high significance"', '"Filter by emotions"', '"What patterns emerged?"'],
    },
    preflight: {
      title: 'Preflight Review',
      examples: ['"Process all items"', '"Skip short documents"', '"What\'s queued?"'],
    },
    upload: {
      title: 'File Upload',
      examples: ['"What formats supported?"', '"Start processing"', '"Link to a case"'],
    },
    cases: {
      title: 'Case Management',
      examples: ['"Show active cases"', '"What\'s in this case?"', '"Add focus area"'],
    },
    patterns: {
      title: 'Pattern Synthesis',
      examples: ['"Run synthesis"', '"Show strongest patterns"', '"Cluster by entity"'],
    },
    default: {
      title: assistantMode ? 'Assistant ready to guide.' : 'Cypher ready.',
      examples: assistantMode
        ? ['"Help me understand"', '"What should I do next?"', '"Explain this step"']
        : ['"Show me entities"', '"Webb isn\'t a person"', '"Focus on Seattle"'],
    },
  }

  const { title, examples } = hints[currentView] || hints.default
  const accentClass = assistantMode ? 'text-amber-400' : 'text-teal-400'

  return (
    <div className="text-center text-muted-foreground text-sm font-mono py-8 px-4">
      <div className={`${accentClass} text-3xl mb-3`}>⟨⟩</div>
      <div className="mb-2">{title}</div>
      <div className="text-xs">
        {assistantMode
          ? 'Ask anything - I\'ll explain the process step by step.'
          : 'Ask questions, correct entities, or request navigation.'}
      </div>
      <div className="mt-4 text-[10px] text-muted-foreground/60 space-y-1">
        {examples.map((ex, i) => (
          <div key={i}>{ex}</div>
        ))}
      </div>
    </div>
  )
}

export function Cypher() {
  const {
    messages,
    isProcessing,
    extractionStatus,
    sendMessage,
    clearHistory,
    isOpen,
    setIsOpen,
    currentView,
    // v0.8: Assistant mode
    assistantMode,
    toggleAssistantMode,
    caseState,
  } = useCypher()

  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // v0.8: Color scheme based on assistant mode
  const accentColor = assistantMode ? 'amber' : 'teal'
  const accentText = assistantMode ? 'text-amber-400' : 'text-teal-400'
  const accentBg = assistantMode ? 'bg-amber-400/20' : 'bg-teal-400/20'
  const accentBorder = assistantMode ? 'border-amber-400/30' : 'border-teal-400/30'

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  const handleSend = async () => {
    if (!input.trim() || isProcessing) return
    const msg = input
    setInput('')
    await sendMessage(msg)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  // Check if extraction is active
  const isExtracting =
    extractionStatus?.status === 'processing' || extractionStatus?.status === 'pending'

  return (
    <>
      {/* Trigger Button */}
      <Button
        variant="outline"
        onClick={() => setIsOpen(true)}
        className="font-mono text-sm gap-2 h-9"
      >
        <span className={accentText}>⟨⟩</span>
        Cypher
        {assistantMode && (
          <Sparkles className={`h-3 w-3 ${accentText}`} />
        )}
        {isExtracting && (
          <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] ${accentBg} ${accentText} animate-pulse`}>
            {extractionStatus.current}/{extractionStatus.total}
          </span>
        )}
      </Button>

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-[100]"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Side Panel */}
      <div
        className={`
          fixed top-0 right-0 h-full w-[420px] bg-background border-l border-border
          flex flex-col z-[101] shadow-2xl
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-border bg-card flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={`text-2xl ${accentText} font-mono`}>⟨⟩</span>
            <div>
              <div className="font-mono font-bold text-base flex items-center gap-2">
                Cypher
                {assistantMode && (
                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${accentText} ${accentBorder}`}>
                    <Sparkles className="h-2.5 w-2.5 mr-1" />
                    Guide
                  </Badge>
                )}
              </div>
              <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider">
                {assistantMode ? 'tutorial assistant' : 'terminal scribe'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Assistant Mode Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleAssistantMode}
              className={`h-8 w-8 ${assistantMode ? accentText : 'text-muted-foreground'} hover:${accentText}`}
              title={assistantMode ? 'Disable assistant mode' : 'Enable assistant mode'}
            >
              <Sparkles className="h-4 w-4" />
            </Button>
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={clearHistory}
                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                title="Clear history"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsOpen(false)}
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
          {/* Progress indicator at top when extracting */}
          <CypherProgress extractionStatus={extractionStatus} />

          {messages.length === 0 && !isExtracting && (
            <EmptyState currentView={currentView} assistantMode={assistantMode} />
          )}

          {messages.map((message, i) => (
            <CypherMessage key={i} message={message} />
          ))}

          {isProcessing && <CypherTyping />}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-border bg-card">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type message..."
              className="font-mono text-sm"
              disabled={isProcessing}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isProcessing}
              size="icon"
              className="shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <div className="text-[10px] text-muted-foreground mt-2 font-mono">
            Enter to send · Esc to close
          </div>
        </div>
      </div>
    </>
  )
}