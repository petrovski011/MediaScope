import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Activity, TrendingUp, TrendingDown, Shuffle, Volume2, Plus, X, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { useAuth } from '../store/auth'
import api from '../lib/api'

const PER_PAGE = 25

const TYPE_META = {
  topic_spike:        { label: 'Skok teme', icon: TrendingUp, color: '#ef4444' },
  topic_drop:         { label: 'Pad teme', icon: TrendingDown, color: '#f59e0b' },
  framing_shift:      { label: 'Framing pomak', icon: Shuffle, color: '#8b5cf6' },
  narrative_intensity:{ label: 'Intenzitet narativa', icon: Activity, color: '#3b82f6' },
  silence_anomaly:    { label: 'Tišina', icon: Volume2, color: '#6b7280' },
}

function PeriodTypesPanel() {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin' || user?.role === 'researcher'
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ date_from: '', date_to: '', period_type: 'electoral', note: '' })

  const { data } = useQuery({
    queryKey: ['period-types'],
    queryFn: () => api.get('/anomalies/period-types').then(r => r.data.period_types),
  })
  const create = useMutation({
    mutationFn: () => api.post('/anomalies/period-types', form),
    onSuccess: () => { qc.invalidateQueries(['period-types']); setOpen(false); setForm({ date_from: '', date_to: '', period_type: 'electoral', note: '' }) },
  })
  const del = useMutation({
    mutationFn: (id) => api.delete(`/anomalies/period-types/${id}`),
    onSuccess: () => qc.invalidateQueries(['period-types']),
  })
  const periods = data || []
  const inputStyle = { background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }

  return (
    <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-2.5 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Tipovi perioda (kontekst anomalija)</span>
        {canEdit && <button onClick={() => setOpen(o => !o)} className="text-xs flex items-center gap-1" style={{ color: 'var(--accent)' }}><Plus size={12} /> Dodaj</button>}
      </div>
      {open && (
        <div className="px-4 py-3 border-b flex flex-wrap gap-2 items-center" style={{ borderColor: 'var(--border)' }}>
          <input type="date" value={form.date_from} onChange={e => setForm(f => ({ ...f, date_from: e.target.value }))} className="px-2 py-1 rounded text-xs border" style={inputStyle} />
          <input type="date" value={form.date_to} onChange={e => setForm(f => ({ ...f, date_to: e.target.value }))} className="px-2 py-1 rounded text-xs border" style={inputStyle} />
          <select value={form.period_type} onChange={e => setForm(f => ({ ...f, period_type: e.target.value }))} className="px-2 py-1 rounded text-xs border" style={inputStyle}>
            <option value="electoral">Izborni</option><option value="crisis">Krizni</option><option value="calm">Miran</option>
          </select>
          <input placeholder="napomena" value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} className="px-2 py-1 rounded text-xs border flex-1" style={inputStyle} />
          <button onClick={() => create.mutate()} disabled={!form.date_from || !form.date_to} className="px-3 py-1 rounded text-xs font-medium disabled:opacity-50" style={{ background: 'var(--accent)', color: 'white' }}>Sačuvaj</button>
        </div>
      )}
      <div className="px-4 py-2 flex flex-wrap gap-2">
        {periods.length === 0 ? <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Nema označenih perioda.</span> :
          periods.map(p => (
            <span key={p.id} className="text-xs px-2 py-1 rounded flex items-center gap-1.5" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
              {p.period_type} · {p.date_from}→{p.date_to}
              {canEdit && <button onClick={() => del.mutate(p.id)}><X size={11} style={{ color: 'var(--text-muted)' }} /></button>}
            </span>
          ))}
      </div>
    </div>
  )
}

export default function Anomalies() {
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('date')
  const [sortDir, setSortDir] = useState('desc')

  const handleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortBy(field); setSortDir('desc') }
    setPage(1)
  }

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <ChevronDown size={11} className="opacity-30" />
    return sortDir === 'desc' ? <ChevronDown size={11} className="opacity-80" /> : <ChevronUp size={11} className="opacity-80" />
  }

  const params = new URLSearchParams({
    limit: PER_PAGE, offset: (page - 1) * PER_PAGE,
    sort_by: sortBy, sort_dir: sortDir,
  })
  if (filter) params.set('anomaly_type', filter)

  const { data } = useQuery({
    queryKey: ['anomalies', filter, page, sortBy, sortDir],
    queryFn: () => api.get(`/anomalies?${params}`).then(r => r.data),
    keepPreviousData: true,
  })
  const anomalies = data?.anomalies || []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PER_PAGE)

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Activity size={18} style={{ color: 'var(--accent)' }} /> Anomalije
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Statistička odstupanja od 7-dnevnog proseka (skokovi tema, framing pomaci, intenzitet narativa)
        </p>
      </div>

      <PeriodTypesPanel />

      {/* Filter + sort header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { setFilter(''); setPage(1) }} className="px-3 py-1.5 rounded-lg text-xs border"
            style={{ background: !filter ? 'var(--accent)' : 'var(--bg-surface)', borderColor: 'var(--border)', color: !filter ? 'white' : 'var(--text-secondary)' }}>Sve</button>
          {Object.entries(TYPE_META).map(([k, m]) => (
            <button key={k} onClick={() => { setFilter(k); setPage(1) }} className="px-3 py-1.5 rounded-lg text-xs border"
              style={{ background: filter === k ? 'var(--accent)' : 'var(--bg-surface)', borderColor: 'var(--border)', color: filter === k ? 'white' : 'var(--text-secondary)' }}>
              {m.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <span>Sortiraj:</span>
          {[['date', 'Datum'], ['deviation_pct', 'Odstupanje'], ['anomaly_type', 'Tip']].map(([f, lbl]) => (
            <button key={f} onClick={() => handleSort(f)}
              className="flex items-center gap-0.5 px-2 py-1 rounded border transition-colors"
              style={{
                borderColor: sortBy === f ? 'var(--accent)' : 'var(--border)',
                color: sortBy === f ? 'var(--accent)' : 'var(--text-secondary)',
                background: 'var(--bg-surface)',
              }}>
              {lbl}<SortIcon field={f} />
            </button>
          ))}
        </div>
      </div>

      {total > 0 && (
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {total.toLocaleString()} anomalija ukupno
        </div>
      )}

      {anomalies.length === 0 ? (
        <div className="rounded-xl border px-4 py-10 text-center text-sm" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
          Nema detektovanih anomalija. Detekcija se pokreće dnevno u 08:15.
        </div>
      ) : (
        <div className="space-y-2">
          {anomalies.map(a => {
            const meta = TYPE_META[a.anomaly_type] || { label: a.anomaly_type, icon: Activity, color: 'var(--text-muted)' }
            const Icon = meta.icon
            return (
              <div key={a.id} className="rounded-xl border p-4 flex items-start gap-3" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
                <div className="mt-0.5 p-1.5 rounded" style={{ background: `${meta.color}22` }}><Icon size={14} style={{ color: meta.color }} /></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: `${meta.color}22`, color: meta.color }}>{meta.label}</span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{a.date}</span>
                    {a.deviation_pct != null && (
                      <span className="text-xs tabular-nums font-medium" style={{ color: meta.color }}>{a.deviation_pct > 0 ? '+' : ''}{a.deviation_pct}%</span>
                    )}
                    {a.source_id && (
                      <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>{a.source_id}</span>
                    )}
                  </div>
                  <p className="text-sm mt-1" style={{ color: 'var(--text-primary)' }}>{a.description}</p>
                  {(a.baseline_value != null && a.detected_value != null) && (
                    <p className="text-xs mt-1 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                      baseline {a.baseline_value} → detektovano {a.detected_value}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Paginacija */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="p-1.5 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', background: 'var(--bg-surface)' }}>
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
            {page} / {totalPages}
          </span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="p-1.5 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', background: 'var(--bg-surface)' }}>
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
