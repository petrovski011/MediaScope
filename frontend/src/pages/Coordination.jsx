import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Share2, Copy, AlertTriangle } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import api from '../lib/api'

const OWNER_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#8b5cf6', '#84cc16', '#f97316']

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
    return <div className="text-sm text-center py-10" style={{ color: 'var(--text-muted)' }}>
      Nema detektovane koordinacije u izabranom periodu. Detekcija se pokreće noćno.
    </div>
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

export default function Coordination() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  const { data: net } = useQuery({
    queryKey: ['coord-network', filterParams],
    queryFn: () => api.get(`/coordination/network?${filterParams}`).then(r => r.data),
  })
  const { data: cp } = useQuery({
    queryKey: ['coord-copypaste', filterParams],
    queryFn: () => api.get(`/coordination/copy-paste?${filterParams}`).then(r => r.data),
  })

  const nodes = net?.nodes || []
  const edges = net?.edges || []
  const pairs = cp?.pairs || []

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Share2 size={18} style={{ color: 'var(--accent)' }} /> Koordinacija
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Mreža usklađenog izveštavanja (copy-paste, framing, narativi)
        </p>
      </div>

      <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Mreža koordinacije</h2>
        <NetworkGraph nodes={nodes} edges={edges} />
        {net?.methodology_note && (
          <p className="text-xs mt-3 flex items-start gap-1.5" style={{ color: 'var(--text-muted)' }}>
            <AlertTriangle size={12} className="mt-0.5 shrink-0" style={{ color: '#f59e0b' }} /> {net.methodology_note}
          </p>
        )}
      </div>

      {/* Copy-paste parovi */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
          <Copy size={13} style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Copy-paste parovi {cp?.source === 'trigram_fallback' && '(trigram fallback)'}
          </span>
        </div>
        {pairs.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nema detektovanih parova.</div>
        ) : (
          <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {pairs.slice(0, 30).map((p, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  <span className="font-mono">{p.article1.source_id}</span> ↔ <span className="font-mono">{p.article2.source_id}</span>
                  <span className="ml-2 truncate" style={{ color: 'var(--text-muted)' }}>{p.article1.title?.slice(0, 80)}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {p.same_owner_group && <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>ista grupa</span>}
                  <span className="text-xs tabular-nums font-medium" style={{ color: 'var(--accent)' }}>{Math.round(p.similarity_score * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
