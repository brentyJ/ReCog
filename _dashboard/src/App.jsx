import { useState } from 'react'
import { Microscope, Users, Activity } from 'lucide-react'
import TextAnalysis from './pages/TextAnalysis'
import EntityRegistry from './pages/EntityRegistry'

function App() {
  const [activeTab, setActiveTab] = useState('analysis')

  const tabs = [
    { id: 'analysis', name: 'Text Analysis', icon: Microscope },
    { id: 'entities', name: 'Entity Registry', icon: Users },
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-secondary/40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold text-foreground font-mono">
                  RECOG DASHBOARD
                </h1>
                <p className="text-sm text-muted-foreground">
                  Recursive Cognition Engine v0.6.0
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <div className="px-3 py-1 rounded-md bg-success/20 text-success text-sm font-mono border border-success/30">
                ● ONLINE
              </div>
              <div className="text-sm text-muted-foreground font-mono">
                localhost:5100
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-border bg-secondary/20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors
                    border-b-2 ${
                      activeTab === tab.id
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  {tab.name}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'analysis' && <TextAnalysis />}
        {activeTab === 'entities' && <EntityRegistry />}
      </main>
    </div>
  )
}

export default App
