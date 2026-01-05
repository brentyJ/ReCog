import { useState, useEffect } from 'react'
import { Zap, Check, X, Loader2, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function TethersPage() {
  const [providers, setProviders] = useState([])
  const [tethers, setTethers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showKeys, setShowKeys] = useState({})
  const [editingProvider, setEditingProvider] = useState(null)
  const [newKey, setNewKey] = useState('')
  const [processing, setProcessing] = useState({})

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      // Load providers
      const providersRes = await fetch('/api/tethers/providers')
      const providersData = await providersRes.json()
      if (providersData.success) {
        setProviders(providersData.providers || [])
      }

      // Load tethers
      const tethersRes = await fetch('/api/tethers')
      const tethersData = await tethersRes.json()
      if (tethersData.success) {
        setTethers(tethersData.tethers || [])
      }
    } catch (error) {
      console.error('Failed to load tether data:', error)
    } finally {
      setLoading(false)
    }
  }

  function getTetherForProvider(providerKey) {
    return tethers.find(t => t.provider === providerKey)
  }

  function getProviderIcon(providerKey) {
    const icons = {
      'claude': '◈',
      'openai': '◉',
      'gemini': '✧',
    }
    return icons[providerKey] || '◆'
  }

  function getProviderColor(providerKey) {
    const colors = {
      'claude': 'text-[#d4a574]',
      'openai': 'text-[#10a37f]',
      'gemini': 'text-[#4285f4]',
    }
    return colors[providerKey] || 'text-orange-light'
  }

  function getProviderBorderColor(providerKey) {
    const colors = {
      'claude': 'border-[#d4a574]/30',
      'openai': 'border-[#10a37f]/30',
      'gemini': 'border-[#4285f4]/30',
    }
    return colors[providerKey] || 'border-orange-mid/30'
  }

  async function handleSaveKey(providerKey) {
    if (!newKey.trim()) return

    setProcessing({ ...processing, [providerKey]: 'saving' })
    try {
      const res = await fetch('/api/tethers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: providerKey, api_key: newKey })
      })
      const data = await res.json()

      if (data.success) {
        setNewKey('')
        setEditingProvider(null)
        // Auto-verify after save
        setTimeout(() => handleVerify(providerKey), 500)
        await loadData()
      } else {
        alert(data.error || 'Failed to save key')
      }
    } catch (error) {
      alert('Network error')
    } finally {
      setProcessing({ ...processing, [providerKey]: null })
    }
  }

  async function handleVerify(providerKey) {
    setProcessing({ ...processing, [providerKey]: 'verifying' })
    try {
      const res = await fetch(`/api/tethers/${providerKey}/verify`, { method: 'POST' })
      const data = await res.json()

      if (!data.valid) {
        alert(data.message || 'Verification failed')
      }
      await loadData()
    } catch (error) {
      alert('Verification failed')
    } finally {
      setProcessing({ ...processing, [providerKey]: null })
    }
  }

  async function handleToggle(providerKey, active) {
    setProcessing({ ...processing, [providerKey]: 'toggling' })
    try {
      const res = await fetch(`/api/tethers/${providerKey}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active })
      })
      const data = await res.json()

      if (!data.success) {
        alert(data.error || 'Toggle failed')
      }
      await loadData()
    } catch (error) {
      alert('Network error')
    } finally {
      setProcessing({ ...processing, [providerKey]: null })
    }
  }

  async function handleRemove(providerKey, providerName) {
    if (!window.confirm(`Remove ${providerName} tether? This will delete the stored API key.`)) {
      return
    }

    setProcessing({ ...processing, [providerKey]: 'removing' })
    try {
      const res = await fetch(`/api/tethers/${providerKey}`, { method: 'DELETE' })
      const data = await res.json()

      if (!data.success) {
        alert(data.error || 'Remove failed')
      }
      await loadData()
    } catch (error) {
      alert('Network error')
    } finally {
      setProcessing({ ...processing, [providerKey]: null })
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto">
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2 text-muted-foreground" />
            <p className="text-muted-foreground">Loading tether data...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Zap className="w-6 h-6 text-orange-light" />
          Tether Management
        </h2>
        <p className="text-muted-foreground">
          Tethers are direct conduits to LLM sources. Unlike mana, tethers never deplete—they 
          channel directly from the source while connected.
        </p>
      </div>

      {/* Providers List */}
      <div className="space-y-4">
        {providers.map((provider) => {
          const tether = getTetherForProvider(provider.provider_key)
          const hasKey = tether && tether.has_key
          const status = tether?.verification_status || 'none'
          const active = tether?.active === 1
          const isConnected = hasKey && active && status === 'valid'
          const isEditing = editingProvider === provider.provider_key
          const isProcessing = processing[provider.provider_key]

          let statusLabel = 'No key configured'
          let statusVariant = 'secondary'
          if (hasKey) {
            if (status === 'valid') {
              statusLabel = active ? 'Connected' : 'Disconnected'
              statusVariant = active ? 'default' : 'secondary'
            } else if (status === 'invalid') {
              statusLabel = 'Invalid key'
              statusVariant = 'destructive'
            } else if (status === 'pending') {
              statusLabel = 'Verification pending'
              statusVariant = 'outline'
            } else {
              statusLabel = 'Key saved'
              statusVariant = 'secondary'
            }
          }

          return (
            <Card 
              key={provider.provider_key}
              className={`
                transition-all
                ${isConnected 
                  ? `${getProviderBorderColor(provider.provider_key)} shadow-lg` 
                  : ''
                }
              `}
            >
              <CardHeader>
                <div className="flex items-center gap-3">
                  <span className={`text-2xl ${getProviderColor(provider.provider_key)}`}>
                    {getProviderIcon(provider.provider_key)}
                  </span>
                  <div className="flex-1">
                    <CardTitle className="text-lg">{provider.display_name}</CardTitle>
                    <CardDescription className="flex items-center gap-2 mt-1">
                      <Badge variant={statusVariant} className="text-xs">
                        {statusLabel}
                      </Badge>
                      {provider.description && (
                        <span className="text-xs text-muted-foreground">
                          {provider.description}
                        </span>
                      )}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-3">
                {hasKey ? (
                  <>
                    {/* Key Display */}
                    <div className="flex items-center gap-2">
                      <div className="flex-1 px-3 py-2 bg-muted/30 rounded-md font-mono text-sm text-muted-foreground">
                        API Key: {showKeys[provider.provider_key] 
                          ? tether.api_key_preview || '****' 
                          : '****'}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setShowKeys({
                          ...showKeys,
                          [provider.provider_key]: !showKeys[provider.provider_key]
                        })}
                      >
                        {showKeys[provider.provider_key] ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </Button>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleVerify(provider.provider_key)}
                        disabled={isProcessing === 'verifying'}
                        className="gap-2"
                      >
                        {isProcessing === 'verifying' ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Verifying...
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            Verify
                          </>
                        )}
                      </Button>

                      <Button
                        variant={active ? 'secondary' : 'default'}
                        size="sm"
                        onClick={() => handleToggle(provider.provider_key, !active)}
                        disabled={isProcessing === 'toggling' || status !== 'valid'}
                        className="gap-2"
                      >
                        {isProcessing === 'toggling' ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {active ? 'Disconnecting...' : 'Connecting...'}
                          </>
                        ) : (
                          <>
                            {active ? <X className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
                            {active ? 'Disconnect' : 'Connect'}
                          </>
                        )}
                      </Button>

                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRemove(provider.provider_key, provider.display_name)}
                        disabled={!!isProcessing}
                        className="gap-2"
                      >
                        {isProcessing === 'removing' ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Removing...
                          </>
                        ) : (
                          <>
                            <X className="w-4 h-4" />
                            Remove
                          </>
                        )}
                      </Button>
                    </div>

                    {/* Warnings */}
                    {status === 'invalid' && (
                      <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-md">
                        <AlertTriangle className="w-4 h-4 text-destructive mt-0.5" />
                        <div className="text-sm text-destructive">
                          API key verification failed. Please check your key and try again.
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    {/* Add Key Form */}
                    {isEditing ? (
                      <div className="space-y-3">
                        <div className="space-y-2">
                          <Label htmlFor={`key-${provider.provider_key}`}>
                            API Key
                          </Label>
                          <Input
                            id={`key-${provider.provider_key}`}
                            type="password"
                            placeholder={`Enter your ${provider.display_name} API key...`}
                            value={newKey}
                            onChange={(e) => setNewKey(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                handleSaveKey(provider.provider_key)
                              } else if (e.key === 'Escape') {
                                setEditingProvider(null)
                                setNewKey('')
                              }
                            }}
                            autoFocus
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => handleSaveKey(provider.provider_key)}
                            disabled={!newKey.trim() || isProcessing === 'saving'}
                            className="gap-2"
                          >
                            {isProcessing === 'saving' ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Saving...
                              </>
                            ) : (
                              <>
                                <Check className="w-4 h-4" />
                                Save Key
                              </>
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => {
                              setEditingProvider(null)
                              setNewKey('')
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        className="w-full gap-2"
                        onClick={() => setEditingProvider(provider.provider_key)}
                      >
                        <Zap className="w-4 h-4" />
                        Add API Key
                      </Button>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Info Card */}
      <Card className="border-orange-mid/20 bg-card">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Zap className="w-5 h-5 text-orange-light mt-0.5 flex-shrink-0" />
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                <strong className="text-foreground">About Tethers:</strong> API keys are stored 
                securely and never leave your system. Tethers only activate when processing requests.
              </p>
              <p>
                To get API keys, visit:
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <a 
                    href="https://console.anthropic.com" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-light hover:underline"
                  >
                    Claude (Anthropic)
                  </a>
                </li>
                <li>
                  <a 
                    href="https://platform.openai.com/api-keys" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-light hover:underline"
                  >
                    OpenAI
                  </a>
                </li>
                <li>
                  <a 
                    href="https://aistudio.google.com/app/apikey" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-orange-light hover:underline"
                  >
                    Google Gemini
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
