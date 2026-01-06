import { cn } from '@/lib/utils'

/**
 * Reusable empty state component
 *
 * @param {React.ElementType} icon - Lucide icon component
 * @param {string} title - Main title text
 * @param {string} description - Description text
 * @param {React.ReactNode} action - Optional action button/element
 * @param {string} variant - Style variant: 'default' | 'card' | 'dashed'
 * @param {string} className - Additional CSS classes
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = 'default',
  className
}) {
  const variants = {
    default: '',
    card: 'bg-card border border-border rounded-lg',
    dashed: 'border border-dashed border-border rounded-lg',
  }

  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center py-12 px-4',
      variants[variant],
      className
    )}>
      {Icon && (
        <Icon className="w-10 h-10 text-muted-foreground mb-3" />
      )}
      {title && (
        <h3 className="text-lg font-medium text-foreground mb-1">
          {title}
        </h3>
      )}
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm mb-4">
          {description}
        </p>
      )}
      {action}
    </div>
  )
}
