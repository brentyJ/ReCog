import { cn } from '@/lib/utils'

/**
 * Status color schemes used across the app
 */
const statusColors = {
  // Case status
  active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  archived: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',

  // Finding/verification status
  verified: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  needs_verification: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',

  // Insight status
  raw: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  refined: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  surfaced: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',

  // Processing status
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  processing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  complete: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',

  // Significance levels
  high: 'bg-orange-mid/20 text-orange-light border-orange-mid/30',
  medium: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  low: 'bg-muted text-muted-foreground border-border',

  // Generic
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  default: 'bg-muted text-muted-foreground border-border',
}

/**
 * Display labels for status values
 */
const statusLabels = {
  needs_verification: 'Needs Review',
  // Add more label overrides as needed
}

/**
 * Reusable status badge component with predefined color schemes
 *
 * @param {string} status - Status key (e.g., 'active', 'verified', 'pending')
 * @param {string} label - Optional custom label (defaults to status with first letter capitalized)
 * @param {string} size - Size variant: 'sm' | 'default'
 * @param {string} className - Additional CSS classes
 */
export function StatusBadge({
  status,
  label,
  size = 'default',
  className
}) {
  const colorClass = statusColors[status] || statusColors.default

  const displayLabel = label || statusLabels[status] || (
    status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ')
  )

  const sizeClass = size === 'sm'
    ? 'px-1.5 py-0.5 text-[10px]'
    : 'px-2 py-0.5 text-xs'

  return (
    <span className={cn(
      'inline-flex items-center rounded font-medium border',
      sizeClass,
      colorClass,
      className
    )}>
      {displayLabel}
    </span>
  )
}

/**
 * Get status color class for custom usage
 */
export function getStatusColor(status) {
  return statusColors[status] || statusColors.default
}

export { statusColors }
