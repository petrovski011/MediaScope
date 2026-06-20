import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, User, Building2, MapPin, Copy } from 'lucide-react'
import api from '../lib/api'

function SimilarArticles({ articleId }) {
  const navigate = useNavigate()
  const { data } = useQuery({
    queryKey: ['similar', articleId],
    queryFn: () => api.get(`/coordination/similar/${articleId}?limit=5`).then(r => r.data),
    retry: false,
  })
  const items = data?.similar?.filter(s => s.similarity_score >= 0.5) || []
  if (!items.length) return null

  return (
    <div className="rounded-xl border mb-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
        <Copy size={13} style={{ color: '#f59e0b' }} />
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Slični članci iz drugih izvora
        </h2>
        <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }}>
          {items.length}
        </span>
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {items.map(s => (
          <div key={s.id} onClick={() => navigate(`/articles/${s.id}`)}
            className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-white/[0.02] transition-colors">
            <span className="text-xs px-2 py-0.5 rounded shrink-0"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
              {s.source_id}
            </span>
            <span className="text-sm flex-1 truncate" style={{ color: 'var(--text-primary)' }}>{s.title}</span>
            <span className="text-xs tabular-nums shrink-0" style={{ color: '#f59e0b' }}>
              {Math.round(s.similarity_score * 100)}% slično
            </span>
            {s.political_score != null && (
              <span className="text-xs tabular-nums shrink-0" style={{
                color: s.political_score > 0.3 ? '#ef4444' : s.political_score < -0.3 ? '#3b82f6' : '#6b7280'
              }}>
                {s.political_score > 0 ? '+' : ''}{s.political_score.toFixed(2)}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="px-4 py-2 text-xs border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        {data?.methodology_note}
      </div>
    </div>
  )
}

const FRAMING_LABELS = {
  threat_frame:   'Okvir pretnje',
  conflict_frame: 'Okvir sukoba',
  victim_frame:   'Okvir žrtve',
  progress_frame: 'Okvir napretka',
  morality_frame: 'Moralni okvir',
}

const TOPIC_LABELS = {
  POLITIKA:'Politika', EU_INTEGRACIJE:'EU integracije', KOSOVO:'Kosovo',
  EKONOMIJA:'Ekonomija', INFRASTRUKTURA:'Infrastruktura', BEZBEDNOST:'Bezbednost',
  MEDIJI_SLOBODA:'Mediji i sloboda', PROTEST:'Protest', KULTURA:'Kultura', SPORT:'Sport',
  HRONIKA:'Hronika', ZDRAVLJE:'Zdravlje', OBRAZOVANJE:'Obrazovanje',
  SPOLJNA_POLITIKA:'Spoljna politika', LOKALNA_VLAST:'Lokalna vlast', DRUSTVO:'Društvo',
}

const ENTITY_ICONS = { person: User, organization: Building2, location: MapPin }

function ScoreGauge({ value, label, min = -1, max = 1 }) {
  if (value == null) return null
  const pct = ((value - min) / (max - min)) * 100
  const color = value > 0.3 ? '#ef4444' : value < -0.3 ? '#3b82f6' : '#6b7280'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ color: 'var(--text-primary)' }}>{value > 0 ? '+' : ''}{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

export default function ArticleDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data: article, isLoading } = useQuery({
    queryKey: ['article', id],
    queryFn: () => api.get(`/articles/${id}`).then(r => r.data),
  })

  if (isLoading) return <div className="p-6 text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
  if (!article) return <div className="p-6 text-sm" style={{ color: 'var(--text-muted)' }}>Članak nije pronađen.</div>

  const a = article
  const analysis = a.analysis

  return (
    <div className="p-6 max-w-4xl">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm mb-5 transition-colors hover:text-white"
        style={{ color: 'var(--text-muted)' }}>
        <ArrowLeft size={14} /> Nazad
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
            {a.source_id}
          </span>
          {a.category && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{a.category}</span>}
          {a.published_at && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {new Date(a.published_at).toLocaleDateString('sr-Latn', { day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
          )}
        </div>
        <h1 className="text-xl font-semibold leading-snug mb-2" style={{ color: 'var(--text-primary)' }}>{a.title}</h1>
        {a.subtitle && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{a.subtitle}</p>}
        <a href={a.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs mt-2 hover:underline"
          style={{ color: 'var(--text-muted)' }}>
          <ExternalLink size={11} /> Otvori originalni članak
        </a>
      </div>

      <SimilarArticles articleId={id} />

      <div className="grid grid-cols-3 gap-4">
        {/* Leva kolona — tekst */}
        <div className="col-span-2 space-y-4">
          {a.text_content && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Tekst članka</h2>
              <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                {a.text_content.slice(0, 3000)}{a.text_content.length > 3000 ? '...' : ''}
              </p>
            </div>
          )}

          {/* Entiteti */}
          {a.entities?.length > 0 && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Detektovani akteri</h2>
              <div className="space-y-2">
                {a.entities.map((e, i) => {
                  const Icon = ENTITY_ICONS[e.entity_type] || User
                  return (
                    <div key={i} className="flex items-start gap-2.5 py-2 border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                      <Icon size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--text-muted)' }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{e.name}</span>
                          {e.is_quoted && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa' }}>citiran</span>}
                          {e.is_subject && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }}>subjekt</span>}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{e.entity_type}</span>
                          {e.mention_count > 1 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>· {e.mention_count}× pomenuto</span>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Narativni okviri */}
          {a.framings?.length > 0 && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Narativni okviri</h2>
              <div className="space-y-2">
                {a.framings.map((f, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                        {FRAMING_LABELS[f.framing_name] || f.framing_description || f.framing_name}
                        {f.topic_key ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--accent)', color: 'white' }}>
                            {TOPIC_LABELS[f.topic_key] || f.topic_key}
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                            globalni
                          </span>
                        )}
                      </span>
                      <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
                        {Math.round((f.confidence || 0) * 100)}%
                      </span>
                    </div>
                    {f.supporting_text && (
                      <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>"{f.supporting_text}"</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Desna kolona — analiza */}
        <div className="space-y-4">
          {analysis ? (
            <>
              <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
                <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>AI analiza</h2>
                <div className="space-y-3">
                  {analysis.primary_topic && (
                    <div>
                      <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Primarna tema</div>
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {TOPIC_LABELS[analysis.primary_topic] || analysis.primary_topic}
                      </span>
                      {analysis.topic_confidence && (
                        <span className="text-xs ml-1.5" style={{ color: 'var(--text-muted)' }}>
                          ({Math.round(analysis.topic_confidence * 100)}%)
                        </span>
                      )}
                    </div>
                  )}

                  {analysis.sentiment && (
                    <div>
                      <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Sentiment</div>
                      <span className="text-sm" style={{
                        color: analysis.sentiment === 'positive' ? '#22c55e'
                          : analysis.sentiment === 'negative' ? '#ef4444' : 'var(--text-secondary)'
                      }}>
                        {analysis.sentiment === 'positive' ? 'Pozitivan'
                          : analysis.sentiment === 'negative' ? 'Negativan'
                          : analysis.sentiment === 'neutral' ? 'Neutralan' : 'Mešovit'}
                      </span>
                    </div>
                  )}
                  {analysis.topic_explanation && (
                    <details className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      <summary className="cursor-pointer hover:text-white transition-colors">Obrazloženje teme</summary>
                      <p className="mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{analysis.topic_explanation}</p>
                    </details>
                  )}
                </div>
              </div>

              <div className="rounded-xl p-4 border space-y-3" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
                <h2 className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Skorovi</h2>
                <ScoreGauge value={analysis.political_score} label="Politički (-1 opoz. / +1 pro-vlada)" />
                {analysis.political_explanation && (
                  <details className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    <summary className="cursor-pointer hover:text-white transition-colors">Obrazloženje</summary>
                    <p className="mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{analysis.political_explanation}</p>
                  </details>
                )}
                <ScoreGauge value={analysis.value_score} label="Vrednosni (-1 progres. / +1 konzervat.)" />
                {analysis.value_explanation && (
                  <details className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    <summary className="cursor-pointer hover:text-white transition-colors">Obrazloženje</summary>
                    <p className="mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{analysis.value_explanation}</p>
                  </details>
                )}
                <ScoreGauge value={analysis.sentiment_score} label="Sentiment score (-1 neg. / +1 poz.)" />
                <ScoreGauge value={analysis.sensationalism} label="Senzacionalizam" min={0} max={1} />
              </div>

              <div className="rounded-xl p-3 border text-xs" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                Model: {analysis.model_used}<br />
                Pipeline v{analysis.analysis_version}
              </div>
            </>
          ) : (
            <div className="rounded-xl p-4 border text-sm" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              Ovaj članak još nije analiziran.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
