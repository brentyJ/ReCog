import { useState, useEffect } from 'react'
import { Zap, FileUp, Clipboard, Users, Lightbulb, Waypoints, FolderOpen } from 'lucide-react'

// Import all page components
import { SignalExtraction } from './components/pages/SignalExtraction'
import { UploadPage } from './components/pages/UploadPage'
import { PreflightPage } from './components/pages/PreflightPage'
import { EntitiesPage } from './components/pages/EntitiesPage'
import { InsightsPage } from './components/pages/InsightsPage'
import { PatternsPage } from './components/pages/PatternsPage'
import { CasesPage } from './components/pages/CasesPage'

function App() {
  const [activePage, setActivePage] = useState('analyse')
  const [serverStatus, setServerStatus] = useState('checking')
  const [badges, setBadges] = useState({
    cases: 0,
    preflight: 0,
    entities: 0,
    insights: 0,
    patterns: 0,
  })

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

  const navSections = [
    {
      title: 'CASES',
      items: [
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
    }
  ]

  const pageConfig = {
    'cases': { title: 'Cases', icon: FolderOpen },
    'analyse': { title: 'Signal Extraction', icon: Zap },
    'upload': { title: 'Upload Files', icon: FileUp },
    'preflight': { title: 'Preflight Review', icon: Clipboard },
    'entities': { title: 'Entity Management', icon: Users },
    'insights': { title: 'Insights', icon: Lightbulb },
    'patterns': { title: 'Patterns', icon: Waypoints },
  }

  const currentPage = pageConfig[activePage]
  const PageIcon = currentPage.icon

  return (
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
                    onClick={() => setActivePage(item.id)}
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
          <div className="flex items-center gap-2">
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
          {activePage === 'cases' && <CasesPage />}
          {activePage === 'analyse' && <SignalExtraction />}
          {activePage === 'upload' && <UploadPage />}
          {activePage === 'preflight' && <PreflightPage />}
          {activePage === 'entities' && <EntitiesPage />}
          {activePage === 'insights' && <InsightsPage />}
          {activePage === 'patterns' && <PatternsPage />}
        </div>
      </main>
    </div>
  )
}

export default App
