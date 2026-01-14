import { useState, useEffect } from 'react'
import {
  Settings,
  Key,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Trash2,
  RefreshCw,
  Shield,
  Zap,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { LoadingState } from '@/components/ui/loading-state'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  getProviders,
  getProvidersStatus,
  configureProvider,
  removeProvider,
  verifyProvider,
} from '@/lib/api'

// Provider icons and colors
const PROVIDER_META = {
  anthropic: {
    name: 'Anthropic (Claude)',
    color: 'text-amber-400',
    bgColor: 'bg-amber-400/10',
    borderColor: 'border-amber-400/30',
    description: 'Claude models - excellent for analysis and reasoning',
    keyPrefix: 'sk-ant-',
    keyPlaceholder: 'sk-ant-api03-...',
  },
  openai: {
    name: 'OpenAI',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-400/10',
    borderColor: 'border-emerald-400/30',
    description: 'GPT models - fast and cost-effective',
    keyPrefix: 'sk-',
    keyPlaceholder: 'sk-proj-...',
  },
}

export function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [providers, setProviders] = useState([])
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  // Dialog state
  const [configDialogOpen, setConfigDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState(null)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [verifying, setVerifying] = useState(null)
  const [removing, setRemoving] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [providersRes, statusRes] = await Promise.all([
        getProviders().catch(() => ({ data: { providers: [] } })),
        getProvidersStatus().catch(() => ({ data: {} })),
      ])
      setProviders(providersRes?.data?.providers || providersRes?.providers || [])
      setStatus(statusRes?.data || statusRes)
    } catch (err) {
      setError(err.message || 'Failed to load providers')
    } finally {
      setLoading(false)
    }
  }

  function openConfigDialog(provider) {
    setSelectedProvider(provider)
    setApiKeyInput('')
    setShowApiKey(false)
    setConfigDialogOpen(true)
  }

  async function handleSaveApiKey() {
    if (!apiKeyInput.trim() || !selectedProvider) return

    setSaving(true)
    setError(null)
    try {
      await configureProvider(selectedProvider.name, apiKeyInput.trim(), true)
      setConfigDialogOpen(false)
      setApiKeyInput('')
      await loadData()
      // Notify header to refresh provider status
      window.dispatchEvent(new CustomEvent('providers-updated'))
    } catch (err) {
      setError(err.message || 'Failed to save API key')
    } finally {
      setSaving(false)
    }
  }

  async function handleVerify(providerName) {
    setVerifying(providerName)
    setError(null)
    try {
      await verifyProvider(providerName)
      await loadData()
    } catch (err) {
      setError(err.message || 'Verification failed')
    } finally {
      setVerifying(null)
    }
  }

  async function handleRemove(providerName) {
    if (!confirm(`Remove ${PROVIDER_META[providerName]?.name || providerName} API key?`)) {
      return
    }

    setRemoving(providerName)
    setError(null)
    try {
      await removeProvider(providerName)
      await loadData()
      // Notify header to refresh provider status
      window.dispatchEvent(new CustomEvent('providers-updated'))
    } catch (err) {
      setError(err.message || 'Failed to remove provider')
    } finally {
      setRemoving(null)
    }
  }

  if (loading) {
    return <LoadingState message="Loading settings..." size="lg" />
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Settings className="w-6 h-6 text-orange-light" />
          Settings
        </h2>
        <p className="text-muted-foreground">
          Configure API providers for AI-powered analysis
        </p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-red-400 font-medium">Error</p>
            <p className="text-red-300/80 text-sm">{error}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => setError(null)}
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Status Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Zap className="w-5 h-5 text-orange-light" />
            Provider Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {status?.configured ? (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-sm">
                  Primary: <span className="text-foreground font-medium">{status.primary_name}</span>
                </span>
              </div>
              {status.fallback && (
                <>
                  <span className="text-muted-foreground">→</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm">
                      Fallback: <span className="text-foreground font-medium">{status.fallback_name}</span>
                    </span>
                  </div>
                </>
              )}
              {status.failover_enabled && (
                <Badge variant="outline" className="ml-auto border-emerald-400/50 text-emerald-400">
                  <Shield className="w-3 h-3 mr-1" />
                  Failover Active
                </Badge>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-amber-400">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">No providers configured. Add an API key below to enable AI features.</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Provider Cards */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">API Providers</h3>

        {providers.map((provider) => {
          const meta = PROVIDER_META[provider.name] || {
            name: provider.display_name,
            color: 'text-blue-400',
            bgColor: 'bg-blue-400/10',
            borderColor: 'border-blue-400/30',
            description: 'LLM provider',
          }

          return (
            <Card
              key={provider.name}
              className={`${provider.active ? meta.borderColor : 'border-border'} ${
                provider.active ? meta.bgColor : ''
              }`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  {/* Provider Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Key className={`w-4 h-4 ${meta.color}`} />
                      <h4 className="font-semibold">{meta.name}</h4>
                      {provider.active ? (
                        <Badge variant="outline" className="border-emerald-400/50 text-emerald-400 text-xs">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Active
                        </Badge>
                      ) : provider.configured ? (
                        <Badge variant="outline" className="border-amber-400/50 text-amber-400 text-xs">
                          Configured
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-muted-foreground/50 text-muted-foreground text-xs">
                          Not Configured
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{meta.description}</p>

                    {provider.configured && provider.masked_key && (
                      <div className="flex items-center gap-2 text-xs font-mono bg-background/50 rounded px-2 py-1 w-fit">
                        <span className="text-muted-foreground">{provider.masked_key}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {provider.configured ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleVerify(provider.name)}
                          disabled={verifying === provider.name}
                        >
                          {verifying === provider.name ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RefreshCw className="w-4 h-4" />
                          )}
                          <span className="ml-1">Verify</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openConfigDialog(provider)}
                        >
                          Update
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-400 hover:text-red-300 hover:bg-red-400/10"
                          onClick={() => handleRemove(provider.name)}
                          disabled={removing === provider.name}
                        >
                          {removing === provider.name ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => openConfigDialog(provider)}
                      >
                        <Key className="w-4 h-4 mr-1" />
                        Add Key
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Help Section */}
      <Card className="bg-card/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Getting API Keys</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            <strong className="text-foreground">Anthropic:</strong>{' '}
            Get your API key at{' '}
            <a
              href="https://console.anthropic.com/settings/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-orange-light hover:underline"
            >
              console.anthropic.com
            </a>
          </p>
          <p>
            <strong className="text-foreground">OpenAI:</strong>{' '}
            Get your API key at{' '}
            <a
              href="https://platform.openai.com/api-keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-orange-light hover:underline"
            >
              platform.openai.com
            </a>
          </p>
          <p className="text-xs mt-4 pt-3 border-t border-border">
            API keys are stored locally in your .env file and never transmitted to any server except the provider's API.
          </p>
        </CardContent>
      </Card>

      {/* Configure Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedProvider?.configured ? 'Update' : 'Add'}{' '}
              {PROVIDER_META[selectedProvider?.name]?.name || selectedProvider?.display_name} API Key
            </DialogTitle>
            <DialogDescription>
              Enter your API key to enable AI-powered analysis. The key will be verified before saving.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="api-key">API Key</Label>
              <div className="relative">
                <Input
                  id="api-key"
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={PROVIDER_META[selectedProvider?.name]?.keyPlaceholder || 'Enter API key...'}
                  className="pr-10 font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                Keys starting with{' '}
                <code className="bg-background px-1 rounded">
                  {PROVIDER_META[selectedProvider?.name]?.keyPrefix || 'sk-'}
                </code>
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfigDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveApiKey}
              disabled={!apiKeyInput.trim() || saving}
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Save & Verify
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
