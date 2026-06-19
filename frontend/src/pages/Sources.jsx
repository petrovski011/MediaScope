import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { CheckCircle, Circle } from 'lucide-react'
import { useFilters } from '../store/filters'
import api from '../lib/api'

function ScoreBar({ value, max = 1, color }) {
  if (value == null) return <span style={{ color: 'var(--text-muted)' }}>—</span>
  const pct = Math.abs(value) / max * 100
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
        {value > 0 ? '+' : ''}{value.toFixed(2)}
      </span>
    </div>
  )
}

const OWNER_COLORS = {
  'Pro-vladini': '#ef4444',
  'Nezavisan': '#3b82f6',
  'Drzavni': '#f59e0b',
  'Javni servis': '#f59e0b',
}

export default function Sources() {
  const navigate = useNavigate()
  const { selectedSources } = useFilters()

  const { data, isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.get('/sources').then(r => r.data.items),
  })

  if (isLoading) return (
    <div className="p-6 text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
  )

  const filtered = selectedSources.length
    ? data?.filter((s) => selectedSources.includes(s.source_id))
    : data

  const grouped = filtered?.reduce((acc, s) => {
    const g = s.owner_group || 'Ostalo'
    if (!acc[g]) acc[g] = []
    acc[g].push(s)
    return acc
  }, {}) || {}

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Izvori</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          {selectedSources.length
            ? `${filtered?.length} od ${data?.length} portala (filtrirano)`
            : `${data?.length} srpskih medijskih portala`}
        </p>
      </div>

      <div className="space-y-6">
        {Object.entries(grouped).map(([group, sources]) => (
          <div key={group}>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full" style={{ background: OWNER_COLORS[group] || '#6b7280' }} />
              <h2 className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>{group}</h2>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({sources.length})</span>
            </div>

            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <table className="w-full">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                    {['', 'Portal', 'Vlasnik', 'Članci', 'Political avg', 'Senzac. avg', 'Timestamp'].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                  {sources.map(s => (
                    <tr key={s.source_id} onClick={() => navigate(`/sources/${s.source_id}`)} className="hover:bg-white/[0.02] transition-colors cursor-pointer">
                      <td className="pl-4 py-3">
                        {s.is_active
                          ? <CheckCircle size={13} className="text-green-500" />
                          : <Circle size={13} style={{ color: 'var(--text-muted)' }} />}
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{s.name}</div>
                        <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{s.source_id}</div>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-secondary)' }}>{s.owner || '—'}</td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-primary)' }}>
                        {s.stats.articles_total?.toLocaleString() || '0'}
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar
                          value={s.stats.avg_political_score}
                          color={s.stats.avg_political_score > 0.3 ? '#ef4444' : s.stats.avg_political_score < -0.3 ? '#3b82f6' : '#6b7280'}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar value={s.stats.avg_sensationalism} color="#f59e0b" />
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>
                        {s.has_timestamp_time ? '✓ vreme' : '— samo datum'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
