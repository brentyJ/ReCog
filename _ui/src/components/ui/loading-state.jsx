import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Reusable loading state component
 *
 * @param {string} message - Loading message to display
 * @param {string} size - Size variant: 'sm' | 'default' | 'lg'
 * @param {string} className - Additional CSS classes
 */
export function LoadingState({
  message = 'Loading...',
  size = 'default',
  className
}) {
  const sizes = {
    sm: { icon: 'w-4 h-4', text: 'text-sm', padding: 'py-4' },
    default: { icon: 'w-6 h-6', text: 'text-base', padding: 'py-8' },
    lg: { icon: 'w-8 h-8', text: 'text-lg', padding: 'py-12' },
  }

  const { icon, text, padding } = sizes[size] || sizes.default

  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center text-muted-foreground',
      padding,
      className
    )}>
      <Loader2 className={cn(icon, 'animate-spin mb-2')} />
      {message && <span className={text}>{message}</span>}
    </div>
  )
}
