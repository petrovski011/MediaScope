import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, User, Building2, MapPin, Copy, StickyNote, Trash2, Pencil, Lock, Unlock, Check, X } from 'lucide-react'
import { useAuth } from '../store/auth'
import api from '../lib/api'

const FRAMING_LABELS = {
  threat_frame:'Okvir pretnje', conflict_frame:'Okvir sukoba', victim_frame:'Okvir žrtve',
  progress_frame:'Okvir napretka', morality_frame:'Moralni okvir',
}

const TOPIC_LABELS = {
  POLITIKA:'Politika', EU_INTEGRACIJE:'EU integracije', KOSOVO:'Kosovo',
  EKONOMIJA:'Ekonomija', INFRASTRUKTURA:'Infrastruktura', BEZBEDNOST:'Bezbednost',
  MEDIJSKE_SLOBODE:'Medijske slobode', MEDIJI_SLOBODA:'Medijske slobode',
  PROTEST:'Protest', KULTURA:'Kultura', ZABAVA_I_ESTRADA:'Zabava i estrada', SPORT:'Sport',
  HRONIKA:'Hronika', ZDRAVLJE:'Zdravlje', OBRAZOVANJE:'Obrazovanje',
  SPOLJNA_POLITIKA:'Spoljna politika', LOKALNA_VLAST:'Lokalna vlast', DRUSTVO:'Društvo',
}

const ENTITY_ICONS = { person: User, organization: Building2, location: MapPin }

function initials(name) {
  return (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
}

function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('sr-Latn', { day: 'numeric', month: 'short', year: 'numeric' })
}

function AnnotationsPanel({ articleId }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [isPrivate, setIsPrivate] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editText, setEditText] = useState('')

  const { data } = useQuery({
    queryKey: ['annotations', articleId],
    queryFn: () => api.get(`/articles/${articleId}/annotations`).then(r => r.data.annotations),
  })
  const add = useMutation({
    mutationFn: () => api.post(`/articles/${articleId}/annotations`, { body: text.trim(), is_private: isPrivate }),
    onSuccess: () => { qc.invalidateQueries(['annotations', articleId]); setText(''); setIsPrivate(false) },
  })
  const del = useMutation({
    mutationFn: (id) => api.delete(`/annotations/${id}`),
    onSuccess: () => qc.invalidateQueries(['annotations', articleId]),
  })
  const edit = useMutation({
    mutationFn: ({ id, body }) => api.put(`/annotations/${id}`, { body }),
    onSuccess: () => { qc.invalidateQueries(['annotations', articleId]); setEditingId(null) },
  })

  const notes = data || []
  const canActOn = (n) => user?.id === n.user_id || user?.role === 'admin'

  return (
    <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <h2 className="text-xs font-medium mb-3 uppercase tracking-wider flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
        <StickyNote size={12} /> Beleške ({notes.length})
      </h2>

      <div className="space-y-3 mb-4">
        {notes.length === 0 && (
          <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>Nema beleški za ovaj članak.</p>
        )}
        {notes.map(n => (
          <div key={n.id} className="rounded-lg p-2.5 border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                style={{ background: 'var(--accent)', color: 'white' }}>
                {initials(n.author_name)}
              </div>
              <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{n.author_name}</span>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{fmtDate(n.created_at)}</span>
              {n.is_private && (
                <span className="ml-auto flex items-center gap-0.5 text-[10px]" style={{ color: '#f59e0b' }}>
                  <Lock size={9} /> privatna
                </span>
              )}
            </div>

            {editingId === n.id ? (
              <div className="space-y-1.5">
                <textarea value={editText} onChange={e => setEditText(e.target.value)} rows={3}
                  className="w-full px-2 py-1.5 rounded text-xs border outline-none resize-none"
                  style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
                <div className="flex gap-1.5">
                  <button onClick={() => edit.mutate({ id: n.id, body: editText })} disabled={edit.isPending || !editText.trim()}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs disabled:opacity-50"
                    style={{ background: 'var(--accent)', color: 'white' }}>
                    <Check size={10} /> Sačuvaj
                  </button>
                  <button onClick={() => setEditingId(null)}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs border"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                    <X size={10} /> Odustani
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{n.body}</p>
            )}

            {canActOn(n) && editingId !== n.id && (
              <div className="flex gap-1.5 mt-1.5">
                <button onClick={() => { setEditingId(n.id); setEditText(n.body) }}
                  className="p-0.5 hover:text-white transition-colors" style={{ color: 'var(--text-muted)' }}>
                  <Pencil size={11} />
                </button>
                <button onClick={() => del.mutate(n.id)} disabled={del.isPending}
                  className="p-0.5 hover:text-red-400 transition-colors" style={{ color: 'var(--text-muted)' }}>
                  <Trash2 size={11} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
        <textarea value={text} onChange={e => setText(e.target.value)} rows={2}
          placeholder="Dodaj belešku…"
          className="w-full px-2 py-1.5 rounded text-xs border outline-none resize-none"
          style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none" style={{ color: 'var(--text-muted)' }}>
            <input type="checkbox" checked={isPrivate} onChange={e => setIsPrivate(e.target.checked)} className="w-3 h-3" />
            {isPrivate ? <Lock size={10} /> : <Unlock size={10} />}
            Privatna
          </label>
          <button onClick={() => add.mutate()} disabled={!text.trim() || add.isPending}
            className="px-3 py-1 rounded text-xs font-medium disabled:opacity-50"
            style={{ background: 'var(--accent)', color: 'white' }}>
            {add.isPending ? '…' : 'Dodaj'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SimilarArticles({ articleId }) {
  const navigate = useNavigate()
  const { data } = useQuery({
    queryKey: ['similar', articleId],
    queryFn: () => api.get(`/coordination/similar/${articleId}?limit=5`).then(r => r.data),
    retry: false,
  })
  const items = data?.similar?.filter(s => s.similarity_score >= 0.5) || []
  if (!items.length) return null

  const dated = items.filter(s => s.published_at).map(s => ({ ...s, t: new Date(s.published_at).getTime() }))
    .sort((a, b) => a.t - b.t)
  const undated = items.filter(s => !s.published_at)
  const times = dated.map(s => s.t)
  const min = times.length ? Math.min(...times) : 0
  const max = times.length ? Math.max(...times) : 0
  const pos = t => (max === min ? 50 : ((t - min) / (max - min)) * 100)
  const fmtDay = t => new Date(t).toLocaleDateString('sr-RS', { day: '2-digit', month: '2-digit' })
  const fmtFull = s => new Date(s.published_at).toLocaleString('sr-RS', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-3 py-2 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
        <Copy size={12} style={{ color: '#f59e0b' }} />
        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Slični članci — vremenski</span>
        <span className="text-xs px-1.5 py-0.5 rounded-full ml-auto" style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }}>
          {items.length}
        </span>
      </div>

      {dated.length > 0 && (
        <div className="px-4 pt-6 pb-2">
          <div className="relative h-12">
            {/* osa */}
            <div className="absolute left-0 right-0 top-5 h-px" style={{ background: 'var(--border)' }} />
            {dated.map((s, i) => (
              <div key={s.id} onClick={() => navigate(`/articles/${s.id}`)}
                title={`${s.source_id} · ${Math.round(s.similarity_score * 100)}% · ${fmtFull(s)}\n${s.title}`}
                className="absolute -translate-x-1/2 cursor-pointer group"
                style={{ left: `${pos(s.t)}%`, top: 0 }}>
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-[9px] tabular-nums leading-none" style={{ color: '#f59e0b' }}>
                    {Math.round(s.similarity_score * 100)}%
                  </span>
                  <div className="rounded-full border-2 transition-transform group-hover:scale-125"
                    style={{
                      width: 11, height: 11,
                      background: '#f59e0b',
                      opacity: 0.4 + 0.6 * s.similarity_score,
                      borderColor: 'var(--bg-surface)',
                    }} />
                  <span className="text-[8px] leading-none mt-0.5 px-1 rounded"
                    style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                    {s.source_id}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-1 text-[9px]" style={{ color: 'var(--text-muted)' }}>
            <span>{fmtDay(min)}</span>
            {max !== min && <span>{fmtDay(max)}</span>}
          </div>
        </div>
      )}

      {undated.length > 0 && (
        <div className="px-3 pb-2 pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="text-[9px] mb-1" style={{ color: 'var(--text-muted)' }}>Bez datuma objave:</div>
          <div className="flex flex-wrap gap-1">
            {undated.map(s => (
              <button key={s.id} onClick={() => navigate(`/articles/${s.id}`)}
                title={s.title}
                className="text-[10px] px-1.5 py-0.5 rounded hover:bg-white/[0.04]"
                style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                {s.source_id} · {Math.round(s.similarity_score * 100)}%
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="px-3 py-1.5 text-[10px] border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        {data?.methodology_note}
      </div>
    </div>
  )
}

function ScoreGauge({ value, label, min = -1, max = 1 }) {
  if (value == null) return null
  const pct = ((value - min) / (max - min)) * 100
  const color = value > 0.3 ? '#ef4444' : value < -0.3 ? '#3b82f6' : '#6b7280'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
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
    <div className="p-6 max-w-7xl">
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
          <a href={a.url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-xs ml-auto hover:underline"
            style={{ color: 'var(--text-muted)' }}>
            <ExternalLink size={11} /> Originalni članak
          </a>
        </div>
        <h1 className="text-xl font-semibold leading-snug mb-1" style={{ color: 'var(--text-primary)' }}>{a.title}</h1>
        {a.subtitle && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{a.subtitle}</p>}
      </div>

      {/* 4-col layout: tekst (1-2) | AI+skorovi+akteri (3) | beleške+slični+okviri (4) */}
      <div className="grid grid-cols-12 gap-4">
        {/* Kolone 1-2 — tekst članka */}
        <div className="col-span-6 space-y-4">
          {a.text_content && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Tekst članka</h2>
              <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                {a.text_content.slice(0, 3000)}{a.text_content.length > 3000 ? '...' : ''}
              </p>
            </div>
          )}
        </div>

        {/* Kolona 3 — AI analiza + skorovi + propaganda + model + detektovani akteri */}
        <div className="col-span-3 space-y-4">
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
                      <summary className="cursor-pointer hover:text-white">Obrazloženje teme</summary>
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
                    <summary className="cursor-pointer hover:text-white">Obrazloženje</summary>
                    <p className="mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{analysis.political_explanation}</p>
                  </details>
                )}
                <ScoreGauge value={analysis.value_score} label="Vrednosni (-1 progres. / +1 konzervat.)" />
                {analysis.value_explanation && (
                  <details className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    <summary className="cursor-pointer hover:text-white">Obrazloženje</summary>
                    <p className="mt-1 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{analysis.value_explanation}</p>
                  </details>
                )}
                <ScoreGauge value={analysis.sentiment_score} label="Sentiment score (-1 neg. / +1 poz.)" />
                <ScoreGauge value={analysis.sensationalism} label="Senzacionalizam" min={0} max={1} />
              </div>

              {analysis.propaganda_techniques?.length > 0 && (
                <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
                  <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Propagandne tehnike</h2>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.propaganda_techniques.map(t => (
                      <span key={t} className="text-xs px-2 py-0.5 rounded"
                        style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                  {analysis.propaganda_targets?.length > 0 && (
                    <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                      Meta: {analysis.propaganda_targets.join(', ')}
                    </p>
                  )}
                  {analysis.propaganda_confidence != null && (
                    <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                      Pouzdanost: {Math.round(analysis.propaganda_confidence * 100)}%
                    </p>
                  )}
                </div>
              )}

              <div className="rounded-xl p-3 border text-xs" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                Model: {analysis.model_used}<br />
                Pipeline v{analysis.analysis_version}
                {analysis.analysis_confidence != null && (
                  <> · Pouzdanost {Math.round(analysis.analysis_confidence * 100)}%</>
                )}
              </div>
            </>
          ) : (
            <div className="rounded-xl p-4 border text-sm" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              Ovaj članak još nije analiziran.
            </div>
          )}

          {/* Detektovani akteri — ispod modela (kolona 3) */}
          {a.entities?.length > 0 && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xs font-medium mb-3 uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Detektovani akteri</h2>
              <div className="space-y-2">
                {a.entities.map((e, i) => {
                  const Icon = ENTITY_ICONS[e.entity_type] || User
                  const sentColor = e.sentiment != null
                    ? e.sentiment > 0.2 ? '#22c55e' : e.sentiment < -0.2 ? '#ef4444' : '#6b7280'
                    : null
                  return (
                    <div key={i} className="flex items-start gap-2.5 py-2 border-b last:border-0" style={{ borderColor: 'var(--border)' }}>
                      <Icon size={13} className="mt-0.5 shrink-0" style={{ color: 'var(--text-muted)' }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{e.name}</span>
                          {e.is_quoted && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa' }}>citiran</span>}
                          {e.is_subject && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24' }}>subjekt</span>}
                          {e.sentiment != null && (
                            <span className="text-xs tabular-nums ml-auto" style={{ color: sentColor }}>
                              {e.sentiment > 0 ? '+' : ''}{e.sentiment.toFixed(2)}
                            </span>
                          )}
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
        </div>

        {/* Kolona 4 — beleške + slični članci + narativni okviri */}
        <div className="col-span-3 space-y-4">
          <AnnotationsPanel articleId={id} />
          <SimilarArticles articleId={id} />

          {/* Narativni okviri — ispod sličnih članaka (kolona 4) */}
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
      </div>
    </div>
  )
}
