import { Button } from '@/components/ui/button'
import { useCypherActions } from '@/hooks/useCypherActions'
import { useCypher } from '@/contexts/CypherContext'
import {
  Users,
  Lightbulb,
  Calendar,
  X,
  Upload,
  Play,
  FileSearch,
  LayoutDashboard,
  GitBranch,
  FolderOpen,
  RefreshCw,
  Check,
  Sparkles,
} from 'lucide-react'

// Map icon names to components
const ICONS = {
  Users,
  Lightbulb,
  Calendar,
  X,
  Upload,
  Play,
  FileSearch,
  LayoutDashboard,
  GitBranch,
  FolderOpen,
  RefreshCw,
  Check,
  Sparkles,
}

export function CypherSuggestions({ suggestions }) {
  const { executeAction } = useCypherActions()
  const { retryLast } = useCypher()

  if (!suggestions || suggestions.length === 0) return null

  const handleClick = async (suggestion) => {
    if (suggestion.action === 'retry_last') {
      retryLast()
      return
    }
    if (suggestion.action) {
      await executeAction(suggestion.action, suggestion.params)
    }
  }

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {suggestions.map((suggestion, i) => {
        const Icon = suggestion.icon ? ICONS[suggestion.icon] : null

        return (
          <Button
            key={i}
            variant="outline"
            size="sm"
            onClick={() => handleClick(suggestion)}
            className="font-mono text-xs h-7 px-2"
          >
            {Icon && <Icon className="h-3 w-3 mr-1" />}
            {suggestion.text}
          </Button>
        )
      })}
    </div>
  )
}
