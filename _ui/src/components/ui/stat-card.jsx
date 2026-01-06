import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * Predefined color variants for stat values
 */
const colorVariants = {
  default: 'text-foreground',
  primary: 'text-orange-light',
  secondary: 'text-blue-light',
  success: 'text-[#5fb3a1]',
  warning: 'text-orange-mid',
  muted: 'text-muted-foreground',
}

/**
 * Reusable stat card component for displaying metrics
 *
 * @param {string|number} value - The stat value to display
 * @param {string} label - Label describing the stat
 * @param {string} color - Color variant: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'muted'
 * @param {React.ElementType} icon - Optional Lucide icon component
 * @param {string} className - Additional CSS classes for the card
 */
export function StatCard({
  value,
  label,
  color = 'primary',
  icon: Icon,
  className
}) {
  const colorClass = colorVariants[color] || colorVariants.default

  return (
    <Card className={className}>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2">
          {Icon && <Icon className={cn('w-5 h-5', colorClass)} />}
          <div className={cn('text-2xl font-bold', colorClass)}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
        </div>
        <div className="text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  )
}

/**
 * Grid container for stat cards
 *
 * @param {React.ReactNode} children - StatCard components
 * @param {number} columns - Number of columns (2-4)
 * @param {string} className - Additional CSS classes
 */
export function StatGrid({ children, columns = 4, className }) {
  const gridCols = {
    2: 'grid-cols-2',
    3: 'grid-cols-2 md:grid-cols-3',
    4: 'grid-cols-2 md:grid-cols-4',
  }

  return (
    <div className={cn('grid gap-4', gridCols[columns] || gridCols[4], className)}>
      {children}
    </div>
  )
}
