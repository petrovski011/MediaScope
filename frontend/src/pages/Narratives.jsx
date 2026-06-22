import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { User, Building2, MapPin, MessageSquare, Copy, AlertTriangle, Plus, X, BookOpen, Check, Sparkles, ChevronLeft, ChevronRight, RotateCcw, Search, Pencil, Quote, TrendingUp } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import api from '../lib/api'

function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between px-4 py-2 border-t text-xs" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
      <span>Stranica {page} od {pages}</span>
      <div className="flex gap-1">
        <button onClick={() => onChange(p => Math.max(1, p - 1))} disabled={page === 1}
          className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronLeft size={14} /></button>
        <button onClick={() => onChange(p => Math.min(pages, p + 1))} disabled={page >= pages}
          className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronRight size={14} /></button>
      </div>
    </div>
  )
}

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJSKE_SLOBODE: 'Medijske slobode', MEDIJI_SLOBODA: 'Medijske slobode',
  PROTEST: 'Protest', KULTURA: 'Kultura', ZABAVA_I_ESTRADA: 'Zabava i estrada', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}

const ALL_TOPICS = Object.keys(TOPIC_LABELS)

const TYPE_ICONS = { person: User, organization: Building2, location: MapPin }
const TYPE_LABELS = { person: 'Osobe', organization: 'Organizacije', location: 'Mesta' }

function SentimentDot({ value }) {
  if (value == null) return <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ background: 'var(--text-muted)' }} title="sentiment nepoznat" />
  const color = value > 0.2 ? '#22c55e' : value < -0.2 ? '#ef4444' : '#94a3b8'
  const label = value > 0.2 ? 'pozitivno' : value < -0.2 ? 'negativno' : 'neutralno'
  return <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ background: color }} title={`${label} (${value.toFixed(2)})`} />
}

function CitationsModal({ entity, onClose }) {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['entity-mentions', entity.id],
    queryFn: () => api.get(`/entities/${entity.id}/mentions?limit=30`).then(r => r.data),
  })
  const mentions = data?.mentions || []
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="rounded-xl border w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }} onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <Quote size={14} style={{ color: '#f59e0b' }} />
            <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Citati: {entity.name}</h3>
          </div>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="overflow-y-auto divide-y" style={{ borderColor: 'var(--border)' }}>
          {isLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje…</div>
          ) : mentions.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nema sačuvanih citata za ovaj entitet.</div>
          ) : mentions.map((m, i) => (
            <div key={i} className="px-4 py-3 cursor-pointer hover:bg-white/[0.02] transition-colors"
              onClick={() => navigate(`/articles/${m.article_id}`)}>
              <div className="flex items-center gap-2 mb-1">
                <SentimentDot value={m.sentiment} />
                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>{m.source_id}</span>
                {m.published_at && <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{new Date(m.published_at).toLocaleDateString('sr-RS')}</span>}
              </div>
              {m.context_snippet && <p className="text-xs italic leading-snug" style={{ color: 'var(--text-secondary)' }}>"{m.context_snippet}"</p>}
              <p className="text-xs mt-0.5 leading-snug" style={{ color: 'var(--text-primary)' }}>{m.title}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function NarrativeCitationsModal({ narrative, onClose }) {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['narrative-citations', narrative.id],
    queryFn: () => api.get(`/narratives/${narrative.id}/citations?limit=30`).then(r => r.data),
  })
  const citations = data?.citations || []
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="rounded-xl border w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }} onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <Quote size={14} style={{ color: '#8b5cf6' }} />
            <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Citati: {narrative.name}</h3>
          </div>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="overflow-y-auto divide-y" style={{ borderColor: 'var(--border)' }}>
          {isLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje…</div>
          ) : citations.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema sačuvanih citata za ovaj narativ. Citati se popunjavaju pri AI analizi novih članaka.
            </div>
          ) : citations.map((c, i) => (
            <div key={i} className="px-4 py-3 cursor-pointer hover:bg-white/[0.02] transition-colors"
              onClick={() => navigate(`/articles/${c.article_id}`)}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                  {c.source_id}
                </span>
                {c.published_at && (
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {new Date(c.published_at).toLocaleDateString('sr-RS')}
                  </span>
                )}
                {c.confidence != null && (
                  <span className="text-[10px] ml-auto" style={{ color: 'var(--text-muted)' }}>
                    pouzdanost: {Math.round(c.confidence * 100)}%
                  </span>
                )}
              </div>
              {c.supporting_text && (
                <p className="text-xs italic leading-relaxed mb-1" style={{ color: 'var(--text-secondary)' }}>
                  "{c.supporting_text}"
                </p>
              )}
              <p className="text-xs leading-snug" style={{ color: 'var(--text-muted)' }}>{c.title}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function EntityEditModal({ entity, onClose }) {
  const qc = useQueryClient()
  const [name, setName] = useState(entity.name)
  const [type, setType] = useState(entity.entity_type)
  const [isActor, setIsActor] = useState(!!entity.is_political_actor)
  const save = useMutation({
    mutationFn: () => api.patch(`/entities/${entity.id}`, { name, entity_type: type, is_political_actor: isActor }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['entities'] }); onClose() },
  })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={onClose}>
      <div className="rounded-xl border w-full max-w-md" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }} onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <h3 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Izmena entiteta</h3>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Naziv</label>
            <input value={name} onChange={e => setName(e.target.value)}
              className="w-full px-2 py-1.5 rounded text-sm border outline-none"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          </div>
          <div>
            <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Tip</label>
            <select value={type} onChange={e => setType(e.target.value)}
              className="w-full px-2 py-1.5 rounded text-sm border outline-none"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}>
              <option value="person">Osoba</option>
              <option value="organization">Organizacija</option>
              <option value="location">Lokacija</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={isActor} onChange={e => setIsActor(e.target.checked)} />
            Politički akter
          </label>
        </div>
        <div className="px-4 py-3 border-t flex justify-end gap-2" style={{ borderColor: 'var(--border)' }}>
          <button onClick={onClose} className="px-3 py-1.5 rounded text-sm border" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>Otkaži</button>
          <button onClick={() => save.mutate()} disabled={save.isPending || !name.trim()}
            className="px-3 py-1.5 rounded text-sm font-medium" style={{ background: 'var(--accent)', color: 'white' }}>
            {save.isPending ? 'Čuvam…' : 'Sačuvaj'}
          </button>
        </div>
      </div>
    </div>
  )
}

function EntityTable({ filterParams }) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'researcher'
  const [citeEntity, setCiteEntity] = useState(null)
  const [editEntity, setEditEntity] = useState(null)
  const [entityType, setEntityType] = useState('')
  const [sortBy, setSortBy] = useState('total_mentions')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PER_PAGE = 10

  const p = new URLSearchParams({ per_page: PER_PAGE, page, sort_by: sortBy, ...filterParams })
  if (entityType) p.set('entity_type', entityType)
  if (search) p.set('search', search)

  const { data, isLoading } = useQuery({
    queryKey: ['entities', JSON.stringify(filterParams), entityType, sortBy, search, page],
    queryFn: () => api.get(`/entities?${p}`).then(r => r.data),
    keepPreviousData: true,
  })

  const items = data?.items || []
  const pages = data?.pages || 1
  const total = data?.total || 0
  const maxMentions = items[0]?.total_mentions || 1

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center justify-between gap-3" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-medium shrink-0" style={{ color: 'var(--text-primary)' }}>
          Entiteti {total > 0 && <span className="text-xs ml-1" style={{ color: 'var(--text-muted)' }}>{total}</span>}
        </h2>
        <div className="flex items-center gap-2 flex-1">
          <div className="relative">
            <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
              placeholder="Pretraži…" className="pl-6 pr-2 py-1 rounded text-xs border outline-none w-32"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          </div>
          <select value={sortBy} onChange={e => { setSortBy(e.target.value); setPage(1) }}
            className="px-2 py-1 rounded text-xs border outline-none"
            style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <option value="total_mentions">Pominjanja</option>
            <option value="article_count">Članci</option>
            <option value="source_count">Izvori</option>
            <option value="name">Naziv</option>
          </select>
          <div className="flex gap-1 ml-auto">
            {[['', 'Svi'], ['person', 'Osobe'], ['organization', 'Org.']].map(([val, label]) => (
              <button key={val} onClick={() => { setEntityType(val); setPage(1) }}
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
                {['#', 'Entitet', 'Tip', 'Pominjanja', 'Članci', 'Izvora', 'Citiran', ''].map((h, hi) => (
                  <th key={hi} className="px-3 py-2.5 text-left text-xs font-medium"
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
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5">
                        <button onClick={e => { e.stopPropagation(); setCiteEntity(entity) }}
                          title="Citati (kontekst pominjanja)"
                          className="p-1 rounded border hover:bg-white/[0.04]"
                          style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                          <Quote size={12} />
                        </button>
                        {canEdit && (
                          <button onClick={e => { e.stopPropagation(); setEditEntity(entity) }}
                            title="Izmeni entitet"
                            className="p-1 rounded border hover:bg-white/[0.04]"
                            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                            <Pencil size={12} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} pages={pages} onChange={setPage} />
      {citeEntity && <CitationsModal entity={citeEntity} onClose={() => setCiteEntity(null)} />}
      {editEntity && <EntityEditModal entity={editEntity} onClose={() => setEditEntity(null)} />}
    </div>
  )
}


const CP_PER_PAGE = 5
const FM_PER_PAGE = 5

function CoordinationPanel({ filterParams }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState('copypaste')
  const [cpPage, setCpPage] = useState(1)
  const [fmPage, setFmPage] = useState(1)

  const cpParams = new URLSearchParams({ threshold: 0.7, limit: 50, ...filterParams })
  const { data: cpData, isLoading: cpLoading } = useQuery({
    queryKey: ['coordination-cp', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/copy-paste?${cpParams}`).then(r => r.data),
  })

  const fmParams = new URLSearchParams({ min_sources: 2, limit: 50, ...filterParams })
  const { data: fmData, isLoading: fmLoading } = useQuery({
    queryKey: ['coordination-framing', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/framing?${fmParams}`).then(r => r.data),
  })

  const cpPairs = cpData?.groups || []
  const fmGroups = fmData?.groups || []
  const fmSignals = fmGroups.filter(g => g.coordination_signal)

  const cpPages = Math.max(1, Math.ceil(cpPairs.length / CP_PER_PAGE))
  const fmPages = Math.max(1, Math.ceil(fmGroups.length / FM_PER_PAGE))
  const cpSlice = cpPairs.slice((cpPage - 1) * CP_PER_PAGE, cpPage * CP_PER_PAGE)
  const fmSlice = fmGroups.slice((fmPage - 1) * FM_PER_PAGE, fmPage * FM_PER_PAGE)

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
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {cpSlice.map((group, i) => (
                <div key={i} className="px-4 py-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: group.max_similarity >= 0.95 ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)',
                        color: group.max_similarity >= 0.95 ? '#fca5a5' : '#fbbf24',
                      }}>
                      {Math.round(group.max_similarity * 100)}% podudaranje
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded"
                      style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                      {group.size} {group.size === 1 ? 'medij' : 'medija'}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {group.articles[0]?.published_at?.slice(0, 10)}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {group.articles.map((a, j) => (
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
          <Pagination page={cpPage} pages={cpPages} onChange={setCpPage} />
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
              Nema framing koordinacije (min. 2 izvora o istoj temi isti dan)
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {fmSlice.map((g, i) => (
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
          <Pagination page={fmPage} pages={fmPages} onChange={setFmPage} />
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
  const [citeNarrative, setCiteNarrative] = useState(null)

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

  const revertMutation = useMutation({
    mutationFn: id => api.patch(`/narratives/${id}`, { is_validated: false }),
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

      <div className="px-4 py-2.5 border-b text-xs leading-relaxed" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)', background: 'var(--bg-elevated)' }}>
        <strong style={{ color: 'var(--text-secondary)' }}>Šta je definicija narativa?</strong>{' '}
        Narrativ je obrazac koji AI pronalazi u člancima. Ovde definišete katalog narativa koji vas zanima — svaki novi članak se tada automatski mapira <em>samo na odobrene narative</em> iz ovog kataloga.
        {' '}<strong style={{ color: 'var(--text-secondary)' }}>Tok:</strong>{' '}
        AI predlaže narative (vidljivi u "Predlozi") → istraživač odobrava ili ručno dodaje → od tog trenutka svaki članak dobija confidence skor + citat za svaki aktivan narrativ.
        Nevalidovani narativi se ne koriste u analizi.
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
              <button onClick={() => setCiteNarrative(n)}
                className="p-1 rounded border hover:bg-white/[0.04] shrink-0"
                title="Citati iz članaka"
                style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                <Quote size={12} />
              </button>
              {canEdit && !n.is_validated && (
                <button onClick={() => validateMutation.mutate(n.id)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded border shrink-0 hover:bg-white/[0.04]"
                  style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                  <Check size={12} /> Validiraj
                </button>
              )}
              {canEdit && n.is_validated && (
                <button onClick={() => revertMutation.mutate(n.id)} disabled={revertMutation.isPending}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded border shrink-0 hover:bg-white/[0.04] disabled:opacity-50"
                  style={{ borderColor: 'var(--border)', color: '#f59e0b' }}
                  title="Vrati u predloge (poništi validaciju)">
                  <RotateCcw size={11} />
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
      {citeNarrative && <NarrativeCitationsModal narrative={citeNarrative} onClose={() => setCiteNarrative(null)} />}
    </div>
  )
}

const PROPOSALS_PER_PAGE = 5

function NarrativeProposalsPanel() {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'researcher'
  const qc = useQueryClient()
  const [page, setPage] = useState(1)

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

  const pages = Math.ceil(proposals.length / PROPOSALS_PER_PAGE)
  const slice = proposals.slice((page - 1) * PROPOSALS_PER_PAGE, page * PROPOSALS_PER_PAGE)

  return (
    <section className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={15} style={{ color: '#f59e0b' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            AI predlozi narativa ({proposals.length})
          </h2>
        </div>
        {pages > 1 && (
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1 rounded border disabled:opacity-30"
              style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
              <ChevronLeft size={13} />
            </button>
            <span className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>{page}/{pages}</span>
            <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
              className="p-1 rounded border disabled:opacity-30"
              style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
              <ChevronRight size={13} />
            </button>
          </div>
        )}
      </div>
      <div className="space-y-2">
        {slice.map(p => (
          <div key={p.id} className="rounded-xl border p-3 flex items-start justify-between gap-3"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                  {NARRATIVE_TYPE_LABELS[p.narrative_type] || p.narrative_type}
                </span>
                <a
                  href={`/articles?narrative_cluster_id=${p.id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] px-1.5 py-0.5 rounded border hover:bg-white/[0.04] transition-colors"
                  style={{ borderColor: 'var(--border)', color: '#a5b4fc' }}
                  title="Otvori listu članaka obuhvaćenih ovim narativom">
                  {p.occurrences} čl. →
                </a>
              </div>
              {p.description && <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{p.description}</p>}
              {p.supporting_text && <p className="text-xs italic mt-1" style={{ color: 'var(--text-muted)' }}>"{p.supporting_text}"</p>}
            </div>
            <div className="flex gap-1.5 shrink-0">
              <button onClick={() => approve.mutate(p.id)} disabled={approve.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]"
                style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                <Check size={12} /> Prihvati
              </button>
              <button onClick={() => reject.mutate(p.id)} disabled={reject.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]"
                style={{ borderColor: 'var(--border)', color: '#ef4444' }}>
                <X size={12} /> Odbij
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

const INTRADAY_COLORS = ['#6366f1', '#f59e0b', '#22c55e', '#ef4444', '#06b6d4', '#a855f7', '#ec4899', '#84cc16']

function IntradayPanel({ filterParams }) {
  const [tab, setTab] = useState('topics')

  const { data: topicData } = useQuery({
    queryKey: ['intraday-topics', filterParams],
    queryFn: () => api.get(`/intraday?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })
  const { data: narrData } = useQuery({
    queryKey: ['intraday-narratives', filterParams],
    queryFn: () => api.get(`/intraday/narratives?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })

  const topics = topicData?.topics || []
  const topicsHasData = topicData?.hourly?.some(h => topics.some(t => h[t]))
  const topNarr = narrData?.top_narratives || []
  const narrHasData = topNarr.length > 0 && narrData?.by_hour?.some(h => topNarr.some(n => h[n]))
  const DOW_LABELS = ["Ned", "Pon", "Uto", "Sre", "Čet", "Pet", "Sub"]
  const heatmap = narrData?.heatmap || []
  const maxHeat = Math.max(1, ...heatmap.map(h => h.count))

  const TABS = [
    { key: 'topics', label: 'Teme/sat' },
    { key: 'narr_hour', label: 'Narativi/sat' },
    { key: 'narr_dow', label: 'Dan u nedelji' },
    { key: 'heatmap', label: 'Heatmap' },
  ]

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Intra-day distribucija</h2>
        <div className="ml-auto flex gap-1">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className="text-xs px-2.5 py-1 rounded-lg transition-colors"
              style={{
                background: tab === t.key ? 'var(--accent)' : 'var(--bg-elevated)',
                color: tab === t.key ? 'white' : 'var(--text-muted)',
              }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
          Samo članci sa tačnim vremenom objave. Narativi: default prozor 30 dana.
          {narrData?.intraday_note?.excluded_sources?.length > 0 &&
            ` Isključeni: ${narrData.intraday_note.excluded_sources.join(', ')}.`}
        </p>

        {tab === 'topics' && (
          !topicsHasData ? (
            <div className="py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema dovoljno članaka sa tačnim vremenom objave u izabranom periodu.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={topicData.hourly} margin={{ left: 0, right: 8 }}>
                <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
                <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                {topics.map((t, i) => (
                  <Bar key={t} dataKey={t} stackId="a" fill={INTRADAY_COLORS[i % INTRADAY_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )
        )}

        {tab === 'narr_hour' && (
          !narrHasData ? (
            <div className="py-8 text-center text-sm space-y-1" style={{ color: 'var(--text-muted)' }}>
              <div>{narrData?.intraday_note?.reason || 'Nema narativa sa tačnim vremenom u periodu.'}</div>
              {topNarr.length === 0 && <div className="text-xs" style={{ color: 'var(--accent)' }}>Odobrite narative u panelu istraživača da biste videli intraday distribuciju.</div>}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={narrData.by_hour} margin={{ left: 0, right: 8 }}>
                <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
                <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                {topNarr.map((n, i) => (
                  <Bar key={n} dataKey={n} stackId="a" fill={INTRADAY_COLORS[i % INTRADAY_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )
        )}

        {tab === 'narr_dow' && (
          !narrHasData ? (
            <div className="py-8 text-center text-sm space-y-1" style={{ color: 'var(--text-muted)' }}>
              <div>{narrData?.intraday_note?.reason || 'Nema narativa sa tačnim vremenom u periodu.'}</div>
              {topNarr.length === 0 && <div className="text-xs" style={{ color: 'var(--accent)' }}>Odobrite narative u panelu istraživača da biste videli distribuciju po danu.</div>}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={narrData.by_dow} margin={{ left: 0, right: 8 }}>
                <XAxis dataKey="dow_label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
                <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                {topNarr.map((n, i) => (
                  <Bar key={n} dataKey={n} stackId="a" fill={INTRADAY_COLORS[i % INTRADAY_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )
        )}

        {tab === 'heatmap' && (
          heatmap.length === 0 ? (
            <div className="py-8 text-center text-sm space-y-1" style={{ color: 'var(--text-muted)' }}>
              <div>{narrData?.intraday_note?.reason || 'Nema narativa sa tačnim vremenom u periodu.'}</div>
              {topNarr.length === 0 && <div className="text-xs" style={{ color: 'var(--accent)' }}>Odobrite narative u panelu istraživača da biste videli heatmap.</div>}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="text-xs mb-1 flex" style={{ color: 'var(--text-muted)' }}>
                <span className="w-8" />
                {Array.from({length: 24}, (_, h) => (
                  <span key={h} className="w-5 text-center" style={{ fontSize: 9 }}>{h}</span>
                ))}
              </div>
              {[1,2,3,4,5,6,0].map(dow => (
                <div key={dow} className="flex items-center mb-0.5">
                  <span className="w-8 text-[10px] shrink-0" style={{ color: 'var(--text-muted)' }}>{DOW_LABELS[dow]}</span>
                  {Array.from({length: 24}, (_, h) => {
                    const cell = heatmap.find(c => c.hour === h && c.dow === dow)
                    const cnt = cell?.count || 0
                    const intensity = cnt / maxHeat
                    return (
                      <div key={h} className="w-5 h-4 rounded-sm mr-0.5"
                        title={`${DOW_LABELS[dow]} ${h}:00 — ${cnt} narativnih čl.`}
                        style={{
                          background: cnt > 0 ? `rgba(99,102,241,${0.1 + intensity * 0.85})` : 'var(--bg-elevated)',
                        }} />
                    )
                  })}
                </div>
              ))}
              <div className="mt-2 flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <span>manje</span>
                {[0.1, 0.3, 0.55, 0.75, 0.95].map(v => (
                  <div key={v} className="w-4 h-3 rounded-sm" style={{ background: `rgba(99,102,241,${v})` }} />
                ))}
                <span>više</span>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  )
}

function NarrativeOriginPanel() {
  const [selectedId, setSelectedId] = useState('')

  const { data: narrList } = useQuery({
    queryKey: ['narratives-list-for-origin'],
    queryFn: () => api.get('/narratives').then(r => r.data.narratives),
  })
  const narratives = (narrList || []).filter(n => n.is_validated)

  const { data, isLoading } = useQuery({
    queryKey: ['narrative-origin', selectedId],
    queryFn: () => api.get(`/narratives/${selectedId}/origin`).then(r => r.data),
    enabled: !!selectedId,
  })

  const fmtDT = (s) => {
    if (!s) return '—'
    const d = new Date(s)
    return d.toLocaleString('sr-Latn', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  const spread = data?.spread_timeline || []
  const origin = data?.origin

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <TrendingUp size={15} style={{ color: 'var(--accent)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Poreklo i širenje narativa
          </h2>
        </div>
        <select
          value={selectedId}
          onChange={e => setSelectedId(e.target.value)}
          className="text-sm rounded-lg border px-3 py-1.5"
          style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)', minWidth: 220 }}>
          <option value="">— Izaberi narativ —</option>
          {narratives.map(n => (
            <option key={n.id} value={n.id}>{n.name}</option>
          ))}
        </select>
      </div>

      {!selectedId && (
        <div className="px-4 py-8 text-sm text-center" style={{ color: 'var(--text-muted)' }}>
          Izaberi narativ da vidiš koji medij ga je prvi plasirao i kako se širio
        </div>
      )}

      {selectedId && isLoading && (
        <div className="px-4 py-8 text-sm text-center" style={{ color: 'var(--text-muted)' }}>Učitavanje…</div>
      )}

      {selectedId && !isLoading && data && (
        <div className="p-4 space-y-4">
          {origin?.first_source_id ? (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs px-2.5 py-1 rounded-full font-medium"
                style={{ background: 'var(--accent)', color: 'white' }}>
                Prvi: {origin.first_source_id}
              </span>
              {origin.first_published_at && (
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {fmtDT(origin.first_published_at)}
                  {!origin.has_exact_time && ' (datum bez sata)'}
                </span>
              )}
              {origin.spread_hours != null && (
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  · {Math.round(origin.spread_hours)}h do potpune pokrivenosti
                </span>
              )}
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {data.origin_note || 'Nema origin podataka za ovaj narativ.'}
            </p>
          )}

          {spread.length > 0 && (
            <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--border)' }}>
              <table className="w-full text-sm">
                <thead style={{ background: 'var(--bg-elevated)' }}>
                  <tr>
                    {['#', 'Izvor', 'Prvi objavio', 'Tač. vreme', 'Članci'].map(h => (
                      <th key={h} className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {spread.map((row, idx) => (
                    <tr key={row.source_id} className="border-t" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-2 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                      <td className="px-4 py-2 font-mono text-xs font-medium" style={{ color: idx === 0 ? 'var(--accent)' : 'var(--text-primary)' }}>
                        {row.source_id}{idx === 0 && <span className="ml-1 text-[9px] opacity-70">prvi</span>}
                      </td>
                      <td className="px-4 py-2 text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                        {fmtDT(row.first_published_at)}
                      </td>
                      <td className="px-4 py-2">
                        {row.exact_time ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#22c55e22', color: '#22c55e' }}>✓</span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#f59e0b22', color: '#f59e0b' }}>datum</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{row.article_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.origin_note && spread.length > 0 && (
            <p className="text-xs italic flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
              <AlertTriangle size={11} style={{ color: '#f59e0b' }} /> {data.origin_note}
            </p>
          )}
        </div>
      )}
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
      <NarrativeOriginPanel />
      <IntradayPanel filterParams={filterParams} />
      <EntityTable filterParams={filterParams} />
    </div>
  )
}
