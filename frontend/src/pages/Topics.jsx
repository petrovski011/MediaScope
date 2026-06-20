import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Brush } from 'recharts'
import { Hash, EyeOff, BarChart3, AlertTriangle, TrendingUp, ChevronDown, ChevronRight, Sparkles, Check, X } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import api from '../lib/api'
import { useAuth } from '../store/auth'

const MIN_MAIN_ARTICLES = 20
const PROPOSALS_PAGE_SIZE = 5

const FR_COLORS = ['#6366f1', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6']

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJSKE_SLOBODE: 'Medijske slobode', MEDIJI_SLOBODA: 'Medijske slobode',
  PROTEST: 'Protest', KULTURA: 'Kultura', ZABAVA_I_ESTRADA: 'Zabava i estrada', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}
const tlabel = (t) => TOPIC_LABELS[t] || t

const TOPIC_COLORS = [
  '#6366f1', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316',
]

const ALL_TOPICS = Object.keys(TOPIC_LABELS).filter(k => k !== 'MEDIJI_SLOBODA')

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
              <Brush dataKey="date" height={22} travellerWidth={8}
                stroke="var(--text-muted)" fill="var(--bg-elevated)"
                tickFormatter={d => d.slice(5)} />
            </AreaChart>
          </ResponsiveContainer>
        )}
        {chartData.length > 0 && (
          <p className="text-[10px] mt-1.5 text-center" style={{ color: 'var(--text-muted)' }}>
            Prevuci krajeve trake ispod grafika za zoom/navigaciju kroz period
          </p>
        )}
      </div>
    </div>
  )
}

function FramingEvolution({ topic }) {
  const { data } = useQuery({
    queryKey: ['framing-evolution', topic],
    queryFn: () => api.get(`/framing/evolution?topic=${encodeURIComponent(topic)}&days=30`).then(r => r.data),
  })
  if (!data?.series?.length || !data.framings?.length) return null
  return (
    <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} style={{ color: 'var(--text-muted)' }} />
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Evolucija framinga (30 dana)</h3>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data.series} margin={{ left: 0, right: 8 }}>
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
          <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
          {data.framings.map((f, i) => (
            <Area key={f} type="monotone" dataKey={f} stackId="1"
              stroke={FR_COLORS[i % FR_COLORS.length]} fill={FR_COLORS[i % FR_COLORS.length]} fillOpacity={0.6} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}


function CoverageDetail({ topic, filterParams }) {
  const { data: cov } = useQuery({
    queryKey: ['topic-coverage', topic, filterParams],
    queryFn: () => api.get(`/topics/${encodeURIComponent(topic)}/coverage?${filterParams}`).then(r => r.data),
  })
  const { data: fr } = useQuery({
    queryKey: ['topic-framing', topic, filterParams],
    queryFn: () => api.get(`/topics/${encodeURIComponent(topic)}/framing?${filterParams}`).then(r => r.data),
  })
  if (!cov) return <div className="px-4 py-6 text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje…</div>

  const maxFraming = Math.max(1, ...(fr?.framing_split || []).map(f => f.count))
  const silent = cov.by_source.filter(s => s.article_count === 0)
  const covering = cov.by_source.filter(s => s.article_count > 0)

  return (
    <div className="space-y-4">
      {/* Silence callout */}
      {cov.sources_silent.length > 0 && (
        <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: '#f59e0b55' }}>
          <div className="flex items-center gap-2 mb-2">
            <EyeOff size={14} style={{ color: '#f59e0b' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Tiho na temi „{tlabel(topic)}" — {cov.sources_silent.length} izvora
            </h3>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {silent.map(s => (
              <span key={s.source_id} className="text-xs px-2 py-0.5 rounded font-mono"
                style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }} title={s.owner_group || ''}>
                {s.source_id}
              </span>
            ))}
          </div>
          <p className="text-xs mt-2 italic" style={{ color: 'var(--text-muted)' }}>{cov.silence_note}</p>
        </div>
      )}

      {/* Coverage by source */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-2.5 border-b text-xs font-semibold uppercase tracking-wider" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
          Pokrivenost po izvoru ({covering.length} aktivnih)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>{['Izvor', 'Vlasnik', 'Članaka', 'Pol. skor', 'Senzac.'].map(h => (
                <th key={h} className="px-4 py-2 text-left text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {covering.map(s => (
                <tr key={s.source_id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{s.source_id}</td>
                  <td className="px-4 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>{s.owner_group || '—'}</td>
                  <td className="px-4 py-2 text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>{s.article_count}</td>
                  <td className="px-4 py-2 text-xs tabular-nums" style={{ color: s.avg_political > 0.2 ? '#60a5fa' : s.avg_political < -0.2 ? '#f87171' : 'var(--text-muted)' }}>
                    {s.avg_political ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{s.avg_sensationalism ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Framing split */}
      {fr?.framing_split?.length > 0 && (
        <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={14} style={{ color: 'var(--text-muted)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Framing distribucija</h3>
          </div>
          <div className="space-y-2">
            {fr.framing_split.map(f => (
              <div key={f.framing} className="flex items-center gap-3">
                <span className="text-xs w-44 truncate" style={{ color: 'var(--text-secondary)' }}>{f.framing}</span>
                <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                  <div className="h-full rounded-full" style={{ width: `${(f.count / maxFraming) * 100}%`, background: 'var(--accent)' }} />
                </div>
                <span className="text-xs tabular-nums w-8 text-right" style={{ color: 'var(--text-muted)' }}>{f.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <FramingEvolution topic={topic} />
    </div>
  )
}

function TopicProposalsPanel() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const canManage = user?.role === 'admin' || user?.role === 'researcher'
  const [page, setPage] = useState(1)
  const [acceptingId, setAcceptingId] = useState(null)
  const [labelInput, setLabelInput] = useState('')

  const { data } = useQuery({
    queryKey: ['topic-proposals'],
    queryFn: () => api.get('/topics/proposals?status=pending').then(r => r.data.proposals),
  })

  const accept = useMutation({
    mutationFn: ({ id, label_sr }) => api.post(`/topics/proposals/${id}/accept`, { label_sr }),
    onSuccess: () => { qc.invalidateQueries(['topic-proposals']); setAcceptingId(null); setLabelInput('') },
  })
  const reject = useMutation({
    mutationFn: (id) => api.post(`/topics/proposals/${id}/reject`),
    onSuccess: () => qc.invalidateQueries(['topic-proposals']),
  })

  const proposals = data || []
  if (proposals.length === 0) return null

  const pages = Math.ceil(proposals.length / PROPOSALS_PAGE_SIZE)
  const slice = proposals.slice((page - 1) * PROPOSALS_PAGE_SIZE, page * PROPOSALS_PAGE_SIZE)

  const fmtDate = (s) => s ? new Date(s).toLocaleDateString('sr-Latn') : '—'

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-2.5 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <Sparkles size={13} style={{ color: '#f59e0b' }} />
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            AI predlozi novih tema ({proposals.length})
          </span>
        </div>
        {pages > 1 && (
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1 rounded border disabled:opacity-30" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
              <ChevronRight size={12} className="rotate-180" />
            </button>
            <span className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>{page}/{pages}</span>
            <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
              className="p-1 rounded border disabled:opacity-30" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
              <ChevronRight size={12} />
            </button>
          </div>
        )}
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {slice.map(p => (
          <div key={p.id} className="px-4 py-2.5">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <span className="text-sm font-mono font-medium" style={{ color: 'var(--text-primary)' }}>{p.key}</span>
                <span className="ml-2 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  {p.count} čl. · {fmtDate(p.first_seen)} – {fmtDate(p.last_seen)}
                </span>
              </div>
              {canManage && acceptingId !== p.id && (
                <div className="flex gap-1.5 shrink-0">
                  <button onClick={() => { setAcceptingId(p.id); setLabelInput('') }}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]"
                    style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                    <Check size={11} /> Prihvati
                  </button>
                  <button onClick={() => reject.mutate(p.id)} disabled={reject.isPending}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04] disabled:opacity-50"
                    style={{ borderColor: 'var(--border)', color: '#ef4444' }}>
                    <X size={11} /> Odbij
                  </button>
                </div>
              )}
            </div>
            {acceptingId === p.id && (
              <div className="mt-2 flex items-center gap-2">
                <input
                  value={labelInput}
                  onChange={e => setLabelInput(e.target.value)}
                  placeholder="Srpski naziv (npr. Ekologija)"
                  className="text-sm px-2 py-1 rounded border flex-1"
                  style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
                />
                <button onClick={() => accept.mutate({ id: p.id, label_sr: labelInput })}
                  disabled={!labelInput.trim() || accept.isPending}
                  className="px-2 py-1 rounded text-xs font-medium disabled:opacity-40"
                  style={{ background: 'var(--accent)', color: 'white' }}>
                  Potvrdi
                </button>
                <button onClick={() => setAcceptingId(null)}
                  className="px-2 py-1 rounded text-xs border"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                  Odustani
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Topics() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })
  const [selected, setSelected] = useState(null)
  const [showSmall, setShowSmall] = useState(false)

  const { data } = useQuery({
    queryKey: ['topics-list', filterParams],
    queryFn: () => api.get(`/topics?${filterParams}`).then(r => r.data),
  })
  const topics = data?.topics || []
  const mainTopics = topics.filter(t => t.article_count >= MIN_MAIN_ARTICLES)
  const smallTopics = topics.filter(t => t.article_count < MIN_MAIN_ARTICLES)
  const active = selected || (mainTopics[0]?.topic) || (topics[0]?.topic)

  return (
    <div className="p-6 space-y-5 max-w-6xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Hash size={18} style={{ color: 'var(--accent)' }} /> Teme i tišina
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Ko pokriva temu, ko ćuti, i kako je framuju
          </p>
        </div>
        {/* Topic dropdown selector */}
        <select
          value={active || ''}
          onChange={e => setSelected(e.target.value)}
          className="text-sm rounded-lg border px-3 py-1.5"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)', minWidth: 200 }}>
          {mainTopics.map(t => (
            <option key={t.topic} value={t.topic}>{tlabel(t.topic)} ({t.article_count})</option>
          ))}
          {smallTopics.length > 0 && <option disabled>─── Male teme ───</option>}
          {smallTopics.map(t => (
            <option key={t.topic} value={t.topic}>{tlabel(t.topic)} ({t.article_count})</option>
          ))}
        </select>
      </div>

      {/* Main topic buttons */}
      <div className="flex flex-wrap gap-2">
        {mainTopics.map(t => (
          <button key={t.topic} onClick={() => setSelected(t.topic)}
            className="px-3 py-1.5 rounded-lg text-xs border transition-colors"
            style={{
              background: active === t.topic ? 'var(--accent)' : 'var(--bg-surface)',
              borderColor: active === t.topic ? 'var(--accent)' : 'var(--border)',
              color: active === t.topic ? 'white' : 'var(--text-secondary)',
            }}>
            {tlabel(t.topic)} <span className="opacity-70">{t.article_count}</span>
            {t.silent_source_count > 0 && (
              <span className="ml-1 opacity-70">· {t.silent_source_count} tih</span>
            )}
          </button>
        ))}
      </div>

      {active && <CoverageDetail topic={active} filterParams={filterParams} />}

      {/* Small topics collapsible */}
      {smallTopics.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <button
            onClick={() => setShowSmall(s => !s)}
            className="w-full px-4 py-2.5 flex items-center gap-2 text-left hover:opacity-80 transition-opacity"
            style={{ borderColor: 'var(--border)' }}>
            {showSmall ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Male teme (ispod {MIN_MAIN_ARTICLES} članaka) — {smallTopics.length}
            </span>
          </button>
          {showSmall && (
            <div className="border-t px-4 py-3 flex flex-wrap gap-2" style={{ borderColor: 'var(--border)' }}>
              {smallTopics.map(t => (
                <button key={t.topic} onClick={() => setSelected(t.topic)}
                  className="px-3 py-1.5 rounded-lg text-xs border transition-colors"
                  style={{
                    background: active === t.topic ? 'var(--accent)' : 'var(--bg-elevated)',
                    borderColor: active === t.topic ? 'var(--accent)' : 'var(--border)',
                    color: active === t.topic ? 'white' : 'var(--text-muted)',
                  }}>
                  {tlabel(t.topic)} <span className="opacity-70">{t.article_count}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <TopicProposalsPanel />

      <TopicTimeline filterParams={Object.fromEntries(new URLSearchParams(filterParams))} />
    </div>
  )
}
