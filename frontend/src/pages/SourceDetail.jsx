import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, User, Building2 } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import api from '../lib/api'

const TYPE_ICONS = { person: User, organization: Building2 }

function EntityBreakdown({ sourceId }) {
  const navigate = useNavigate()
  const { data } = useQuery({
    queryKey: ['entities-source', sourceId],
    queryFn: () => api.get(`/entities?source_ids=${sourceId}&limit=15`).then(r => r.data),
  })
  const items = data?.items || []
  if (!items.length) return null
  const max = items[0]?.total_mentions || 1

  return (
    <div className="rounded-xl border mt-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Najčešće pominjani entiteti</h2>
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {items.map(e => {
          const Icon = TYPE_ICONS[e.entity_type] || User
          return (
            <div key={e.id}
              onClick={() => navigate(`/articles?entity_id=${e.id}&entity_name=${encodeURIComponent(e.name)}`)}
              className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-white/[0.02] transition-colors">
              <Icon size={12} style={{ color: 'var(--text-muted)', shrink: 0 }} />
              <div className="w-32 text-sm truncate" style={{ color: 'var(--text-primary)' }}>{e.name}</div>
              <div className="flex-1 h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
                <div className="h-full rounded-full" style={{ width: `${e.total_mentions / max * 100}%`, background: '#6366f1' }} />
              </div>
              <div className="text-xs tabular-nums w-8 text-right" style={{ color: 'var(--text-muted)' }}>
                {e.total_mentions}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function SourceDetail() {
  const { id } = useParams()
  const navigate = useNavigate()


  const { data, isLoading } = useQuery({
    queryKey: ['source', id],
    queryFn: () => api.get(`/sources/${id}`).then(r => r.data),
  })

  if (isLoading) return <div className="p-6 text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
  if (!data) return null

  return (
    <div className="p-6 max-w-3xl">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm mb-5 hover:text-white transition-colors"
        style={{ color: 'var(--text-muted)' }}>
        <ArrowLeft size={14} /> Nazad na izvore
      </button>

      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>{data.name}</h1>
        <div className="flex items-center gap-3 mt-1.5">
          <span className="text-sm" style={{ color: 'var(--text-muted)' }}>{data.owner_group}</span>
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <a href={data.url} target="_blank" rel="noreferrer"
            className="text-xs flex items-center gap-1 hover:underline" style={{ color: 'var(--text-muted)' }}>
            <ExternalLink size={11} /> {data.url}
          </a>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          ['Vlasnik', data.owner],
          ['Tip', data.media_type],
          ['Scraper', data.scraper_method],
          ['Timestamp', data.has_timestamp_time ? 'Tačno vreme' : 'Samo datum'],
          ['Autor', data.has_author ? 'Da' : 'Ne'],
          ['Cloudflare', data.cloudflare ? 'Da (zaštićen)' : 'Ne'],
        ].map(([label, value]) => value && (
          <div key={label} className="rounded-lg p-3 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{label}</div>
            <div className="text-sm" style={{ color: 'var(--text-primary)' }}>{value}</div>
          </div>
        ))}
      </div>

      {data.score_history?.length > 0 ? (
        <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-medium mb-4" style={{ color: 'var(--text-primary)' }}>
            Politički skor — poslednjih 30 dana
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.score_history} margin={{ left: -20, right: 8 }}>
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                tickFormatter={d => d.slice(5)} />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [v?.toFixed(3), 'Political score']}
              />
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" />
              <Line type="monotone" dataKey="political_score" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          {data.notes && (
            <p className="text-xs mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              Napomena: {data.notes}
            </p>
          )}
        </div>
      ) : (
        <div className="rounded-xl p-4 border text-sm" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
          Nema dovoljno analiziranih članaka za prikaz historije.
        </div>
      )}

      <EntityBreakdown sourceId={id} />
    </div>
  )
}
