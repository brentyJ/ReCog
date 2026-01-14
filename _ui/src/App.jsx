import { useState, useEffect } from 'react'
import { Zap, FileUp, Clipboard, Users, Lightbulb, Waypoints, FolderOpen, Activity, FileText, Settings, Shield, AlertTriangle } from 'lucide-react'
import { getProvidersStatus } from './lib/api'

// Cypher - Conversational Analysis Interface
import { CypherProvider } from './contexts/CypherContext'
import { Cypher } from './components/cypher'

// Error Boundary for catching rendering errors
import { ErrorBoundary } from './components/ui/error-boundary'

// Import all page components
import { SignalExtraction } from './components/pages/SignalExtraction'
import { UploadPage } from './components/pages/UploadPage'
import { PreflightPage } from './components/pages/PreflightPage'
import { EntitiesPage } from './components/pages/EntitiesPage'
import { InsightsPage } from './components/pages/InsightsPage'
import { PatternsPage } from './components/pages/PatternsPage'
import { CasesPage } from './components/pages/CasesPage'
import { Dashboard } from './components/pages/Dashboard'
import { DocumentViewerPage } from './components/pages/DocumentViewerPage'
import { SettingsPage } from './components/pages/SettingsPage'

function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [serverStatus, setServerStatus] = useState('checking')
  const [providerStatus, setProviderStatus] = useState(null)
  const [badges, setBadges] = useState({
    cases: 0,
    preflight: 0,
    entities: 0,
    insights: 0,
    patterns: 0,
  })

  // Handle hash-based routing
  useEffect(() => {
    function handleHashChange() {
      const hash = window.location.hash
      // Match patterns like #preflight/123 or #cases/456 or just #insights
      const match = hash.match(/^#(\w+)/)
      if (match) {
        const page = match[1]
        // Validate it's a known page
        const validPages = ['dashboard', 'cases', 'analyse', 'upload', 'preflight', 'entities', 'insights', 'patterns', 'document', 'settings']
        if (validPages.includes(page)) {
          setActivePage(page)
          return
        }
      }
      // Default to dashboard if no valid hash (empty hash, back button, etc.)
      setActivePage('dashboard')
    }

    // Check hash on mount
    handleHashChange()

    // Listen for hash changes
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // Check server health
  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health')
        const data = await res.json()
        setServerStatus(data.success ? 'online' : 'offline')
        
        // Update badges from health data
        if (data.database) {
          setBadges({
            cases: data.database.cases || 0,
            preflight: data.database.preflight_sessions || 0,
            entities: data.database.unknown_entities || 0,
            insights: data.database.insights || 0,
            patterns: data.database.patterns || 0,
          })
        }
      } catch (e) {
        setServerStatus('offline')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  // Fetch provider status
  useEffect(() => {
    async function fetchProviderStatus() {
      try {
        const res = await getProvidersStatus()
        setProviderStatus(res?.data || res)
      } catch (e) {
        setProviderStatus(null)
      }
    }
    fetchProviderStatus()
    // Refresh on settings changes
    const handleRefresh = () => fetchProviderStatus()
    window.addEventListener('providers-updated', handleRefresh)
    return () => window.removeEventListener('providers-updated', handleRefresh)
  }, [])

  const navSections = [
    {
      title: 'OVERVIEW',
      items: [
        { id: 'dashboard', label: 'Dashboard', icon: Activity, badge: null },
        { id: 'cases', label: 'Cases', icon: FolderOpen, badge: badges.cases },
      ]
    },
    {
      title: 'ANALYSIS',
      items: [
        { id: 'analyse', label: 'Signal Extraction', icon: Zap, badge: null },
        { id: 'upload', label: 'Upload File', icon: FileUp, badge: null },
      ]
    },
    {
      title: 'WORKFLOW',
      items: [
        { id: 'preflight', label: 'Preflight', icon: Clipboard, badge: badges.preflight },
        { id: 'entities', label: 'Entities', icon: Users, badge: badges.entities },
      ]
    },
    {
      title: 'RESULTS',
      items: [
        { id: 'insights', label: 'Insights', icon: Lightbulb, badge: badges.insights },
        { id: 'patterns', label: 'Patterns', icon: Waypoints, badge: badges.patterns },
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { id: 'settings', label: 'Settings', icon: Settings, badge: null },
      ]
    }
  ]

  const pageConfig = {
    'dashboard': { title: 'Dashboard', icon: Activity },
    'cases': { title: 'Cases', icon: FolderOpen },
    'analyse': { title: 'Signal Extraction', icon: Zap },
    'upload': { title: 'Upload Files', icon: FileUp },
    'preflight': { title: 'Preflight Review', icon: Clipboard },
    'entities': { title: 'Entity Management', icon: Users },
    'insights': { title: 'Insights', icon: Lightbulb },
    'patterns': { title: 'Patterns', icon: Waypoints },
    'document': { title: 'Document Viewer', icon: FileText },
    'settings': { title: 'Settings', icon: Settings },
  }

  const currentPage = pageConfig[activePage]
  const PageIcon = currentPage.icon

  return (
    <CypherProvider caseId={null}>
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-[260px] bg-card border-r border-border flex flex-col fixed top-0 left-0 bottom-0 z-50">
        {/* Logo */}
        <div className="p-6 border-b border-border">
          <a href="/" className="block">
            <img 
              src="/recog-logo.svg" 
              alt="ReCog - Recursive Cognition Engine" 
              className="w-full max-w-[220px] h-auto"
            />
          </a>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto scrollbar-thin">
          {navSections.map((section) => (
            <div key={section.title} className="mb-6">
              <div className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider px-3 mb-2">
                {section.title}
              </div>
              {section.items.map((item) => {
                const Icon = item.icon
                const isActive = activePage === item.id
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActivePage(item.id)
                      window.location.hash = item.id
                    }}
                    className={`
                      w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-all
                      ${isActive 
                        ? 'bg-orange-mid/15 text-orange-light border border-orange-mid/30' 
                        : 'text-muted-foreground hover:bg-card hover:text-foreground border border-transparent hover:border-border'
                      }
                    `}
                  >
                    <Icon className="w-[18px] h-[18px] flex-shrink-0" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {item.badge !== null && item.badge > 0 && (
                      <span className={`
                        px-2 py-0.5 rounded-full text-xs font-mono
                        ${isActive 
                          ? 'bg-orange-mid text-background' 
                          : 'bg-muted text-muted-foreground'
                        }
                      `}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className={`
              w-2 h-2 rounded-full
              ${serverStatus === 'online' ? 'bg-[#5fb3a1] shadow-[0_0_8px_#5fb3a1]' : 
                serverStatus === 'offline' ? 'bg-destructive' : 'bg-muted'}
            `} />
            <span className="text-xs">
              {serverStatus === 'online' ? 'Connected' : 
               serverStatus === 'offline' ? 'Offline' : 'Checking...'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-[260px] flex flex-col">
        {/* Header */}
        <header className="h-14 bg-card border-b border-border flex items-center justify-between px-6 sticky top-0 z-40">
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <PageIcon className="w-5 h-5 text-orange-light" />
            {currentPage.title}
          </h1>
          <div className="flex items-center gap-3">
            {/* Provider Status Indicator */}
            <button
              onClick={() => {
                window.location.hash = '#settings'
              }}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium
                transition-colors cursor-pointer
                ${providerStatus?.configured
                  ? providerStatus?.failover_enabled
                    ? 'bg-emerald-400/10 text-emerald-400 hover:bg-emerald-400/20'
                    : 'bg-amber-400/10 text-amber-400 hover:bg-amber-400/20'
                  : 'bg-red-400/10 text-red-400 hover:bg-red-400/20'
                }
              `}
              title={
                providerStatus?.configured
                  ? `Primary: ${providerStatus.primary_name}${providerStatus.fallback ? ` → Fallback: ${providerStatus.fallback_name}` : ''}`
                  : 'No AI provider configured'
              }
            >
              {providerStatus?.configured ? (
                <>
                  {providerStatus?.failover_enabled ? (
                    <Shield className="w-3.5 h-3.5" />
                  ) : (
                    <Zap className="w-3.5 h-3.5" />
                  )}
                  <span>{providerStatus.primary_name?.split(' ')[0]}</span>
                  {providerStatus?.failover_enabled && (
                    <span className="text-emerald-400/60">+1</span>
                  )}
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>No AI</span>
                </>
              )}
            </button>

            <span className="text-muted-foreground">|</span>

            {/* Cypher trigger */}
            <Cypher />
            <span className="text-muted-foreground">|</span>
            <a
              href="https://ehkolabs.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              EhkoLabs
            </a>
            <span className="text-muted-foreground">•</span>
            <a
              href="/api/info"
              target="_blank"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              API Docs
            </a>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 p-8 overflow-y-auto scrollbar-thin">
          <ErrorBoundary key={activePage}>
            {activePage === 'dashboard' && <Dashboard />}
            {activePage === 'cases' && <CasesPage />}
            {activePage === 'analyse' && <SignalExtraction />}
            {activePage === 'upload' && <UploadPage />}
            {activePage === 'preflight' && <PreflightPage />}
            {activePage === 'entities' && <EntitiesPage />}
            {activePage === 'insights' && <InsightsPage />}
            {activePage === 'patterns' && <PatternsPage />}
            {activePage === 'document' && <DocumentViewerPage />}
            {activePage === 'settings' && <SettingsPage />}
          </ErrorBoundary>
        </div>
      </main>
    </div>
    </CypherProvider>
  )
}

export default App
