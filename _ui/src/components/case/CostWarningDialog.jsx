/**
 * CostWarningDialog - Cost confirmation dialog before starting LLM processing (v0.8)
 *
 * Shows:
 * - Document count
 * - Estimated tokens
 * - Estimated cost in USD
 * - Confirm/Cancel buttons
 */

import { AlertCircle, DollarSign, FileText, Cpu, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export default function CostWarningDialog({
  open,
  onOpenChange,
  onConfirm,
  onCancel,
  estimate,
  isLoading = false,
}) {
  if (!estimate) return null

  const handleConfirm = () => {
    onConfirm?.()
  }

  const handleCancel = () => {
    onCancel?.()
    onOpenChange?.(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="text-yellow-400" size={24} />
            <DialogTitle className="text-lg">Ready for Deep Analysis</DialogTitle>
          </div>
          <DialogDescription className="text-muted-foreground">
            AI-powered extraction will analyze your documents for insights
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-4">
          {/* Document Count */}
          <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <FileText size={16} />
              Documents
            </div>
            <span className="font-bold text-foreground">
              {estimate.extraction?.document_count || estimate.document_count || 0}
            </span>
          </div>

          {/* Estimated Tokens */}
          <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Cpu size={16} />
              Estimated Tokens
            </div>
            <span className="font-mono text-sm text-foreground">
              {(estimate.total_tokens || estimate.extraction?.estimated_tokens || 0).toLocaleString()}
            </span>
          </div>

          {/* Cost */}
          <div className="flex items-center justify-between p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-sm font-medium">
              <DollarSign size={16} className="text-yellow-400" />
              Estimated Cost
            </div>
            <span className="font-bold text-lg">
              ${(estimate.total_cost_usd || estimate.extraction?.estimated_cost_usd || 0).toFixed(2)}
            </span>
          </div>

          {/* Model info */}
          {estimate.model && (
            <div className="text-xs text-muted-foreground text-center">
              Using {estimate.model}
            </div>
          )}

          <p className="text-xs text-muted-foreground pt-2">
            This will extract insights, identify patterns, and generate synthesis.
            Progress will be shown in real-time on the terminal monitor.
          </p>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isLoading}
            className="bg-yellow-500 hover:bg-yellow-600 text-black"
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              'Start Deep Analysis'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
