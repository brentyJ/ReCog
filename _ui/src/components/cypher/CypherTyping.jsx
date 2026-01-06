export function CypherTyping() {
  return (
    <div className="flex justify-start">
      <div className="bg-card border border-border rounded-lg p-3">
        <div className="flex gap-1">
          <span
            className="w-2 h-2 bg-teal-400 rounded-full animate-bounce"
            style={{ animationDelay: '0ms' }}
          />
          <span
            className="w-2 h-2 bg-teal-400 rounded-full animate-bounce"
            style={{ animationDelay: '150ms' }}
          />
          <span
            className="w-2 h-2 bg-teal-400 rounded-full animate-bounce"
            style={{ animationDelay: '300ms' }}
          />
        </div>
      </div>
    </div>
  )
}
