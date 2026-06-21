import { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { useQuery } from '@tanstack/react-query'
import { Search, ChevronLeft, ChevronRight, Download, X } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useAuth } from '../store/auth'
import api from '../lib/api'

const TOPICS = [
  'POLITIKA','EU_INTEGRACIJE','KOSOVO','EKONOMIJA','INFRASTRUKTURA',
  'BEZBEDNOST','MEDIJSKE_SLOBODE','MEDIJI_SLOBODA','PROTEST','KULTURA','ZABAVA_I_ESTRADA',
  'SPORT','HRONIKA','ZDRAVLJE','OBRAZOVANJE','SPOLJNA_POLITIKA','LOKALNA_VLAST','DRUSTVO',
]
const TOPIC_LABELS = {
  POLITIKA:'Politika', EU_INTEGRACIJE:'EU integracije', KOSOVO:'Kosovo',
  EKONOMIJA:'Ekonomija', INFRASTRUKTURA:'Infrastruktura', BEZBEDNOST:'Bezbednost',
  MEDIJSKE_SLOBODE:'Medijske slobode', MEDIJI_SLOBODA:'Medijske slobode',
  PROTEST:'Protest', KULTURA:'Kultura', ZABAVA_I_ESTRADA:'Zabava i estrada', SPORT:'Sport',
  HRONIKA:'Hronika', ZDRAVLJE:'Zdravlje', OBRAZOVANJE:'Obrazovanje',
  SPOLJNA_POLITIKA:'Spoljna politika', LOKALNA_VLAST:'Lokalna vlast', DRUSTVO:'Društvo',
}

function PoliticalDot({ score }) {
  if (score == null) return null
  const color = score > 0.3 ? '#ef4444' : score < -0.3 ? '#3b82f6' : '#6b7280'
  return (
    <span className="inline-flex items-center gap-1 text-xs" style={{ color }}>
      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: color }} />
      {score > 0 ? '+' : ''}{score.toFixed(2)}
    </span>
  )
}

export default function Articles() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { token } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [topic, setTopic] = useState('')
  const [hasAnalysis, setHasAnalysis] = useState('')
  const [exporting, setExporting] = useState(false)

  const { dateFrom, dateTo, selectedSources } = useFilters()
  const globalParams = toParams({ dateFrom, dateTo, selectedSources })

  const entityId = searchParams.get('entity_id')
  const entityName = searchParams.get('entity_name')
  const entitySentiment = searchParams.get('entity_sentiment')
  const framingTypeId = searchParams.get('framing_type_id')
  const framingName = searchParams.get('framing_name')
  const urlSourceIds = searchParams.get('source_ids')
  const narrativeClusterId = searchParams.get('narrative_cluster_id')

  useEffect(() => { setPage(1) }, [dateFrom, dateTo, selectedSources.join(','), entityId, entitySentiment, framingTypeId, urlSourceIds, narrativeClusterId])

  const params = new URLSearchParams({ page, per_page: 25, ...globalParams })
  if (search) params.set('search', search)
  if (topic) params.set('topic', topic)
  if (hasAnalysis) params.set('has_analysis', hasAnalysis)
  if (entityId) params.set('entity_id', entityId)
  if (entitySentiment) params.set('entity_sentiment', entitySentiment)
  if (framingTypeId) params.set('framing_type_id', framingTypeId)
  if (urlSourceIds) params.set('source_ids', urlSourceIds)
  if (narrativeClusterId) params.set('narrative_cluster_id', narrativeClusterId)

  const { data, isLoading } = useQuery({
    queryKey: ['articles', page, search, topic, hasAnalysis, dateFrom, dateTo, selectedSources.join(','), entityId, entitySentiment, framingTypeId, urlSourceIds, narrativeClusterId],
    queryFn: () => api.get(`/articles?${params}`).then(r => r.data),
    keepPreviousData: true,
  })

  const handleSearch = e => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const exportParams = new URLSearchParams(globalParams)
      if (search) exportParams.set('search', search)
      if (topic) exportParams.set('topic', topic)
      if (hasAnalysis) exportParams.set('has_analysis', hasAnalysis)

      const res = await fetch(`/api/v1/export/articles.csv?${exportParams}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const blob = await res.blob()
      const rows = res.headers.get('X-Row-Count') || '?'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mediascope_export_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="p-6">
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Članci</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {data?.total ? `${data.total.toLocaleString()} članaka` : ''}
            </p>
            {entityName && (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border"
                style={{ borderColor: '#6366f1', color: '#a5b4fc', background: 'rgba(99,102,241,0.1)' }}>
                entitet: {entityName}
                <button onClick={() => setSearchParams({})} className="hover:text-white transition-colors ml-0.5">
                  <X size={10} />
                </button>
              </span>
            )}
            {framingName && (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border"
                style={{ borderColor: '#8b5cf6', color: '#c4b5fd', background: 'rgba(139,92,246,0.1)' }}>
                framing: {framingName}
                <button onClick={() => setSearchParams({})} className="hover:text-white transition-colors ml-0.5">
                  <X size={10} />
                </button>
              </span>
            )}
          </div>
        </div>
        <button onClick={handleExport} disabled={exporting || !data?.total}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs border transition-colors disabled:opacity-40"
          style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', background: 'var(--bg-surface)' }}>
          <Download size={13} />
          {exporting ? 'Exportujem...' : 'CSV export'}
        </button>
      </div>

      {/* Filteri */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-60">
          <div className="relative flex-1">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              value={searchInput} onChange={e => setSearchInput(e.target.value)}
              placeholder="Pretraži članke (naslov i tekst)..."
              className="w-full pl-8 pr-3 py-2 rounded-lg text-sm border outline-none"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            />
          </div>
          <button type="submit" className="px-3 py-2 rounded-lg text-sm border transition-colors hover:bg-white/5"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            Traži
          </button>
        </form>

        <select value={topic} onChange={e => { setTopic(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg text-sm border outline-none"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
          <option value="">Sve teme</option>
          {TOPICS.map(t => <option key={t} value={t}>{TOPIC_LABELS[t]}</option>)}
        </select>

        <select value={hasAnalysis} onChange={e => { setHasAnalysis(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg text-sm border outline-none"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
          <option value="">Svi članci</option>
          <option value="true">Samo analizirani</option>
          <option value="false">Neanalizirani</option>
        </select>
      </div>

      {/* Tabela */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <table className="w-full">
          <thead>
            <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
              {['Izvor', 'Naslov', 'Tema', 'Political', 'Sens.', 'Datum'].map(h => (
                <th key={h} className="px-4 py-2.5 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {isLoading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</td></tr>
            ) : data?.items?.map(a => (
              <tr key={a.id} onClick={() => navigate(`/articles/${a.id}`)} className="hover:bg-white/[0.02] transition-colors cursor-pointer">
                <td className="px-4 py-2.5">
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                    {a.source_id}
                  </span>
                </td>
                <td className="px-4 py-2.5 max-w-xs">
                  <a href={a.url} target="_blank" rel="noreferrer"
                    className="text-sm hover:underline truncate block" style={{ color: 'var(--text-primary)' }}>
                    {a.title}
                  </a>
                  {a.category && <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>{a.category}</div>}
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {a.analysis_summary?.primary_topic ? (TOPIC_LABELS[a.analysis_summary.primary_topic] || a.analysis_summary.primary_topic) : '—'}
                </td>
                <td className="px-4 py-2.5">
                  <PoliticalDot score={a.analysis_summary?.political_score} />
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {a.analysis_summary?.sensationalism != null ? a.analysis_summary.sensationalism.toFixed(2) : '—'}
                </td>
                <td className="px-4 py-2.5 text-xs whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                  {a.published_at ? new Date(a.published_at).toLocaleDateString('sr-Latn') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Paginacija */}
        {data?.pages > 1 && (
          <div className="px-4 py-3 border-t flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Strana {page} od {data.pages}
            </span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded disabled:opacity-30 hover:bg-white/5 transition-colors"
                style={{ color: 'var(--text-secondary)' }}>
                <ChevronLeft size={14} />
              </button>
              <button onClick={() => setPage(p => Math.min(data.pages, p + 1))} disabled={page === data.pages}
                className="p-1.5 rounded disabled:opacity-30 hover:bg-white/5 transition-colors"
                style={{ color: 'var(--text-secondary)' }}>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
