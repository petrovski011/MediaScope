import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, AlertCircle, Info, CheckCheck, Bell } from 'lucide-react'
import api from '../lib/api'

const SEVERITY_CONFIG = {
  high:   { label: 'Visok', color: '#ef4444', bg: 'rgba(239,68,68,0.12)', Icon: AlertTriangle },
  medium: { label: 'Srednji', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', Icon: AlertCircle },
  low:    { label: 'Nizak', color: '#6b7280', bg: 'rgba(107,114,128,0.12)', Icon: Info },
}

const TYPE_LABELS = {
  coordination_copy: 'Koordinirano kopiranje',
  topic_spike:       'Topic spike',
  scraper_gap:       'Scraper gap',
}

function AlertCard({ alert, onRead }) {
  const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low
  const Icon = cfg.Icon
  return (
    <div className="flex items-start gap-3 px-4 py-3 border-b last:border-0 transition-colors"
      style={{ borderColor: 'var(--border)', opacity: alert.is_read ? 0.55 : 1 }}>
      <div className="shrink-0 mt-0.5 p-1.5 rounded" style={{ background: cfg.bg }}>
        <Icon size={13} style={{ color: cfg.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{alert.title}</span>
          <span className="text-xs px-1.5 py-0.5 rounded shrink-0"
            style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
            {TYPE_LABELS[alert.alert_type] || alert.alert_type}
          </span>
        </div>
        {alert.description && (
          <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{alert.description}</p>
        )}
        {alert.source_ids?.length > 0 && (
          <div className="flex gap-1 mt-1 flex-wrap">
            {alert.source_ids.map(s => (
              <span key={s} className="text-xs px-1.5 py-0.5 rounded"
                style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>{s}</span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-3 mt-1">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{alert.date}</span>
          {alert.score != null && (
            <span className="text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>
              score: {alert.score.toFixed(2)}
            </span>
          )}
        </div>
      </div>
      {!alert.is_read && (
        <button onClick={() => onRead(alert.id)}
          className="shrink-0 text-xs px-2 py-1 rounded border transition-colors hover:bg-white/[0.04]"
          style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
          Pročitano
        </button>
      )}
    </div>
  )
}

export default function Alerts() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [severity, setSeverity] = useState('')
  const qc = useQueryClient()

  const params = new URLSearchParams({ limit: 100 })
  if (unreadOnly) params.set('unread_only', 'true')
  if (severity) params.set('severity', severity)

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', unreadOnly, severity],
    queryFn: () => api.get(`/alerts?${params}`).then(r => r.data),
    refetchInterval: 60000,
  })

  const readMutation = useMutation({
    mutationFn: id => api.patch(`/alerts/${id}/read`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries(['alerts']),
  })

  const readAllMutation = useMutation({
    mutationFn: () => api.patch('/alerts/read-all').then(r => r.data),
    onSuccess: () => qc.invalidateQueries(['alerts']),
  })

  const alerts = data?.alerts || []
  const unreadCount = data?.unread_count || 0

  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Upozorenja</h1>
            {unreadCount > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ background: '#ef4444', color: '#fff' }}>{unreadCount}</span>
            )}
          </div>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Koordinacija, anomalije i problemi sa scraperima
          </p>
        </div>
        {unreadCount > 0 && (
          <button onClick={() => readAllMutation.mutate()}
            disabled={readAllMutation.isPending}
            className="flex items-center gap-1.5 text-xs px-3 py-2 rounded border transition-colors hover:bg-white/[0.04] disabled:opacity-50"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <CheckCheck size={13} /> Označi sve kao pročitano
          </button>
        )}
      </div>

      {/* Filteri */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <button onClick={() => setUnreadOnly(v => !v)}
          className="text-xs px-3 py-1.5 rounded border transition-colors"
          style={{
            borderColor: unreadOnly ? '#3b82f6' : 'var(--border)',
            color: unreadOnly ? '#60a5fa' : 'var(--text-secondary)',
            background: unreadOnly ? 'rgba(59,130,246,0.1)' : 'transparent',
          }}>
          Samo nepročitana
        </button>
        {['', 'high', 'medium', 'low'].map(s => (
          <button key={s} onClick={() => setSeverity(s)}
            className="text-xs px-3 py-1.5 rounded border transition-colors"
            style={{
              borderColor: severity === s ? '#3b82f6' : 'var(--border)',
              color: severity === s ? '#60a5fa' : 'var(--text-secondary)',
              background: severity === s ? 'rgba(59,130,246,0.1)' : 'transparent',
            }}>
            {s === '' ? 'Sve' : (SEVERITY_CONFIG[s]?.label || s)}
          </button>
        ))}
      </div>

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        {isLoading ? (
          <div className="px-4 py-8 text-sm text-center" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
        ) : alerts.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <Bell size={24} className="mx-auto mb-2" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Nema upozorenja za prikaz.</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Detekcija se pokreće automatski svakog jutra u 08:00.
            </p>
          </div>
        ) : (
          alerts.map(a => (
            <AlertCard key={a.id} alert={a} onRead={id => readMutation.mutate(id)} />
          ))
        )}
      </div>
    </div>
  )
}
