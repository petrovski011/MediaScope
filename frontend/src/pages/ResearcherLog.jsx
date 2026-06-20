import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ClipboardList, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../lib/api'

const ACTION_LABELS = {
  approve: 'Prihvaćeno',
  accept: 'Prihvaćeno',
  reject: 'Odbijeno',
  validate: 'Validirano',
  unvalidate: 'Vraćena validacija',
  edit: 'Uređeno',
}

const ENTITY_LABELS = {
  narrative_cluster: 'narativ (klaster)',
  narrative: 'narativ',
  framing_proposal: 'framing predlog',
  topic_proposal: 'predlog teme',
  entity: 'entitet',
}

const ACTION_TYPES = ['approve', 'reject', 'validate', 'unvalidate', 'accept', 'edit']

export default function ResearcherLog() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [actionType, setActionType] = useState('')
  const PER_PAGE = 20

  const { data, isLoading } = useQuery({
    queryKey: ['researcher-log', page, actionType],
    queryFn: () => api.get(`/researcher-log?page=${page}&per_page=${PER_PAGE}${actionType ? `&action_type=${actionType}` : ''}`).then(r => r.data),
    keepPreviousData: true,
  })

  const revert = useMutation({
    mutationFn: (id) => api.post(`/researcher-log/${id}/revert`),
    onSuccess: () => qc.invalidateQueries(['researcher-log']),
  })

  const items = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  const fmtDate = (s) => s ? new Date(s).toLocaleString('sr-Latn', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }) : '—'

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <ClipboardList size={18} style={{ color: 'var(--accent)' }} /> Istraživački log
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Istorija akcija istraživača — validacije, uređivanja, vraćanja
        </p>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <select
          value={actionType}
          onChange={e => { setActionType(e.target.value); setPage(1) }}
          className="text-sm rounded-lg border px-3 py-1.5"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}>
          <option value="">Sve akcije</option>
          {ACTION_TYPES.map(t => (
            <option key={t} value={t}>{ACTION_LABELS[t]}</option>
          ))}
        </select>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{total} ukupno</span>
      </div>

      {/* Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--bg-elevated)' }}>
            <tr>
              {['Vreme', 'Korisnik', 'Akcija', 'Entitet', ''].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide"
                  style={{ color: 'var(--text-muted)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje…</td></tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nema zabeleženih akcija.</td></tr>
            )}
            {items.map(item => (
              <tr key={item.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                <td className="px-4 py-2.5 text-xs tabular-nums whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                  {fmtDate(item.created_at)}
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {item.user_email || item.user_id || '—'}
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-xs px-2 py-0.5 rounded"
                    style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                    {ACTION_LABELS[item.action_type] || item.action_type}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-primary)' }}>
                  {ENTITY_LABELS[item.entity_type] || item.entity_type} #{item.entity_id}
                  {item.old_status && item.new_status && (
                    <span className="ml-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      {item.old_status} → {item.new_status}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {item.is_revertible && !item.reverted_at && (
                    <button
                      onClick={() => revert.mutate(item.id)}
                      disabled={revert.isPending}
                      className="flex items-center gap-1 px-2 py-1 rounded text-xs border hover:bg-white/[0.04] disabled:opacity-50"
                      style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                      <RotateCcw size={11} /> Vrati
                    </button>
                  )}
                  {item.reverted_at && (
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      vraćeno {fmtDate(item.reverted_at)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="p-1.5 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{page} / {pages}</span>
          <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
            className="p-1.5 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
