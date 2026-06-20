import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Hash, EyeOff, BarChart3 } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import api from '../lib/api'

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJI_SLOBODA: 'Mediji i sloboda', PROTEST: 'Protest', KULTURA: 'Kultura', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}
const tlabel = (t) => TOPIC_LABELS[t] || t

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
    </div>
  )
}

export default function Topics() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })
  const [selected, setSelected] = useState(null)

  const { data } = useQuery({
    queryKey: ['topics-list', filterParams],
    queryFn: () => api.get(`/topics?${filterParams}`).then(r => r.data),
  })
  const topics = data?.topics || []
  const active = selected || (topics[0]?.topic)

  return (
    <div className="p-6 space-y-5 max-w-6xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Hash size={18} style={{ color: 'var(--accent)' }} /> Teme i tišina
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Ko pokriva temu, ko ćuti, i kako je framuju
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {topics.map(t => (
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
    </div>
  )
}
