import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Layers, Plus, Check, X, Sparkles } from 'lucide-react'
import api from '../lib/api'
import { useAuth } from '../store/auth'

const canManage = (role) => role === 'admin' || role === 'researcher'

function ProposalsPanel() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['framing-proposals'],
    queryFn: () => api.get('/framing/proposals?status=pending').then(r => r.data.proposals),
  })
  const approve = useMutation({
    mutationFn: (id) => api.post(`/framing/proposals/${id}/approve`),
    onSuccess: () => { qc.invalidateQueries(['framing-proposals']); qc.invalidateQueries(['framing-types']) },
  })
  const reject = useMutation({
    mutationFn: (id) => api.post(`/framing/proposals/${id}/reject`),
    onSuccess: () => qc.invalidateQueries(['framing-proposals']),
  })

  const proposals = data || []
  if (proposals.length === 0) return null

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={15} style={{ color: '#f59e0b' }} />
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          AI predlozi novih okvira ({proposals.length})
        </h2>
      </div>
      <div className="space-y-2">
        {proposals.map(p => (
          <div key={p.id} className="rounded-xl border p-3 flex items-start justify-between gap-3"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.name}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ background: p.topic_key ? 'var(--accent)' : 'var(--bg-elevated)', color: p.topic_key ? 'white' : 'var(--text-muted)' }}>
                  {p.topic_key || 'globalni'}
                </span>
                {p.occurrences > 1 && (
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>×{p.occurrences}</span>
                )}
              </div>
              {p.description && <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{p.description}</p>}
              {p.supporting_text && <p className="text-xs italic mt-1" style={{ color: 'var(--text-muted)' }}>"{p.supporting_text}"</p>}
            </div>
            <div className="flex gap-1.5 shrink-0">
              <button onClick={() => approve.mutate(p.id)} disabled={approve.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]"
                style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                <Check size={12} /> Prihvati
              </button>
              <button onClick={() => reject.mutate(p.id)} disabled={reject.isPending}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]"
                style={{ borderColor: 'var(--border)', color: '#ef4444' }}>
                <X size={12} /> Odbij
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function CreateForm({ topics }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [topicKey, setTopicKey] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')

  const create = useMutation({
    mutationFn: () => api.post('/framing/types', { name: name.trim(), topic_key: topicKey || null, description: description || null }),
    onSuccess: () => {
      qc.invalidateQueries(['framing-types'])
      setName(''); setTopicKey(''); setDescription(''); setOpen(false); setError('')
    },
    onError: (e) => setError(e.response?.data?.detail || 'Greška'),
  })

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium"
        style={{ background: 'var(--accent)', color: 'white' }}>
        <Plus size={13} /> Novi okvir
      </button>
    )
  }

  const inputCls = "w-full px-3 py-2 rounded-md text-sm border outline-none"
  const inputStyle = { background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }
  return (
    <div className="rounded-xl border p-4 w-full max-w-lg" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="space-y-3">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="naziv_okvira (npr. izdaja_frame)" className={inputCls} style={inputStyle} />
        <select value={topicKey} onChange={e => setTopicKey(e.target.value)} className={inputCls} style={inputStyle}>
          <option value="">Globalni (sve teme)</option>
          {topics.map(t => <option key={t.key} value={t.key}>{t.label_sr}</option>)}
        </select>
        <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Opis okvira" rows={2} className={inputCls} style={inputStyle} />
        {error && <p className="text-xs text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={() => { setOpen(false); setError('') }} className="px-3 py-1.5 text-sm rounded-md border" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>Odustani</button>
          <button onClick={() => create.mutate()} disabled={!name.trim() || create.isPending} className="px-3 py-1.5 text-sm rounded-md font-medium disabled:opacity-50" style={{ background: 'var(--accent)', color: 'white' }}>Sačuvaj</button>
        </div>
      </div>
    </div>
  )
}

export default function Framing() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const manage = canManage(user?.role)

  const { data: typesData } = useQuery({
    queryKey: ['framing-types'],
    queryFn: () => api.get('/framing/types').then(r => r.data.framing_types),
  })
  const { data: topicsData } = useQuery({
    queryKey: ['framing-topics'],
    queryFn: () => api.get('/framing/topics').then(r => r.data.topics),
  })

  const validate = useMutation({
    mutationFn: (id) => api.post(`/framing/types/${id}/validate`),
    onSuccess: () => qc.invalidateQueries(['framing-types']),
  })

  const types = typesData || []
  const topics = topicsData || []

  // grupiši po topic_key (null = globalni)
  const groups = {}
  for (const t of types) {
    const key = t.topic_key || '__global__'
    ;(groups[key] = groups[key] || []).push(t)
  }
  const topicLabel = (key) => key === '__global__' ? 'Globalni okviri (sve teme)' : (topics.find(t => t.key === key)?.label_sr || key)
  const orderedKeys = Object.keys(groups).sort((a, b) => a === '__global__' ? -1 : b === '__global__' ? 1 : a.localeCompare(b))

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Layers size={18} style={{ color: 'var(--accent)' }} />
          <div>
            <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Framing okviri</h1>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Tematski specifični narativni okviri — AI predlaže, istraživač validira</p>
          </div>
        </div>
        {manage && <CreateForm topics={topics} />}
      </div>

      {manage && <ProposalsPanel />}

      <div className="space-y-6">
        {orderedKeys.map(key => (
          <section key={key}>
            <h2 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
              {topicLabel(key)} <span style={{ color: 'var(--text-muted)' }}>({groups[key].length})</span>
            </h2>
            <div className="rounded-xl border divide-y" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              {groups[key].map(t => (
                <div key={t.id} className="px-4 py-2.5 flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{t.name}</span>
                      {!t.is_validated && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#f59e0b33', color: '#f59e0b' }}>nevalidiran</span>
                      )}
                    </div>
                    {t.description && <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{t.description}</p>}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{t.usage_count} čl.</span>
                    {manage && !t.is_validated && (
                      <button onClick={() => validate.mutate(t.id)} className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04]" style={{ borderColor: 'var(--border)', color: '#22c55e' }}>
                        <Check size={12} /> Validiraj
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
