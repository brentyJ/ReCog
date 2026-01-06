import { useState, useEffect } from 'react'
import { Users, UserPlus, AlertCircle, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { LoadingState } from '@/components/ui/loading-state'
import { EmptyState } from '@/components/ui/empty-state'
import { StatCard, StatGrid } from '@/components/ui/stat-card'
import { getEntities, getUnknownEntities, updateEntity, getEntityStats } from '@/lib/api'

export function EntitiesPage() {
  const [entities, setEntities] = useState([])
  const [unknownEntities, setUnknownEntities] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [isIdentifyDialogOpen, setIsIdentifyDialogOpen] = useState(false)
  const [identifyForm, setIdentifyForm] = useState({
    display_name: '',
    relationship: '',
    anonymise: false,
    placeholder_name: '',
  })

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [entitiesData, unknownData, statsData] = await Promise.all([
        getEntities({ confirmed: true }),
        getUnknownEntities(),
        getEntityStats(),
      ])
      setEntities(entitiesData.entities || [])
      setUnknownEntities(unknownData.entities || [])
      setStats(statsData)
    } catch (error) {
      console.error('Failed to load entities:', error)
    } finally {
      setLoading(false)
    }
  }

  function openIdentifyDialog(entity) {
    setSelectedEntity(entity)
    setIdentifyForm({
      display_name: entity.raw_value,
      relationship: '',
      anonymise: false,
      placeholder_name: '',
    })
    setIsIdentifyDialogOpen(true)
  }

  async function handleIdentify() {
    try {
      await updateEntity(selectedEntity.id, identifyForm)
      setIsIdentifyDialogOpen(false)
      await loadData()
    } catch (error) {
      alert(`Failed to identify entity: ${error.message}`)
    }
  }

  const relationshipTypes = [
    'family',
    'work',
    'friend',
    'medical',
    'professional',
    'other',
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <Users className="w-6 h-6 text-orange-light" />
          Entity Management
        </h2>
        <p className="text-muted-foreground">
          Manage people, organizations, and entities detected in your documents
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <StatGrid>
          <StatCard value={stats.total_entities} label="Total Entities" color="primary" />
          <StatCard value={stats.confirmed} label="Confirmed" color="success" />
          <StatCard value={stats.unknown} label="Need ID" color="warning" />
          <StatCard value={stats.anonymised || 0} label="Anonymised" color="secondary" />
        </StatGrid>
      )}

      {/* Unknown Entities Queue */}
      {unknownEntities.length > 0 && (
        <Card className="border-orange-mid/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-orange-light" />
              Entities Needing Identification
            </CardTitle>
            <CardDescription>
              {unknownEntities.length} entities need to be identified before processing
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {unknownEntities.map((entity) => (
                <div
                  key={entity.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="w-20 justify-center">
                      {entity.entity_type}
                    </Badge>
                    <div>
                      <div className="font-mono font-semibold">{entity.raw_value}</div>
                      <div className="text-sm text-muted-foreground">
                        {entity.occurrence_count} occurrence{entity.occurrence_count !== 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => openIdentifyDialog(entity)}
                    className="gap-2"
                  >
                    <UserPlus className="w-4 h-4" />
                    Identify
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirmed Entities */}
      <Card>
        <CardHeader>
          <CardTitle>Entity Registry</CardTitle>
          <CardDescription>
            {entities.length} confirmed entities
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <LoadingState message="Loading entities..." size="lg" />
          ) : entities.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No confirmed entities yet"
              description="Entities will appear here once you've identified them."
            />
          ) : (
            <div className="space-y-2">
              {entities.map((entity) => (
                <div
                  key={entity.id}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="secondary" className="w-20 justify-center">
                      {entity.entity_type}
                    </Badge>
                    <div>
                      <div className="font-semibold">
                        {entity.display_name || entity.raw_value}
                        {entity.anonymise_in_prompts && (
                          <Badge variant="outline" className="ml-2 text-xs">
                            Anonymised
                          </Badge>
                        )}
                      </div>
                      {entity.relationship && (
                        <div className="text-sm text-muted-foreground">
                          {entity.relationship}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {entity.occurrence_count} mentions
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Identify Dialog */}
      <Dialog open={isIdentifyDialogOpen} onOpenChange={setIsIdentifyDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Identify Entity</DialogTitle>
            <DialogDescription>
              Provide information about this entity
            </DialogDescription>
          </DialogHeader>

          {selectedEntity && (
            <div className="space-y-4">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Raw Value</div>
                <div className="font-mono font-semibold">{selectedEntity.raw_value}</div>
              </div>

              <div className="space-y-2">
                <Label>Display Name</Label>
                <Input
                  value={identifyForm.display_name}
                  onChange={(e) => setIdentifyForm({...identifyForm, display_name: e.target.value})}
                  placeholder="How should this entity appear?"
                />
              </div>

              <div className="space-y-2">
                <Label>Relationship</Label>
                <Select
                  value={identifyForm.relationship}
                  onValueChange={(value) => setIdentifyForm({...identifyForm, relationship: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select relationship type" />
                  </SelectTrigger>
                  <SelectContent>
                    {relationshipTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="anonymise"
                  checked={identifyForm.anonymise}
                  onChange={(e) => setIdentifyForm({...identifyForm, anonymise: e.target.checked})}
                  className="w-4 h-4"
                />
                <Label htmlFor="anonymise">Anonymise in LLM prompts</Label>
              </div>

              {identifyForm.anonymise && (
                <div className="space-y-2">
                  <Label>Placeholder Name</Label>
                  <Input
                    value={identifyForm.placeholder_name}
                    onChange={(e) => setIdentifyForm({...identifyForm, placeholder_name: e.target.value})}
                    placeholder="e.g., Person A, Colleague 1"
                  />
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <Button onClick={handleIdentify} className="flex-1 gap-2">
                  <Check className="w-4 h-4" />
                  Identify
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setIsIdentifyDialogOpen(false)}
                  className="flex-1 gap-2"
                >
                  <X className="w-4 h-4" />
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
