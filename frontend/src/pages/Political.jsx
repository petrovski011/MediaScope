import { useQuery } from '@tanstack/react-query'
import { Landmark, Users, AlertTriangle } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import api from '../lib/api'

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJI_SLOBODA: 'Mediji i sloboda', PROTEST: 'Protest', KULTURA: 'Kultura', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}

function ActorRow({ a }) {
  const total = (a.pro_gov_mentions + a.opposition_mentions + a.neutral_mentions) || 1
  const pg = (a.pro_gov_mentions / total) * 100
  const opp = (a.opposition_mentions / total) * 100
  const neu = (a.neutral_mentions / total) * 100
  return (
    <div className="px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{a.name}</span>
        <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{a.mentions} pom. · {a.source_count} izv.</span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden" title={`pro-vlada ${a.pro_gov_mentions} / opozicija ${a.opposition_mentions} / neutralno ${a.neutral_mentions}`}>
        <div style={{ width: `${pg}%`, background: '#60a5fa' }} />
        <div style={{ width: `${neu}%`, background: '#6b7280' }} />
        <div style={{ width: `${opp}%`, background: '#f87171' }} />
      </div>
    </div>
  )
}

export default function Political() {
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  const { data: actorsData } = useQuery({
    queryKey: ['political-actors', filterParams],
    queryFn: () => api.get(`/political/actors?${filterParams}`).then(r => r.data),
  })
  const { data: metaData } = useQuery({
    queryKey: ['political-meta', filterParams],
    queryFn: () => api.get(`/political/meta-framing?${filterParams}`).then(r => r.data),
  })
  const actors = actorsData?.actors || []
  const metaSrc = metaData?.by_source || []
  const metaTopic = metaData?.by_topic || []
  const maxMetaSrc = Math.max(1, ...metaSrc.map(m => m.populist))

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Landmark size={18} style={{ color: 'var(--accent)' }} /> Politička analiza
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Narativni akteri i populistički „narod vs. elite" meta-framing
        </p>
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
          <Users size={13} style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Narativni akteri</span>
          <span className="text-xs ml-auto flex gap-2" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#60a5fa' }} />pro-vlada</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#6b7280' }} />neutralno</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#f87171' }} />opozicija</span>
          </span>
        </div>
        {actors.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
            Nema označenih političkih aktera. Popunjava se kako AI analiza obrađuje nove članke.
          </div>
        ) : actors.map(a => <ActorRow key={a.id} a={a} />)}
      </div>

      {/* Meta-framing */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>„Narod vs. elite" po izvoru</h2>
          {metaSrc.length === 0 ? <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Nema podataka još.</p> :
            <div className="space-y-2">
              {metaSrc.slice(0, 12).map(m => (
                <div key={m.source_id} className="flex items-center gap-3">
                  <span className="text-xs font-mono w-20" style={{ color: 'var(--text-secondary)' }}>{m.source_id}</span>
                  <div className="flex-1 h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                    <div className="h-full rounded-full" style={{ width: `${(m.populist / maxMetaSrc) * 100}%`, background: '#8b5cf6' }} />
                  </div>
                  <span className="text-xs tabular-nums w-16 text-right" style={{ color: 'var(--text-muted)' }}>{m.populist} ({Math.round(m.share * 100)}%)</span>
                </div>
              ))}
            </div>}
        </div>
        <div className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>„Narod vs. elite" po temi</h2>
          {metaTopic.length === 0 ? <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Nema podataka još.</p> :
            <div className="space-y-2">
              {metaTopic.slice(0, 12).map(m => (
                <div key={m.topic} className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{TOPIC_LABELS[m.topic] || m.topic}</span>
                  <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{m.populist} ({Math.round(m.share * 100)}%)</span>
                </div>
              ))}
            </div>}
        </div>
      </div>

      {actorsData?.methodology_note && (
        <p className="text-xs flex items-start gap-1.5 italic" style={{ color: 'var(--text-muted)' }}>
          <AlertTriangle size={12} className="mt-0.5 shrink-0" style={{ color: '#f59e0b' }} /> {actorsData.methodology_note}
        </p>
      )}
    </div>
  )
}
