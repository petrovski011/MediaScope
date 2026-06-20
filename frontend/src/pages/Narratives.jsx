import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { User, Building2, MapPin, MessageSquare, Copy, AlertTriangle, Plus, X, BookOpen, Check, Sparkles } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import api from '../lib/api'

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJI_SLOBODA: 'Mediji i sloboda', PROTEST: 'Protest', KULTURA: 'Kultura', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}

const TOPIC_COLORS = [
  '#6366f1', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316',
]

const ALL_TOPICS = Object.keys(TOPIC_LABELS)

const TYPE_ICONS = { person: User, organization: Building2, location: MapPin }
const TYPE_LABELS = { person: 'Osobe', organization: 'Organizacije', location: 'Mesta' }

function EntityTable({ filterParams }) {
  const navigate = useNavigate()
  const [entityType, setEntityType] = useState('')

  const p = new URLSearchParams({ limit: 50, ...filterParams })
  if (entityType) p.set('entity_type', entityType)

  const { data, isLoading } = useQuery({
    queryKey: ['entities', JSON.stringify(filterParams), entityType],
    queryFn: () => api.get(`/entities?${p}`).then(r => r.data),
  })

  const items = data?.items || []
  const maxMentions = items[0]?.total_mentions || 1

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Najčešće pominjani entiteti</h2>
        <div className="flex gap-1">
          {[['', 'Svi'], ['person', 'Osobe'], ['organization', 'Organizacije']].map(([val, label]) => (
            <button key={val} onClick={() => setEntityType(val)}
              className="px-2.5 py-1 rounded text-xs border transition-colors"
              style={{
                borderColor: entityType === val ? '#6366f1' : 'var(--border)',
                color: entityType === val ? '#a5b4fc' : 'var(--text-muted)',
                background: entityType === val ? 'rgba(99,102,241,0.1)' : 'transparent',
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
      ) : items.length === 0 ? (
        <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          Nema podataka — pipeline analiza mora da kompletira entitete
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                {['#', 'Entitet', 'Tip', 'Pominjanja', 'Članci', 'Izvora', 'Citiran'].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left text-xs font-medium"
                    style={{ color: 'var(--text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {items.map((entity, i) => {
                const Icon = TYPE_ICONS[entity.entity_type] || User
                return (
                  <tr key={entity.id}
                  onClick={() => navigate(`/articles?entity_id=${entity.id}&entity_name=${encodeURIComponent(entity.name)}`)}
                  className="hover:bg-white/[0.02] transition-colors cursor-pointer">
                    <td className="pl-4 pr-2 py-3 text-xs w-8 tabular-nums"
                      style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <Icon size={13} style={{ color: 'var(--text-muted)' }} />
                        <div>
                          <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                            {entity.name}
                          </div>
                          {entity.is_political_actor && (
                            <div className="text-xs" style={{ color: '#f59e0b' }}>politički akter</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-xs px-2 py-0.5 rounded"
                        style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                        {TYPE_LABELS[entity.entity_type] || entity.entity_type}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
                          <div className="h-full rounded-full"
                            style={{ width: `${entity.total_mentions / maxMentions * 100}%`, background: '#6366f1' }} />
                        </div>
                        <span className="text-xs tabular-nums" style={{ color: 'var(--text-primary)' }}>
                          {entity.total_mentions}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      {entity.article_count}
                    </td>
                    <td className="px-3 py-3 text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                      {entity.source_count}
                    </td>
                    <td className="px-3 py-3">
                      {entity.quoted_count > 0 && (
                        <div className="flex items-center gap-1 text-xs" style={{ color: '#22c55e' }}>
                          <MessageSquare size={11} />
                          {entity.quoted_count}x
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function TopicTimeline({ filterParams }) {
  const [selectedTopics, setSelectedTopics] = useState([
    'POLITIKA', 'EU_INTEGRACIJE', 'KOSOVO', 'EKONOMIJA', 'PROTEST',
  ])

  const topicParam = selectedTopics.join(',')
  const p = new URLSearchParams({ ...filterParams })
  if (topicParam) p.set('topics', topicParam)

  const { data, isLoading } = useQuery({
    queryKey: ['topics-timeline', JSON.stringify(filterParams), topicParam],
    queryFn: () => api.get(`/topics/timeline?${p}`).then(r => r.data),
    enabled: selectedTopics.length > 0,
  })

  const chartData = useMemo(() => {
    if (!data?.items?.length) return []
    const byDate = {}
    data.items.forEach(({ date, topic, count }) => {
      if (!byDate[date]) byDate[date] = { date }
      byDate[date][topic] = count
    })
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  }, [data])

  const toggleTopic = (t) =>
    setSelectedTopics(prev =>
      prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]
    )

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>
          Tematski trendovi po danu
        </h2>
        <div className="flex flex-wrap gap-1.5">
          {ALL_TOPICS.map((t, i) => {
            const active = selectedTopics.includes(t)
            const color = TOPIC_COLORS[i % TOPIC_COLORS.length]
            return (
              <button key={t} onClick={() => toggleTopic(t)}
                className="px-2 py-0.5 rounded text-xs border transition-all"
                style={{
                  borderColor: active ? color : 'var(--border)',
                  color: active ? color : 'var(--text-muted)',
                  background: active ? `${color}18` : 'transparent',
                }}>
                {TOPIC_LABELS[t]}
              </button>
            )
          })}
        </div>
      </div>

      <div className="p-4">
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
            Učitavanje...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
            Nema podataka za izabrani period i teme
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={chartData} margin={{ left: 0, right: 8 }}>
              <XAxis dataKey="date"
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                tickFormatter={d => d.slice(5)}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 11,
                }}
                labelStyle={{ color: 'var(--text-primary)', marginBottom: 4 }}
                formatter={(val, name) => [val, TOPIC_LABELS[name] || name]}
              />
              {selectedTopics.map((t) => {
                const idx = ALL_TOPICS.indexOf(t)
                const color = TOPIC_COLORS[idx % TOPIC_COLORS.length]
                return (
                  <Area key={t} type="monotone" dataKey={t}
                    stroke={color}
                    fill={`${color}15`}
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls
                  />
                )
              })}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

function CoordinationPanel({ filterParams }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState('copypaste')

  const cpParams = new URLSearchParams({ threshold: 0.7, limit: 30, ...filterParams })
  const { data: cpData, isLoading: cpLoading } = useQuery({
    queryKey: ['coordination-cp', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/copy-paste?${cpParams}`).then(r => r.data),
  })

  const fmParams = new URLSearchParams({ min_sources: 3, limit: 20, ...filterParams })
  const { data: fmData, isLoading: fmLoading } = useQuery({
    queryKey: ['coordination-framing', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/framing?${fmParams}`).then(r => r.data),
  })

  const cpPairs = cpData?.pairs || []
  const fmGroups = fmData?.groups || []
  const fmSignals = fmGroups.filter(g => g.coordination_signal)

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Koordinacioni signali</h2>
        </div>
        <div className="flex gap-1">
          {[
            ['copypaste', `Copy-paste (${cpPairs.length})`],
            ['framing', `Framing (${fmGroups.length})`],
          ].map(([val, label]) => (
            <button key={val} onClick={() => setTab(val)}
              className="px-2.5 py-1 rounded text-xs border transition-colors"
              style={{
                borderColor: tab === val ? '#f59e0b' : 'var(--border)',
                color: tab === val ? '#fbbf24' : 'var(--text-muted)',
                background: tab === val ? 'rgba(245,158,11,0.1)' : 'transparent',
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'copypaste' && (
        <div>
          {cpLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
          ) : cpPairs.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema copy-paste parova (threshold ≥70%)
            </div>
          ) : (
            <div className="divide-y overflow-auto" style={{ borderColor: 'var(--border)', maxHeight: 400 }}>
              {cpPairs.map((pair, i) => (
                <div key={i} className="px-4 py-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: pair.similarity_score >= 0.95 ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                        color: pair.similarity_score >= 0.95 ? '#fca5a5' : '#fbbf24',
                      }}>
                      {Math.round(pair.similarity_score * 100)}% podudaranje
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {pair.article1.published_at?.slice(0, 10)}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {[pair.article1, pair.article2].map((a, j) => (
                      <div key={j} onClick={() => navigate(`/articles/${a.id}`)}
                        className="flex items-center gap-2 cursor-pointer hover:bg-white/[0.02] rounded p-1.5 -mx-1.5 transition-colors">
                        <span className="text-xs px-2 py-0.5 rounded shrink-0"
                          style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                          {a.source_id}
                        </span>
                        <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                          {a.title}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
            {cpData?.methodology_note}
          </div>
        </div>
      )}

      {tab === 'framing' && (
        <div>
          {fmLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
          ) : fmGroups.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema framing koordinacije (min. 3 izvora o istoj temi isti dan)
            </div>
          ) : (
            <div className="divide-y overflow-auto" style={{ borderColor: 'var(--border)', maxHeight: 400 }}>
              {fmGroups.map((g, i) => (
                <div key={i} className="px-4 py-3 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {ALL_TOPICS.includes(g.topic) ? TOPIC_LABELS[g.topic] : g.topic}
                      </span>
                      {g.coordination_signal && (
                        <span className="text-xs px-1.5 py-0.5 rounded"
                          style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}>
                          signal
                        </span>
                      )}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {g.date} · {g.source_count} izvora · {g.direction}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {g.sources.map(s => (
                        <span key={s} className="text-xs px-1.5 py-0.5 rounded"
                          style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm tabular-nums" style={{
                      color: g.avg_political_score > 0.3 ? '#ef4444' : g.avg_political_score < -0.3 ? '#3b82f6' : '#6b7280'
                    }}>
                      {g.avg_political_score > 0 ? '+' : ''}{g.avg_political_score.toFixed(2)} avg
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      raspon ±{g.score_range.toFixed(2)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
            {fmData?.methodology_note}
          </div>
        </div>
      )}
    </div>
  )
}

const NARRATIVE_TYPE_LABELS = {
  systemic: 'Sistemski', thematic: 'Tematski', pro_vlada: 'Pro-vladini', opozicioni: 'Opozicioni',
}

function NarrativesPanel() {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'researcher'
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', narrative_type: 'thematic', description: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['narratives'],
    queryFn: () => api.get('/narratives').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: body => api.post('/narratives', body).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries(['narratives'])
      setShowCreate(false)
      setForm({ name: '', narrative_type: 'thematic', description: '' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: id => api.delete(`/narratives/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries(['narratives']),
  })

  const validateMutation = useMutation({
    mutationFn: id => api.post(`/narratives/${id}/validate`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries(['narratives']),
  })

  const narratives = data?.narratives || []

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <BookOpen size={13} style={{ color: 'var(--text-muted)' }} />
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Definisani narativi</h2>
          {narratives.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
              {narratives.length}
            </span>
          )}
        </div>
        {canEdit && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded border transition-colors hover:bg-white/[0.04]"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <Plus size={12} /> Dodaj narrativ
          </button>
        )}
      </div>

      {showCreate && (
        <div className="px-4 py-4 border-b space-y-3" style={{ borderColor: 'var(--border)', background: 'var(--bg-elevated)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Novi narrativ</span>
            <button onClick={() => setShowCreate(false)}><X size={13} style={{ color: 'var(--text-muted)' }} /></button>
          </div>
          <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Naziv narativa (npr. 'EU nameće uslove Srbiji')"
            className="w-full px-3 py-2 rounded text-sm border outline-none"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            placeholder="Opis i ključne reči (opciono)"
            className="w-full px-3 py-2 rounded text-sm border outline-none"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          <div className="flex items-center gap-3">
            <select value={form.narrative_type} onChange={e => setForm(f => ({ ...f, narrative_type: e.target.value }))}
              className="px-3 py-2 rounded text-sm border"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}>
              <option value="thematic">Tematski</option>
              <option value="systemic">Sistemski</option>
            </select>
            <button onClick={() => createMutation.mutate(form)}
              disabled={!form.name || createMutation.isPending}
              className="px-4 py-2 rounded text-sm font-medium disabled:opacity-50"
              style={{ background: '#3b82f6', color: '#fff' }}>
              {createMutation.isPending ? 'Čuvanje...' : 'Sačuvaj'}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="px-4 py-6 text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
      ) : narratives.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          Nema definisanih narativa. {canEdit ? 'Dodajte prvi narrativ pomoću dugmeta iznad.' : ''}
        </div>
      ) : (
        <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
          {narratives.map(n => (
            <div key={n.id} className="flex items-center gap-4 px-4 py-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{n.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded shrink-0"
                    style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                    {NARRATIVE_TYPE_LABELS[n.narrative_type] || n.narrative_type}
                  </span>
                  {!n.is_validated && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0" style={{ background: '#f59e0b33', color: '#f59e0b' }}>
                      nevalidiran
                    </span>
                  )}
                </div>
                {n.description && (
                  <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>{n.description}</p>
                )}
              </div>
              <span className="text-sm tabular-nums shrink-0" style={{ color: 'var(--text-secondary)' }}>
                {n.article_count} članaka
              </span>
              {canEdit && !n.is_validated && (
                <button onClick={() => validateMutation.mutate(n.id)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded border shrink-0 hover:bg-white/[0.04]"
                  style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                  <Check size={12} /> Validiraj
                </button>
              )}
              {canEdit && (
                <button onClick={() => deleteMutation.mutate(n.id)}
                  className="text-xs hover:text-red-400 transition-colors shrink-0"
                  style={{ color: 'var(--text-muted)' }}>
                  <X size={13} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        Članci se mapiraju na <strong>validirane</strong> narative AI-jem tokom analize. Intenzitet se agregira dnevno u 06:00.
      </div>
    </div>
  )
}

function NarrativeProposalsPanel() {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'researcher'
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: ['narrative-proposals'],
    queryFn: () => api.get('/narratives/proposals?status=pending').then(r => r.data.proposals),
    enabled: canEdit,
  })
  const approve = useMutation({
    mutationFn: id => api.post(`/narratives/proposals/${id}/approve`),
    onSuccess: () => { qc.invalidateQueries(['narrative-proposals']); qc.invalidateQueries(['narratives']) },
  })
  const reject = useMutation({
    mutationFn: id => api.post(`/narratives/proposals/${id}/reject`),
    onSuccess: () => qc.invalidateQueries(['narrative-proposals']),
  })

  const proposals = data || []
  if (!canEdit || proposals.length === 0) return null

  return (
    <div className="rounded-xl border overflow-hidden mb-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
        <Sparkles size={13} style={{ color: '#f59e0b' }} />
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>AI predlozi narativa</h2>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#f59e0b33', color: '#f59e0b' }}>{proposals.length}</span>
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {proposals.map(p => (
          <div key={p.id} className="px-4 py-3 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                  {NARRATIVE_TYPE_LABELS[p.narrative_type] || p.narrative_type}
                </span>
                {p.occurrences > 1 && <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>×{p.occurrences}</span>}
              </div>
              {p.description && <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{p.description}</p>}
              {p.supporting_text && <p className="text-xs italic mt-1" style={{ color: 'var(--text-muted)' }}>"{p.supporting_text}"</p>}
            </div>
            <div className="flex gap-1.5 shrink-0">
              <button onClick={() => approve.mutate(p.id)} disabled={approve.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]" style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                <Check size={12} /> Prihvati
              </button>
              <button onClick={() => reject.mutate(p.id)} disabled={reject.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]" style={{ borderColor: 'var(--border)', color: '#ef4444' }}>
                <X size={12} /> Odbij
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Narratives() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          Narativi i entiteti
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Ko se pominje, u kojim kontekstima i kako se teme menjaju kroz vreme
        </p>
      </div>

      <NarrativeProposalsPanel />
      <NarrativesPanel />
      <TopicTimeline filterParams={filterParams} />
      <CoordinationPanel filterParams={filterParams} />
      <EntityTable filterParams={filterParams} />
    </div>
  )
}
