import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Share2, Copy, AlertTriangle, Users, Hash, TrendingUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'

// ─── Constants ────────────────────────────────────────────────────────────────

const OWNER_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#8b5cf6', '#84cc16', '#f97316']
const CP_PER_PAGE = 5
const FM_PER_PAGE = 5

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJSKE_SLOBODE: 'Medijske slobode', MEDIJI_SLOBODA: 'Medijske slobode',
  PROTEST: 'Protest', KULTURA: 'Kultura', ZABAVA_I_ESTRADA: 'Zabava i estrada', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}
const ALL_TOPICS = Object.keys(TOPIC_LABELS)

// ─── Shared helpers ────────────────────────────────────────────────────────────

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

function ErrorMessage({ message }) {
  return (
    <div className="px-4 py-6 flex items-center justify-center gap-2 text-sm" style={{ color: '#fca5a5' }}>
      <AlertTriangle size={14} style={{ color: '#ef4444', flexShrink: 0 }} />
      {message || 'Greška pri učitavanju podataka.'}
    </div>
  )
}

// ─── Segment 1 helpers ─────────────────────────────────────────────────────────

function ownerColorMap(nodes) {
  const groups = [...new Set(nodes.map(n => n.owner_group || 'Nezavisan'))]
  const map = {}
  groups.forEach((g, i) => { map[g] = OWNER_COLORS[i % OWNER_COLORS.length] })
  return map
}

function NetworkGraph({ nodes, edges }) {
  const size = 520, cx = size / 2, cy = size / 2, R = 200
  const colorMap = useMemo(() => ownerColorMap(nodes), [nodes])

  const pos = useMemo(() => {
    const p = {}
    nodes.forEach((n, i) => {
      const ang = (2 * Math.PI * i) / Math.max(1, nodes.length) - Math.PI / 2
      p[n.id] = { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) }
    })
    return p
  }, [nodes])

  const maxW = Math.max(1, ...edges.map(e => e.weight))
  const maxNode = Math.max(1, ...nodes.map(n => n.weight))

  if (nodes.length === 0) {
    return (
      <div className="text-sm text-center py-10" style={{ color: 'var(--text-muted)' }}>
        Nema detektovane koordinacije u izabranom periodu. Detekcija se pokreće noćno.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxWidth: 560, margin: '0 auto', display: 'block' }}>
        {edges.map((e, i) => {
          const a = pos[e.source], b = pos[e.target]
          if (!a || !b) return null
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={e.same_owner_group ? 'var(--text-muted)' : 'var(--accent)'}
              strokeWidth={1 + (e.weight / maxW) * 5}
              strokeDasharray={e.same_owner_group ? '4 3' : ''}
              strokeOpacity={e.same_owner_group ? 0.4 : 0.65} />
          )
        })}
        {nodes.map(n => {
          const p = pos[n.id]
          const r = 6 + (n.weight / maxNode) * 12
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={r} fill={colorMap[n.owner_group || 'Nezavisan']} fillOpacity={0.85} />
              <text x={p.x} y={p.y - r - 4} textAnchor="middle" fontSize="10" fill="var(--text-secondary)">{n.id}</text>
            </g>
          )
        })}
      </svg>
      <div className="flex flex-wrap gap-3 justify-center mt-2">
        {Object.entries(colorMap).map(([g, c]) => (
          <span key={g} className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} /> {g}
          </span>
        ))}
        <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-muted)' }}>
          <svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="var(--text-muted)" strokeWidth="2" strokeDasharray="4 3" /></svg>
          ista vlasnička grupa
        </span>
      </div>
    </div>
  )
}

// ─── Segment 1: Koordinacioni signali ─────────────────────────────────────────

function CoordinationPanel({ filterParams }) {
  const navigate = useNavigate()
  const [tab, setTab] = useState('copypaste')
  const [cpPage, setCpPage] = useState(1)
  const [fmPage, setFmPage] = useState(1)

  const cpParams = new URLSearchParams({ threshold: 0.7, limit: 50, ...filterParams })
  const { data: cpData, isLoading: cpLoading, isError: cpError } = useQuery({
    queryKey: ['coordination-cp', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/copy-paste?${cpParams}`).then(r => r.data),
  })

  const fmParams = new URLSearchParams({ min_sources: 2, limit: 50, ...filterParams })
  const { data: fmData, isLoading: fmLoading, isError: fmError } = useQuery({
    queryKey: ['coordination-framing', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/framing?${fmParams}`).then(r => r.data),
  })

  const cpPairs = cpData?.groups || []
  const fmGroups = fmData?.groups || []

  const cpPages = Math.max(1, Math.ceil(cpPairs.length / CP_PER_PAGE))
  const fmPages = Math.max(1, Math.ceil(fmGroups.length / FM_PER_PAGE))
  const cpSlice = cpPairs.slice((cpPage - 1) * CP_PER_PAGE, cpPage * CP_PER_PAGE)
  const fmSlice = fmGroups.slice((fmPage - 1) * FM_PER_PAGE, fmPage * FM_PER_PAGE)

  const netParams = new URLSearchParams({ ...filterParams })
  const { data: net, isError: netError } = useQuery({
    queryKey: ['coord-network', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/network?${netParams}`).then(r => r.data),
  })
  const nodes = net?.nodes || []
  const edges = net?.edges || []

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      {/* Header */}
      <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Koordinacioni signali</h2>
        </div>
        <div className="flex gap-1">
          {[
            ['copypaste', `Copy-paste (${cpPairs.length} gr.)`],
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

      {/* Copy-paste network graph */}
      {tab === 'copypaste' && (
        <div>
          <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-xs font-medium mb-3" style={{ color: 'var(--text-muted)' }}>Mreža koordinacije</h3>
            {netError ? (
              <ErrorMessage message="Greška pri učitavanju mreže koordinacije." />
            ) : (
              <NetworkGraph nodes={nodes} edges={edges} />
            )}
            {net?.methodology_note && (
              <p className="text-xs mt-3 flex items-start gap-1.5" style={{ color: 'var(--text-muted)' }}>
                <AlertTriangle size={12} className="mt-0.5 shrink-0" style={{ color: '#f59e0b' }} /> {net.methodology_note}
              </p>
            )}
          </div>

          {cpError ? (
            <ErrorMessage message="Greška pri učitavanju copy-paste parova." />
          ) : cpLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
          ) : cpPairs.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema copy-paste grupa (threshold ≥70%)
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
                      {group.size} {group.size === 1 ? 'medij' : group.size < 5 ? 'medija' : 'medija'}
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
          {cpData?.methodology_note && (
            <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              {cpData.methodology_note}
            </div>
          )}
        </div>
      )}

      {/* Framing koordinacija */}
      {tab === 'framing' && (
        <div>
          {fmError ? (
            <ErrorMessage message="Greška pri učitavanju framing koordinacije." />
          ) : fmLoading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
          ) : fmGroups.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Nema framing koordinacije (isti okvir + tema kod min. 2 izvora)
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead style={{ background: 'var(--bg-elevated)' }}>
                  <tr>{['Okvir', 'Tema', 'Izvora', 'Članaka', 'Pouzdanost', 'Mediji'].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{h}</th>
                  ))}</tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                  {fmSlice.map((g, i) => (
                    <tr key={i}>
                      <td className="px-3 py-2.5">
                        <span className="text-sm font-medium" style={{ color: '#fbbf24' }}>
                          {(g.framing_name || '').replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {ALL_TOPICS.includes(g.topic) ? TOPIC_LABELS[g.topic] : g.topic}
                      </td>
                      <td className="px-3 py-2.5 text-sm tabular-nums" style={{ color: 'var(--text-primary)' }}>{g.source_count}</td>
                      <td className="px-3 py-2.5 text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>{g.article_count}</td>
                      <td className="px-3 py-2.5 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                        {g.avg_confidence != null ? `${Math.round(g.avg_confidence * 100)}%` : '—'}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {g.sources?.map(s => (
                            <span key={s} className="text-[10px] px-1.5 py-0.5 rounded"
                              style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination page={fmPage} pages={fmPages} onChange={setFmPage} />
          {fmData?.methodology_note && (
            <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              {fmData.methodology_note}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Segment 2: SNA mreže ─────────────────────────────────────────────────────

function MatrixTable({ data, rowKey, colKey, valKey, rowLabel, emptyMsg, getCellUrl }) {
  if (!Array.isArray(data) || data.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
        {emptyMsg || 'Nema podataka.'}
      </div>
    )
  }

  const rows = [...new Set(data.map(d => d[rowKey]))]
  const cols = [...new Set(data.map(d => d[colKey]))]
  const lookup = {}
  const itemLookup = {}
  for (const d of data) {
    const k = `${d[rowKey]}||${d[colKey]}`
    lookup[k] = d[valKey] || 0
    itemLookup[k] = d
  }
  const maxVal = Math.max(1, ...data.map(d => d[valKey] || 0))

  return (
    <div className="overflow-x-auto">
      <table className="text-xs w-full min-w-max">
        <thead>
          <tr>
            <th className="px-3 py-2 text-left font-medium" style={{ color: 'var(--text-muted)' }}>{rowLabel || 'Izvor'}</th>
            {cols.map(c => (
              <th key={c} className="px-2 py-2 text-center font-medium max-w-[80px]" style={{ color: 'var(--text-muted)' }}>
                <span className="block truncate max-w-[80px]" title={c}>{c}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row} className="border-t" style={{ borderColor: 'var(--border)' }}>
              <td className="px-3 py-1.5 font-mono font-medium whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>{row}</td>
              {cols.map(col => {
                const k = `${row}||${col}`
                const v = lookup[k] || 0
                const item = itemLookup[k]
                const intensity = v / maxVal
                const url = getCellUrl && v > 0 ? getCellUrl(item) : null
                return (
                  <td key={col} className="px-2 py-1.5 text-center tabular-nums"
                    style={{
                      background: v > 0 ? `rgba(99,102,241,${0.1 + intensity * 0.55})` : 'transparent',
                      color: v > 0 ? (intensity > 0.5 ? 'white' : 'var(--text-secondary)') : 'var(--text-muted)',
                      padding: 0,
                    }}>
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer"
                        className="block w-full h-full px-2 py-1.5 hover:brightness-125"
                        style={{ color: 'inherit', textDecoration: 'none' }}
                        title={`${row} → ${col}: ${v} (klikni za članke)`}>
                        {v}
                      </a>
                    ) : (
                      <span className="block px-2 py-1.5">{v > 0 ? v : '·'}</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const SNA_TABS = [
  {
    key: 'actors', label: 'Mediji ↔ Akteri', icon: <Users size={12} />,
    endpoint: '/coordination/network/actors',
    rowKey: 'source_id', colKey: 'entity_name', valKey: 'count',
    desc: 'Broj pomena svakog aktera po mediju (top 10 aktera × svi aktivni izvori)',
    emptyMsg: 'Nema podataka o pominjanju aktera. Popunjava se kako AI analiza obrađuje članke.',
    buildUrl: d => `/articles?source_ids=${d.source_id}&entity_id=${d.entity_id}&entity_name=${encodeURIComponent(d.entity_name)}`,
  },
  {
    key: 'topics', label: 'Mediji ↔ Teme', icon: <Hash size={12} />,
    endpoint: '/coordination/network/topics',
    rowKey: 'source_id', colKey: 'topic', valKey: 'count',
    desc: 'Broj članaka po temi po mediju (sve teme × svi aktivni izvori)',
    emptyMsg: 'Nema podataka o pokrivenosti tema.',
    buildUrl: d => `/articles?source_ids=${d.source_id}&topic=${encodeURIComponent(d.topic)}`,
  },
  {
    key: 'narratives', label: 'Mediji ↔ Narativi', icon: <TrendingUp size={12} />,
    endpoint: '/coordination/network/narratives',
    rowKey: 'source_id', colKey: 'narrative_name', valKey: 'count',
    desc: 'Broj članaka koji nose svaki narativ po mediju (AI klasteri sa ≥2 pojavljivanja × svi aktivni izvori)',
    emptyMsg: 'Nema narativnih klastera sa ≥2 pojavljivanja u izabranom periodu.',
    buildUrl: d => `/articles?source_ids=${d.source_id}&narrative_cluster_id=${d.cluster_id}`,
  },
]

function SNANetworks({ filterParams }) {
  const [activeTab, setActiveTab] = useState(0)

  const tab = SNA_TABS[activeTab]

  const { data: actorsData, isLoading: actorsLoading, isError: actorsError } = useQuery({
    queryKey: ['sna-actors', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/network/actors?${new URLSearchParams(filterParams)}`).then(r => r.data),
    enabled: activeTab === 0,
  })

  const { data: topicsData, isLoading: topicsLoading, isError: topicsError } = useQuery({
    queryKey: ['sna-topics', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/network/topics?${new URLSearchParams(filterParams)}`).then(r => r.data),
    enabled: activeTab === 1,
  })

  const { data: narrativesData, isLoading: narrativesLoading, isError: narrativesError } = useQuery({
    queryKey: ['sna-narratives', JSON.stringify(filterParams)],
    queryFn: () => api.get(`/coordination/network/narratives?${new URLSearchParams(filterParams)}`).then(r => r.data),
    enabled: activeTab === 2,
  })

  const tabState = [
    { data: actorsData, isLoading: actorsLoading, isError: actorsError },
    { data: topicsData, isLoading: topicsLoading, isError: topicsError },
    { data: narrativesData, isLoading: narrativesLoading, isError: narrativesError },
  ]
  const { data, isLoading, isError } = tabState[activeTab]
  const matrix = data?.matrix || []

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      {/* Tab bar */}
      <div className="flex border-b" style={{ borderColor: 'var(--border)' }}>
        {SNA_TABS.map((t, i) => (
          <button key={t.key} onClick={() => setActiveTab(i)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors"
            style={{
              borderColor: activeTab === i ? 'var(--accent)' : 'transparent',
              color: activeTab === i ? 'var(--accent)' : 'var(--text-muted)',
            }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4">
        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>{tab.desc}</p>
        {isError ? (
          <ErrorMessage message={`Greška pri učitavanju SNA matrice (${tab.label}). Proverite da li su endpointi dostupni.`} />
        ) : isLoading ? (
          <div className="py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
        ) : (
          <MatrixTable
            data={matrix}
            rowKey={tab.rowKey}
            colKey={tab.colKey}
            valKey={tab.valKey}
            emptyMsg={tab.emptyMsg}
            getCellUrl={tab.buildUrl || null}
          />
        )}
      </div>
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function Coordination() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Share2 size={18} style={{ color: 'var(--accent)' }} /> Koordinacija
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Koordinacioni signali i SNA matrice — copy-paste, framing koordinacija, mreže po akterima, temama i narativima
        </p>
      </div>

      {/* Segment 1: Koordinacioni signali */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
          Koordinacioni signali
        </h2>
        <CoordinationPanel filterParams={filterParams} />
      </section>

      {/* Segment 2: SNA mreže */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>
          SNA mreže
        </h2>
        <SNANetworks filterParams={filterParams} />
      </section>
    </div>
  )
}
