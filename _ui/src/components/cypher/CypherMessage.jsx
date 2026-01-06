import { CypherSuggestions } from './CypherSuggestions'

function formatTimestamp(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function CypherMessage({ message }) {
  const isUser = message.role === 'user'
  const isCypher = message.role === 'assistant'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] ${isUser ? 'order-2' : 'order-1'}`}>
        {/* Role indicator */}
        <div className={`flex items-center gap-2 mb-1 ${isUser ? 'justify-end' : ''}`}>
          {isCypher && <span className="text-teal-400 font-mono text-xs">⟨⟩</span>}
          <span className="text-[10px] text-muted-foreground font-mono">
            {formatTimestamp(message.timestamp)}
          </span>
          {isUser && <span className="text-muted-foreground text-xs">you</span>}
        </div>

        {/* Message content */}
        <div
          className={`rounded-lg p-3 font-mono text-sm whitespace-pre-wrap ${
            isUser
              ? 'bg-orange-mid/20 text-foreground border border-orange-mid/30'
              : 'bg-card border border-border'
          }`}
        >
          {message.content}
        </div>

        {/* Suggestions (only for Cypher messages) */}
        {isCypher && message.suggestions && (
          <CypherSuggestions suggestions={message.suggestions} />
        )}
      </div>
    </div>
  )
}
