import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Landmark, Users, AlertTriangle, Shield, Globe, GitMerge, Unlink, ChevronDown, ChevronUp } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import api from '../lib/api'

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU integracije', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJSKE_SLOBODE: 'Medijske slobode', MEDIJI_SLOBODA: 'Medijske slobode',
  PROTEST: 'Protest', KULTURA: 'Kultura', ZABAVA_I_ESTRADA: 'Zabava i estrada', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna politika', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}

const PROPAGANDA_LABELS = {
  DEMONIZACIJA: 'Demonizacija', DEZINFORMACIJA: 'Dezinformacija',
  CONSPIRACY_THEORY: 'Teorija zavere', FEAR_APPEAL: 'Apel na strah',
  FALSE_DICHOTOMY: 'Lažna dihotomija', SCAPEGOATING: 'Žrtveni jarac',
  DEFAMATION: 'Kleveta', SMEAR_CAMPAIGN: 'Blatna kampanja',
  WHATABOUTISM: 'Whataboutism', CHERRY_PICKING: 'Selektivni fakti',
  EMOTIONAL_APPEAL: 'Emotivni apel',
  FAR_RIGHT_NARRATIVE: 'Desničarski narativ',
  ULTRA_RIGHT_NARRATIVE: 'Ultradesničarski narativ',
}

const TARGET_GROUP_LABELS = {
  civil_society: 'Civilno društvo / NVO',
  opposition: 'Opozicija',
  students: 'Studenti / protesti',
  media: 'Mediji / novinari',
  other: 'Ostalo',
}

const TARGET_GROUP_COLORS = {
  civil_society: '#8b5cf6',
  opposition: '#3b82f6',
  students: '#f59e0b',
  media: '#06b6d4',
  other: '#6b7280',
}

function SentimentBar({ pos, neg, neu }) {
  const total = (pos + neg + neu) || 1
  return (
    <div className="flex h-2 rounded-full overflow-hidden w-full"
      title={`pozitivno ${pos} / neutralno ${neu} / negativno ${neg}`}>
      <div style={{ width: `${(pos / total) * 100}%`, background: '#22c55e' }} />
      <div style={{ width: `${(neu / total) * 100}%`, background: '#6b7280' }} />
      <div style={{ width: `${(neg / total) * 100}%`, background: '#ef4444' }} />
    </div>
  )
}

function ActorRow({ a }) {
  const navigate = useNavigate()
  const total = (a.positive_mentions + a.negative_mentions + a.neutral_mentions) || 1
  const pos = (a.positive_mentions / total) * 100
  const neg = (a.negative_mentions / total) * 100
  const neu = (a.neutral_mentions / total) * 100

  const sentColor = a.avg_entity_sentiment != null
    ? a.avg_entity_sentiment > 0.15 ? '#22c55e'
      : a.avg_entity_sentiment < -0.15 ? '#ef4444' : '#6b7280'
    : '#6b7280'

  return (
    <div className="px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-1">
        <button onClick={() => navigate(`/articles?entity_id=${a.id}&entity_name=${encodeURIComponent(a.name)}`)}
          className="text-sm font-medium hover:underline text-left" style={{ color: 'var(--text-primary)' }}>
          {a.name}
        </button>
        <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
          {a.avg_entity_sentiment != null && (
            <span className="tabular-nums font-medium" style={{ color: sentColor }}>
              {a.avg_entity_sentiment > 0 ? '+' : ''}{a.avg_entity_sentiment.toFixed(2)} sent.
            </span>
          )}
          <span>{a.mentions} pom. · {a.source_count} izv.</span>
        </div>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden"
        title={`pozitivno ${a.positive_mentions} / neutralno ${a.neutral_mentions} / negativno ${a.negative_mentions}`}>
        <div style={{ width: `${pos}%`, background: '#22c55e' }} />
        <div style={{ width: `${neu}%`, background: '#6b7280' }} />
        <div style={{ width: `${neg}%`, background: '#ef4444' }} />
      </div>
      <div className="flex items-center gap-1.5 mt-1.5">
        <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Filtriraj po sentimentu:</span>
        {[['positive', 'pozitivno', '#22c55e'], ['neutral', 'neutralno', '#6b7280'], ['negative', 'negativno', '#ef4444']].map(([key, label, color]) => (
          <button key={key}
            onClick={() => navigate(`/articles?entity_id=${a.id}&entity_name=${encodeURIComponent(a.name)}&entity_sentiment=${key}`)}
            className="text-[10px] px-1.5 py-0.5 rounded border hover:bg-white/[0.04] transition-colors"
            style={{ borderColor: 'var(--border)', color }}>
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

function EntityMergePanel() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('suggestions')
  const [selectedForMerge, setSelectedForMerge] = useState({})

  const { data: suggestionsData, isLoading: loadingSugg } = useQuery({
    queryKey: ['entity-suggestions'],
    queryFn: () => api.get('/entities/suggestions').then(r => r.data),
    enabled: open,
  })
  const { data: groupsData } = useQuery({
    queryKey: ['entity-groups'],
    queryFn: () => api.get('/entities/groups').then(r => r.data),
    enabled: open && activeTab === 'groups',
  })

  const mergeMut = useMutation({
    mutationFn: (body) => api.post('/entities/merge', body).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries(['entity-suggestions'])
      qc.invalidateQueries(['entity-groups'])
      qc.invalidateQueries(['political-actors'])
      setSelectedForMerge({})
    },
  })
  const decoupleMut = useMutation({
    mutationFn: (entityId) => api.delete(`/entities/${entityId}/canonical`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries(['entity-groups'])
      qc.invalidateQueries(['entity-suggestions'])
      qc.invalidateQueries(['political-actors'])
    },
  })

  const suggestions = suggestionsData?.suggestions || []
  const groups = groupsData?.groups || []

  function handleMerge(suggestion) {
    const sel = selectedForMerge[suggestion.normalized] || {}
    const canonicalId = sel.canonical
    if (!canonicalId) return
    const aliasIds = suggestion.entities
      .filter(e => e.id !== canonicalId)
      .map(e => e.id)
    if (!aliasIds.length) return
    mergeMut.mutate({ canonical_id: canonicalId, alias_ids: aliasIds })
  }

  const cardStyle = { background: 'var(--bg-surface)', borderColor: 'var(--border)' }
  const tabBtn = (t) => ({
    padding: '4px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500,
    background: activeTab === t ? 'var(--accent)' : 'transparent',
    color: activeTab === t ? '#fff' : 'var(--text-muted)',
    border: 'none', cursor: 'pointer',
  })

  return (
    <div className="rounded-xl border overflow-hidden" style={cardStyle}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-2.5 border-b flex items-center gap-2 text-left"
        style={{ borderColor: 'var(--border)', background: 'transparent' }}
      >
        <GitMerge size={13} style={{ color: 'var(--text-muted)' }} />
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          Upravljanje akterima
        </span>
        <span className="ml-auto" style={{ color: 'var(--text-muted)' }}>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      {open && (
        <div className="p-4 space-y-4">
          <div className="flex gap-1">
            <button style={tabBtn('suggestions')} onClick={() => setActiveTab('suggestions')}>
              Predlozi ({suggestions.length})
            </button>
            <button style={tabBtn('groups')} onClick={() => setActiveTab('groups')}>
              Aktivne grupe
            </button>
          </div>

          {activeTab === 'suggestions' && (
            <div className="space-y-2">
              {loadingSugg && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Učitavanje...</p>}
              {!loadingSugg && suggestions.length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Nema predloga za spajanje.</p>
              )}
              {suggestions.map(sg => {
                const sel = selectedForMerge[sg.normalized] || {}
                return (
                  <div key={sg.normalized} className="rounded-lg border p-3 space-y-2"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-base)' }}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--border)', color: 'var(--text-muted)' }}>
                        {sg.entity_type}
                      </span>
                      {sg.entities.map(e => (
                        <label key={e.id} className="flex items-center gap-1 text-xs cursor-pointer"
                          style={{ color: sel.canonical === e.id ? 'var(--accent)' : 'var(--text-primary)' }}>
                          <input
                            type="radio"
                            name={`canon-${sg.normalized}`}
                            checked={sel.canonical === e.id}
                            onChange={() => setSelectedForMerge(s => ({ ...s, [sg.normalized]: { canonical: e.id } }))}
                          />
                          {e.name}
                        </label>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Izaberi kanonski → ostali postaju aliasi
                      </span>
                      <button
                        disabled={!sel.canonical || mergeMut.isPending}
                        onClick={() => handleMerge(sg)}
                        className="ml-auto text-xs px-3 py-1 rounded"
                        style={{
                          background: sel.canonical ? 'var(--accent)' : 'var(--border)',
                          color: sel.canonical ? '#fff' : 'var(--text-muted)',
                          border: 'none', cursor: sel.canonical ? 'pointer' : 'default',
                        }}
                      >
                        Spoji
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {activeTab === 'groups' && (
            <div className="space-y-2">
              {groups.length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Nema aktivnih grupacija.</p>
              )}
              {groups.map(g => (
                <div key={g.canonical_id} className="rounded-lg border p-3"
                  style={{ borderColor: 'var(--border)', background: 'var(--bg-base)' }}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {g.canonical_name}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--border)', color: 'var(--text-muted)' }}>
                      {g.entity_type}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(g.aliases || []).map(a => (
                      <div key={a.id} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded"
                        style={{ background: 'var(--border)', color: 'var(--text-muted)' }}>
                        {a.name}
                        <button
                          onClick={() => decoupleMut.mutate(a.id)}
                          title="Odvoji iz grupe"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, lineHeight: 1 }}
                        >
                          <Unlink size={11} style={{ color: '#ef4444' }} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Political() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isResearcher = user?.role === 'researcher' || user?.role === 'admin'
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  const { data: actorsData } = useQuery({
    queryKey: ['political-actors', filterParams],
    queryFn: () => api.get(`/political/actors?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })
  const { data: propagandaData } = useQuery({
    queryKey: ['political-propaganda', filterParams],
    queryFn: () => api.get(`/political/propaganda?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })
  const { data: geoData } = useQuery({
    queryKey: ['political-geopolitical', filterParams],
    queryFn: () => api.get(`/political/geopolitical?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })

  const actors = actorsData?.actors || []
  const byTechnique = propagandaData?.by_technique || []
  const bySrcProp = propagandaData?.by_source || []
  const byTargetGroup = propagandaData?.by_target_group || []
  const geoActors = geoData?.by_actor || []
  const maxTech = Math.max(1, ...byTechnique.map(t => t.count))

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Landmark size={18} style={{ color: 'var(--accent)' }} /> Politička analiza
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Narativni akteri, entitetski sentiment i propagandne tehnike
        </p>
      </div>

      {/* Legenda */}
      <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#22c55e' }} />Pozitivni sentiment</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#6b7280' }} />Neutralni sentiment</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: '#ef4444' }} />Negativni sentiment</span>
        <span className="ml-auto flex items-center gap-1 italic">Klik na aktere → filtrirani članci</span>
      </div>

      {/* Akteri */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
          <Users size={13} style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Narativni akteri ({actors.length})
          </span>
        </div>
        {actors.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
            Nema označenih političkih aktera. Popunjava se kako AI analiza obrađuje nove članke.
          </div>
        ) : actors.map(a => <ActorRow key={a.id} a={a} />)}
      </div>

      {/* Propaganda */}
      {(byTechnique.length > 0 || bySrcProp.length > 0) && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
            <Shield size={13} style={{ color: '#ef4444' }} />
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Propagandne tehnike
            </span>
          </div>
          <div className="p-4 grid grid-cols-2 gap-6">
            {/* By technique */}
            <div>
              <h3 className="text-xs font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>Po tehnici</h3>
              <div className="space-y-2">
                {byTechnique.map(t => (
                  <button key={t.technique}
                    onClick={() => navigate(`/articles?propaganda_technique=${encodeURIComponent(t.technique)}`)}
                    className="flex items-center gap-3 w-full text-left rounded hover:bg-white/[0.03] px-1 -mx-1 transition-colors"
                    title="Prikaži članke sa ovom tehnikom">
                    <span className="text-xs w-40 truncate" style={{ color: 'var(--text-secondary)' }}>
                      {PROPAGANDA_LABELS[t.technique] || t.technique}
                    </span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                      <div className="h-full rounded-full" style={{ width: `${(t.count / maxTech) * 100}%`, background: '#ef4444' }} />
                    </div>
                    <span className="text-xs tabular-nums w-8 text-right" style={{ color: 'var(--text-muted)' }}>{t.count}</span>
                  </button>
                ))}
              </div>
            </div>
            {/* By source */}
            <div>
              <h3 className="text-xs font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>Po izvoru</h3>
              <div className="space-y-2">
                {bySrcProp.slice(0, 12).map(s => (
                  <div key={s.source_id} className="flex items-center gap-3">
                    <button onClick={() => navigate(`/articles?source_ids=${s.source_id}`)}
                      title="Prikaži članke ovog medija"
                      className="text-xs font-mono w-20 text-left hover:underline" style={{ color: '#a5b4fc' }}>{s.source_id}</button>
                    <div className="flex flex-1 gap-0.5">
                      {Object.entries(s.techniques).slice(0, 4).map(([tech, cnt]) => (
                        <span key={tech} className="text-[9px] px-1 rounded truncate"
                          style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}
                          title={`${PROPAGANDA_LABELS[tech] || tech}: ${cnt}`}>
                          {PROPAGANDA_LABELS[tech]?.slice(0, 6) || tech.slice(0, 6)}
                        </span>
                      ))}
                    </div>
                    <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{s.total}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Smear kampanje po target grupi */}
          {byTargetGroup.length > 0 && (
            <div className="px-4 pb-4 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-xs font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                Mete smear kampanja / kleveta
              </h3>
              <div className="flex flex-wrap gap-2">
                {byTargetGroup.map(tg => (
                  <span key={tg.target_group} className="text-xs px-2 py-1 rounded-full font-medium"
                    style={{
                      background: `${TARGET_GROUP_COLORS[tg.target_group] || '#6b7280'}22`,
                      color: TARGET_GROUP_COLORS[tg.target_group] || '#6b7280',
                      border: `1px solid ${TARGET_GROUP_COLORS[tg.target_group] || '#6b7280'}44`,
                    }}>
                    {TARGET_GROUP_LABELS[tg.target_group] || tg.target_group} · {tg.count}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="px-4 py-2 text-xs border-t italic" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
            Propaganda detekcija je eksperimentalna — primenjuje se na nove članke od implementacije.
          </div>
        </div>
      )}

      {/* Geopolitički sentiment */}
      {geoActors.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
            <Globe size={13} style={{ color: '#3b82f6' }} />
            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              Geopolitički sentiment
            </span>
            <span className="ml-auto text-xs italic" style={{ color: 'var(--text-muted)' }}>
              kako srpski mediji prikazuju geopolitičke aktere
            </span>
          </div>
          <div className="p-4 space-y-3">
            {geoActors.map(g => {
              const sent = g.avg_sentiment
              const isPos = sent >= 0
              const barPct = Math.abs(sent) * 50
              const color = sent > 0.1 ? '#22c55e' : sent < -0.1 ? '#ef4444' : '#6b7280'
              return (
                <div key={g.actor} className="flex items-center gap-3">
                  <span className="text-sm font-medium w-14" style={{ color: 'var(--text-primary)' }}>{g.actor}</span>
                  {/* Diverging bar */}
                  <div className="flex-1 flex items-center">
                    <div className="flex-1 h-3 flex justify-end" style={{ paddingRight: '50%' }}>
                      {!isPos && (
                        <div className="h-full rounded-l-full" style={{ width: `${barPct * 2}%`, background: '#ef4444' }} />
                      )}
                    </div>
                    <div className="w-px h-4 shrink-0" style={{ background: 'var(--border)' }} />
                    <div className="flex-1 h-3 flex justify-start" style={{ paddingLeft: '0%' }}>
                      {isPos && (
                        <div className="h-full rounded-r-full" style={{ width: `${barPct * 2}%`, background: '#22c55e' }} />
                      )}
                    </div>
                  </div>
                  <span className="text-xs tabular-nums w-12 text-right font-medium" style={{ color }}>
                    {sent > 0 ? '+' : ''}{sent.toFixed(2)}
                  </span>
                  <span className="text-xs w-16 text-right" style={{ color: 'var(--text-muted)' }}>
                    {g.article_count} čl.
                  </span>
                </div>
              )
            })}
          </div>
          <div className="px-4 py-2 text-xs border-t flex items-center gap-6" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1"><span className="w-3 h-1.5 rounded inline-block" style={{ background: '#ef4444' }} /> negativan tretman</span>
            <span className="flex items-center gap-1"><span className="w-3 h-1.5 rounded inline-block" style={{ background: '#22c55e' }} /> pozitivan tretman</span>
            <span className="ml-auto italic">{geoData?.methodology_note}</span>
          </div>
        </div>
      )}

      {actorsData?.methodology_note && (
        <p className="text-xs flex items-start gap-1.5 italic" style={{ color: 'var(--text-muted)' }}>
          <AlertTriangle size={12} className="mt-0.5 shrink-0" style={{ color: '#f59e0b' }} /> {actorsData.methodology_note}
        </p>
      )}

      {isResearcher && <EntityMergePanel />}
    </div>
  )
}
