import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Pencil, Trash2, Check, X, ShieldCheck, Eye, Play, Pause, ChevronLeft, ChevronRight, Zap, HardDrive } from 'lucide-react'
import api from '../lib/api'

const ROLES = ['admin', 'researcher', 'viewer']

function Badge({ role }) {
  const colors = {
    admin:   'bg-red-500/20 text-red-300',
    analyst: 'bg-blue-500/20 text-blue-300',
    viewer:  'bg-gray-500/20 text-gray-300',
  }
  const icons = { admin: ShieldCheck, analyst: Eye, viewer: Eye }
  const Icon = icons[role] || Eye
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${colors[role] || colors.viewer}`}>
      <Icon size={10} />{role}
    </span>
  )
}

function UserRow({ user, onEdit, onDelete, currentUserId }) {
  return (
    <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-primary)' }}>{user.name}</td>
      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{user.email}</td>
      <td className="px-4 py-3"><Badge role={user.role} /></td>
      <td className="px-4 py-3 text-sm">
        <span className={`inline-flex items-center gap-1 text-xs ${user.is_active ? 'text-green-400' : 'text-gray-500'}`}>
          {user.is_active ? <Check size={12} /> : <X size={12} />}
          {user.is_active ? 'Aktivan' : 'Neaktivan'}
        </span>
      </td>
      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>
        {user.last_login ? new Date(user.last_login).toLocaleString('sr-Latn') : '—'}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button onClick={() => onEdit(user)}
            className="p-1.5 rounded hover:bg-white/10 transition-colors"
            style={{ color: 'var(--text-muted)' }}>
            <Pencil size={13} />
          </button>
          {user.id !== currentUserId && (
            <button onClick={() => onDelete(user)}
              className="p-1.5 rounded hover:bg-red-500/20 transition-colors text-red-400">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

function EditModal({ user, onClose, onSave }) {
  const [name, setName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [role, setRole] = useState(user?.role || 'viewer')
  const [password, setPassword] = useState('')
  const [isActive, setIsActive] = useState(user?.is_active ?? true)
  const [error, setError] = useState('')

  const handleSave = async () => {
    setError('')
    try {
      await onSave({ name, email, role, password: password || undefined, is_active: isActive })
      onClose()
    } catch (e) {
      setError(e.response?.data?.detail || 'Greška pri čuvanju')
    }
  }

  const isNew = !user?.id
  const inputCls = "w-full px-3 py-2 rounded-md text-sm border outline-none focus:border-blue-500"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)' }}>
      <div className="w-full max-w-md rounded-xl border p-6" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-base font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          {isNew ? 'Novi korisnik' : 'Uredi korisnika'}
        </h2>

        <div className="space-y-3">
          <div>
            <label className="text-xs mb-1 block" style={{ color: 'var(--text-muted)' }}>Ime</label>
            <input value={name} onChange={e => setName(e.target.value)}
              className={inputCls} style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          </div>
          {isNew && (
            <div>
              <label className="text-xs mb-1 block" style={{ color: 'var(--text-muted)' }}>Email</label>
              <input value={email} onChange={e => setEmail(e.target.value)} type="email"
                className={inputCls} style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
            </div>
          )}
          <div>
            <label className="text-xs mb-1 block" style={{ color: 'var(--text-muted)' }}>
              {isNew ? 'Lozinka' : 'Nova lozinka (ostavite prazno da ne mijenjate)'}
            </label>
            <input value={password} onChange={e => setPassword(e.target.value)} type="password"
              className={inputCls} style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
          </div>
          <div>
            <label className="text-xs mb-1 block" style={{ color: 'var(--text-muted)' }}>Uloga</label>
            <select value={role} onChange={e => setRole(e.target.value)}
              className={inputCls} style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          {!isNew && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="rounded" />
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Aktivan</span>
            </label>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border transition-colors hover:bg-white/5"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            Odustani
          </button>
          <button onClick={handleSave}
            className="px-4 py-2 text-sm rounded-md font-medium transition-colors"
            style={{ background: 'var(--accent)', color: 'white' }}>
            Sačuvaj
          </button>
        </div>
      </div>
    </div>
  )
}

function ConfirmModal({ user, onClose, onConfirm }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)' }}>
      <div className="w-full max-w-sm rounded-xl border p-6" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Brisanje korisnika</h2>
        <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>
          Sigurno brisanje <strong>{user.name}</strong> ({user.email})?
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border hover:bg-white/5"
            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            Odustani
          </button>
          <button onClick={onConfirm}
            className="px-4 py-2 text-sm rounded-md font-medium bg-red-500/80 hover:bg-red-500 text-white">
            Obriši
          </button>
        </div>
      </div>
    </div>
  )
}

function SystemControl({ label, statusKey, statusUrl, pauseUrl, resumeUrl, description }) {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: [statusKey],
    queryFn: () => api.get(statusUrl).then(r => r.data),
    refetchInterval: 15_000,
  })

  const pauseMutation = useMutation({
    mutationFn: () => api.post(pauseUrl).then(r => r.data),
    onSuccess: () => qc.invalidateQueries([statusKey]),
  })
  const resumeMutation = useMutation({
    mutationFn: () => api.post(resumeUrl).then(r => r.data),
    onSuccess: () => qc.invalidateQueries([statusKey]),
  })

  const paused = data?.paused ?? false

  return (
    <div className="rounded-xl border p-4 flex items-center justify-between"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: paused ? '#ef4444' : '#22c55e' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            {label} — {paused ? 'Zaustavljen' : 'Aktivan'}
          </span>
        </div>
        {paused && (
          <p className="text-xs mt-0.5" style={{ color: '#f59e0b' }}>{description}</p>
        )}
      </div>
      <button
        onClick={() => paused ? resumeMutation.mutate() : pauseMutation.mutate()}
        disabled={pauseMutation.isPending || resumeMutation.isPending}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm border transition-colors hover:bg-white/[0.04] disabled:opacity-50"
        style={{ borderColor: 'var(--border)', color: paused ? '#22c55e' : '#ef4444' }}>
        {paused ? <><Play size={13} /> Nastavi</> : <><Pause size={13} /> Zaustavi</>}
      </button>
    </div>
  )
}


function CalibrationPanel() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['calibration-prompts'],
    queryFn: () => api.get('/admin/calibration/prompts').then(r => r.data.items),
  })
  const runMutation = useMutation({
    mutationFn: () => api.post('/admin/calibration/run'),
    onSuccess: () => setTimeout(() => qc.invalidateQueries(['calibration-prompts']), 1500),
  })
  const activateMutation = useMutation({
    mutationFn: (id) => api.post(`/admin/calibration/prompts/${id}/activate`),
    onSuccess: () => qc.invalidateQueries(['calibration-prompts']),
  })
  const prompts = data || []

  return (
    <section className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Kalibracija (RLHF)</h2>
        <button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}
          className="px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--accent)', color: 'white' }}>
          {runMutation.isPending ? 'Pokrećem…' : 'Pokreni kalibraciju'}
        </button>
      </div>
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        {prompts.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
            Nema kalibracionih verzija. Pokreni kalibraciju nakon što analitičari pošalju feedback.
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {prompts.map(p => (
              <div key={p.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {p.analysis_type} v{p.version}
                    </span>
                    {p.is_active
                      ? <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#22c55e33', color: '#22c55e' }}>aktivna</span>
                      : <button onClick={() => activateMutation.mutate(p.id)}
                          className="text-[10px] px-1.5 py-0.5 rounded border hover:bg-white/[0.04]" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                          aktiviraj
                        </button>}
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{p.feedback_count} feedback</span>
                  </div>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {p.created_at ? new Date(p.created_at).toLocaleString('sr-Latn', { hour12: false }) : ''}
                  </span>
                </div>
                <pre className="text-xs mt-1.5 whitespace-pre-wrap" style={{ color: 'var(--text-muted)', fontFamily: 'inherit' }}>{p.prompt_text}</pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function ReanalyzePanel() {
  const [form, setForm] = useState({ date_from: '', date_to: '', source_id: '' })
  const [msg, setMsg] = useState('')
  const run = useMutation({
    mutationFn: () => api.post('/admin/reanalyze', {
      date_from: form.date_from || null, date_to: form.date_to || null,
      source_id: form.source_id || null,
    }).then(r => r.data),
    onSuccess: (d) => setMsg(`Zakazano: ${d.article_count} članaka u re-analizu`),
  })
  const inputStyle = { background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }
  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Re-analiza članaka</h2>
      <div className="rounded-xl border p-4 flex flex-wrap items-end gap-3" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div>
          <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Od datuma</label>
          <input type="date" value={form.date_from} onChange={e => setForm(f => ({ ...f, date_from: e.target.value }))} className="px-2 py-1.5 rounded text-xs border" style={inputStyle} />
        </div>
        <div>
          <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Do datuma</label>
          <input type="date" value={form.date_to} onChange={e => setForm(f => ({ ...f, date_to: e.target.value }))} className="px-2 py-1.5 rounded text-xs border" style={inputStyle} />
        </div>
        <div>
          <label className="text-xs block mb-1" style={{ color: 'var(--text-muted)' }}>Izvor (opciono)</label>
          <input value={form.source_id} onChange={e => setForm(f => ({ ...f, source_id: e.target.value }))} placeholder="npr. informer" className="px-2 py-1.5 rounded text-xs border w-32" style={inputStyle} />
        </div>
        <button onClick={() => run.mutate()} disabled={run.isPending}
          className="px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50" style={{ background: 'var(--accent)', color: 'white' }}>
          {run.isPending ? 'Pokrećem…' : 'Re-analiziraj'}
        </button>
        {msg && <span className="text-xs" style={{ color: '#22c55e' }}>{msg}</span>}
      </div>
      <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
        Ponovo analizira već analizirane članke pod tekućim promptom (npr. nakon kalibracije ili novih framing/narativ definicija).
      </p>
    </section>
  )
}

function TriggerPanel() {
  const [msgs, setMsgs] = useState({})
  const trigger = async (task) => {
    setMsgs(m => ({ ...m, [task]: 'Pokrećem...' }))
    try {
      const r = await api.post('/admin/tasks/trigger', { task_name: task })
      setMsgs(m => ({ ...m, [task]: r.data?.message || 'Pokrenuto ✓' }))
    } catch (e) {
      setMsgs(m => ({ ...m, [task]: `Greška: ${e.response?.data?.detail || e.message}` }))
    }
    setTimeout(() => setMsgs(m => { const n = { ...m }; delete n[task]; return n }), 5000)
  }
  const TASKS = [
    { key: 'detect_anomalies', label: 'Pokreni detect_anomalies' },
    { key: 'detect_coordination', label: 'Pokreni detect_coordination' },
    { key: 'detect_copypaste', label: 'Pokreni detect_copypaste' },
    { key: 'generate_daily_summary', label: 'Generiši dnevni pregled (juče)' },
    { key: 'consolidate_narrative_proposals', label: 'Klasteriraj narativne predloge' },
    { key: 'generate_embeddings', label: 'Generiši embeddings' },
  ]
  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Ručno pokretanje taskova</h2>
      <div className="grid grid-cols-2 gap-3">
        {TASKS.map(({ key, label }) => (
          <div key={key} className="rounded-xl border p-4 flex items-center justify-between"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
            <div className="flex items-center gap-2">
              {msgs[key] && <span className="text-xs" style={{ color: msgs[key].startsWith('Gr') ? '#f87171' : '#22c55e' }}>{msgs[key]}</span>}
              <button onClick={() => trigger(key)}
                className="flex items-center gap-1 px-2.5 py-1 rounded text-xs border hover:bg-white/[0.04] transition-colors"
                style={{ borderColor: 'var(--border)', color: 'var(--accent)' }}>
                <Zap size={11} /> Pokreni
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function ResourcesPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-resources'],
    queryFn: () => api.get('/admin/system/resources').then(r => r.data),
    refetchInterval: 30_000,
  })

  const Bar = ({ pct, color }) => (
    <div className="w-full rounded-full h-2 mt-1" style={{ background: 'var(--bg-elevated)' }}>
      <div className="h-2 rounded-full transition-all" style={{ width: `${Math.min(100, pct || 0)}%`, background: color }} />
    </div>
  )

  if (isLoading) return <div className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>Učitavanje resursa...</div>
  if (!data) return <div className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>Endpoint /admin/system/resources nije dostupan</div>

  const resources = [
    { label: 'Disk (ukupno)', value: data.disk_used_gb != null ? `${data.disk_used_gb} / ${data.disk_total_gb} GB` : '—', pct: data.disk_pct, color: data.disk_pct > 85 ? '#ef4444' : '#6366f1' },
    { label: 'RAM', value: data.ram_used_gb != null ? `${data.ram_used_gb} / ${data.ram_total_gb} GB` : '—', pct: data.ram_pct, color: data.ram_pct > 85 ? '#ef4444' : '#3b82f6' },
    { label: 'CPU (trenutno)', value: data.cpu_pct != null ? `${data.cpu_pct}%` : '—', pct: data.cpu_pct, color: data.cpu_pct > 85 ? '#ef4444' : '#10b981' },
  ]

  return (
    <div className="grid grid-cols-3 gap-4">
      {resources.map(({ label, value, pct, color }) => (
        <div key={label} className="rounded-xl border p-4" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <HardDrive size={13} style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
          </div>
          <div className="text-lg font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>{value}</div>
          {pct != null && <Bar pct={pct} color={color} />}
          {pct != null && <div className="text-xs mt-0.5 text-right" style={{ color: 'var(--text-muted)' }}>{pct.toFixed(1)}%</div>}
        </div>
      ))}
    </div>
  )
}

const TABS = ['Administracija', 'Korisnici', 'Logovi', 'Resursi']

export default function Admin() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('Administracija')
  const [editUser, setEditUser] = useState(null)
  const [deleteUser, setDeleteUser] = useState(null)
  const [isNewUser, setIsNewUser] = useState(false)
  const [runsPage, setRunsPage] = useState(1)
  const [runsSource, setRunsSource] = useState('')
  const [batchesPage, setBatchesPage] = useState(1)
  const [expandedBatch, setExpandedBatch] = useState(null)
  const [expandedRun, setExpandedRun] = useState(null)
  const [errorsModal, setErrorsModal] = useState(null) // { batchDbId, batchId }

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then(r => r.data),
  })

  const batchesParams = new URLSearchParams({ page: batchesPage, per_page: 50 })
  const { data: batchesData } = useQuery({
    queryKey: ['admin-pipeline-batches', batchesPage],
    queryFn: () => api.get(`/admin/pipeline/batches?${batchesParams}`).then(r => r.data),
    keepPreviousData: true,
  })
  const batches = batchesData?.items || []
  const batchesTotal = batchesData?.total || 0
  const batchesPages = batchesData?.pages || 1

  const runsParams = new URLSearchParams({ page: runsPage, per_page: 50 })
  if (runsSource) runsParams.set('source_id', runsSource)

  const { data: runsData } = useQuery({
    queryKey: ['admin-scraper-runs', runsPage, runsSource],
    queryFn: () => api.get(`/admin/scraper/runs?${runsParams}`).then(r => r.data),
    keepPreviousData: true,
  })

  const { data: errorsData, isLoading: errorsLoading } = useQuery({
    queryKey: ['admin-batch-errors', errorsModal?.batchDbId],
    queryFn: () => api.get(`/admin/pipeline/batches/${errorsModal.batchDbId}/errors`).then(r => r.data),
    enabled: !!errorsModal,
  })
  const runs = runsData?.items || []
  const runsTotal = runsData?.total || 0
  const runsPages = runsData?.pages || 1

  const createMutation = useMutation({
    mutationFn: (data) => api.post('/admin/users', data),
    onSuccess: () => qc.invalidateQueries(['admin-users']),
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }) => api.put(`/admin/users/${id}`, data),
    onSuccess: () => qc.invalidateQueries(['admin-users']),
  })
  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/admin/users/${id}`),
    onSuccess: () => { qc.invalidateQueries(['admin-users']); setDeleteUser(null) },
  })

  const handleSaveEdit = async (data) => { await updateMutation.mutateAsync({ id: editUser.id, ...data }) }
  const handleSaveNew = async (data) => { await createMutation.mutateAsync(data) }

  const thCls = "px-4 py-2 text-left text-xs font-medium uppercase tracking-wide"

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Admin panel</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Upravljanje sistemom i monitoring</p>
        </div>
      </div>

      {/* Tab navigacija */}
      <div className="flex gap-1 mb-6 border-b" style={{ borderColor: 'var(--border)' }}>
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className="px-4 py-2 text-sm font-medium transition-colors rounded-t -mb-px border-b-2"
            style={{
              color: activeTab === tab ? 'var(--accent)' : 'var(--text-muted)',
              borderBottomColor: activeTab === tab ? 'var(--accent)' : 'transparent',
              background: 'transparent',
            }}>
            {tab}
          </button>
        ))}
      </div>

      {/* ---- TAB: Administracija ---- */}
      {activeTab === 'Administracija' && (
        <div>
          <section className="mb-8 space-y-3">
            <SystemControl label="AI Pipeline" statusKey="pipeline-status"
              statusUrl="/admin/pipeline/status" pauseUrl="/admin/pipeline/pause" resumeUrl="/admin/pipeline/resume"
              description="Novi batch-evi nece se pokrenuti dok se pipeline ne nastavi." />
            <SystemControl label="Scraper" statusKey="scraper-status"
              statusUrl="/admin/scraper/status" pauseUrl="/admin/scraper/pause" resumeUrl="/admin/scraper/resume"
              description="Zakazani scraper rundovi nece se pokrenuti dok se scraper ne nastavi." />
          </section>
          <TriggerPanel />
          <CalibrationPanel />
          <ReanalyzePanel />
        </div>
      )}

      {/* ---- TAB: Korisnici ---- */}
      {activeTab === 'Korisnici' && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Korisnici</h2>
            <button onClick={() => setIsNewUser(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
              style={{ background: 'var(--accent)', color: 'white' }}>
              <UserPlus size={13} /> Novi korisnik
            </button>
          </div>
          <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            {isLoading ? (
              <div className="py-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje...</div>
            ) : (
              <table className="w-full">
                <thead style={{ background: 'var(--bg-elevated)' }}>
                  <tr>{['Ime', 'Email', 'Uloga', 'Status', 'Zadnja prijava', ''].map(h => (
                    <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <UserRow key={u.id} user={u}
                      currentUserId={users.find(x => x.role === 'admin')?.id}
                      onEdit={setEditUser} onDelete={setDeleteUser} />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* ---- TAB: Logovi ---- */}
      {activeTab === 'Logovi' && (
        <div>
          {/* Pipeline logovi */}
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Pipeline logovi (AI analiza)</h2>
                {batchesTotal > 0 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{batchesTotal} ukupno</span>}
              </div>
            </div>
            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead style={{ background: 'var(--bg-elevated)' }}>
                    <tr>{['Batch ID', 'Tip', 'Datum', 'Status', 'Ukupno', 'Sačuvano', 'Greške', 'Pokrenuto', 'Trajanje', 'Poruka'].map(h => (
                      <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {batches.length === 0 ? (
                      <tr><td colSpan={10} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                        Nema logova — batch-evi se upisuju od sledećeg noćnog runda.
                      </td></tr>
                    ) : batches.map(b => {
                      const durationMs = b.submitted_at && b.finished_at
                        ? new Date(b.finished_at) - new Date(b.submitted_at) : null
                      const isExp = expandedBatch === b.id
                      return [
                        <tr key={b.id} className="border-b cursor-pointer hover:bg-white/[0.02]"
                          style={{ borderColor: 'var(--border)' }}
                          onClick={() => setExpandedBatch(isExp ? null : b.id)}>
                          <td className="px-4 py-2.5 font-mono text-xs max-w-[140px] truncate" style={{ color: 'var(--text-muted)' }}
                            title={b.batch_id}>{b.batch_id?.slice(0, 16)}…</td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>{b.batch_type}</td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-secondary)' }}>{b.batch_date || '—'}</td>
                          <td className="px-4 py-2.5">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              b.status === 'completed' ? 'bg-green-500/20 text-green-300' :
                              b.status === 'failed'    ? 'bg-red-500/20 text-red-300' :
                              b.status === 'submitted' ? 'bg-blue-500/20 text-blue-300' :
                                                         'bg-yellow-500/20 text-yellow-300'
                            }`}>{b.status}</span>
                          </td>
                          <td className="px-4 py-2.5 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{b.article_count ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs tabular-nums text-green-400">{b.articles_saved ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs tabular-nums">
                            {b.articles_failed > 0 ? (
                              <button
                                onClick={e => { e.stopPropagation(); setErrorsModal({ batchDbId: b.id, batchId: b.batch_id }) }}
                                className="underline decoration-dotted hover:opacity-80 tabular-nums"
                                style={{ color: '#f87171' }}
                                title="Klikni da vidiš detalje grešaka"
                              >{b.articles_failed}</button>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>{b.articles_failed ?? '—'}</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                            {b.submitted_at ? new Date(b.submitted_at).toLocaleString('sr-Latn', { hour12: false }) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                            {durationMs != null ? `${Math.round(durationMs / 60000)}min` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-xs max-w-[160px] truncate" style={{ color: '#f87171' }}
                            title={b.error_message}>{b.error_message?.slice(0, 40) || ''}</td>
                        </tr>,
                        isExp && b.error_message && (
                          <tr key={`${b.id}-exp`} style={{ background: 'var(--bg-elevated)' }}>
                            <td colSpan={10} className="px-4 py-2">
                              <pre className="text-xs whitespace-pre-wrap break-all" style={{ color: '#f87171' }}>{b.error_message}</pre>
                            </td>
                          </tr>
                        ),
                      ]
                    })}
                  </tbody>
                </table>
              </div>
              {batchesPages > 1 && (
                <div className="flex items-center justify-between px-4 py-2.5 border-t text-xs"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                  <span>Stranica {batchesPage} od {batchesPages}</span>
                  <div className="flex gap-1">
                    <button onClick={() => setBatchesPage(p => Math.max(1, p - 1))} disabled={batchesPage === 1}
                      className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronLeft size={14} /></button>
                    <button onClick={() => setBatchesPage(p => Math.min(batchesPages, p + 1))} disabled={batchesPage >= batchesPages}
                      className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronRight size={14} /></button>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Scraper logovi */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Scraper logovi</h2>
                {runsTotal > 0 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{runsTotal} ukupno</span>}
              </div>
              <input value={runsSource} onChange={e => { setRunsSource(e.target.value); setRunsPage(1) }}
                placeholder="Filtriraj po izvoru…"
                className="px-3 py-1.5 rounded text-xs border outline-none w-40"
                style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
            </div>
            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead style={{ background: 'var(--bg-elevated)' }}>
                    <tr>{['Izvor', 'Status', 'Pronađeno', 'Novi', 'Preskočeni', 'Ažurirani', 'Trajanje', 'Pokrenuto', 'Tip greške'].map(h => (
                      <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {runs.length === 0 ? (
                      <tr><td colSpan={9} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
                        Nema logova — scraper počinje da upisuje od sledećeg runda.
                      </td></tr>
                    ) : runs.map(r => {
                      const isExp = expandedRun === r.id
                      return [
                        <tr key={r.id} className="border-b cursor-pointer hover:bg-white/[0.02]"
                          style={{ borderColor: 'var(--border)' }}
                          onClick={() => setExpandedRun(isExp ? null : r.id)}>
                          <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{r.source_id}</td>
                          <td className="px-4 py-2.5">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              r.status === 'success' ? 'bg-green-500/20 text-green-300' :
                              r.status === 'error'   ? 'bg-red-500/20 text-red-300' :
                              r.status === 'running' ? 'bg-blue-500/20 text-blue-300' :
                                                      'bg-yellow-500/20 text-yellow-300'
                            }`}>{r.status}</span>
                          </td>
                          <td className="px-4 py-2.5 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{r.articles_found ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs tabular-nums text-green-400">{r.articles_new ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs tabular-nums" style={{ color: 'var(--text-muted)' }}>{r.articles_skipped ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs tabular-nums" style={{ color: 'var(--text-secondary)' }}>{r.articles_updated ?? '—'}</td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                            {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                            {r.started_at ? new Date(r.started_at).toLocaleString('sr-Latn', { hour12: false }) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-xs max-w-[160px] truncate" style={{ color: '#f87171' }}
                            title={r.error_message}>{r.error_type || ''}</td>
                        </tr>,
                        isExp && (r.error_message || r.error_type) && (
                          <tr key={`${r.id}-exp`} style={{ background: 'var(--bg-elevated)' }}>
                            <td colSpan={9} className="px-4 py-2">
                              <pre className="text-xs whitespace-pre-wrap break-all" style={{ color: '#f87171' }}>
                                {r.error_type ? `[${r.error_type}] ` : ''}{r.error_message || ''}
                              </pre>
                            </td>
                          </tr>
                        ),
                      ]
                    })}
                  </tbody>
                </table>
              </div>
              {runsPages > 1 && (
                <div className="flex items-center justify-between px-4 py-2.5 border-t text-xs"
                  style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                  <span>Stranica {runsPage} od {runsPages}</span>
                  <div className="flex gap-1">
                    <button onClick={() => setRunsPage(p => Math.max(1, p - 1))} disabled={runsPage === 1}
                      className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronLeft size={14} /></button>
                    <button onClick={() => setRunsPage(p => Math.min(runsPages, p + 1))} disabled={runsPage >= runsPages}
                      className="p-1 rounded disabled:opacity-30 hover:bg-white/[0.04]"><ChevronRight size={14} /></button>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* ---- TAB: Resursi ---- */}
      {activeTab === 'Resursi' && (
        <div>
          <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Sistemski resursi</h2>
          <ResourcesPanel />
        </div>
      )}

      {/* Modali */}
      {(editUser || isNewUser) && (
        <EditModal user={isNewUser ? null : editUser}
          onClose={() => { setEditUser(null); setIsNewUser(false) }}
          onSave={isNewUser ? handleSaveNew : handleSaveEdit} />
      )}
      {deleteUser && (
        <ConfirmModal user={deleteUser}
          onClose={() => setDeleteUser(null)}
          onConfirm={() => deleteMutation.mutate(deleteUser.id)} />
      )}

      {/* Modal: greške batcha */}
      {errorsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)' }}
          onClick={() => setErrorsModal(null)}>
          <div className="rounded-xl border w-full max-w-3xl max-h-[80vh] flex flex-col"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3.5 border-b" style={{ borderColor: 'var(--border)' }}>
              <div>
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Greške u batchu</h3>
                <p className="text-xs mt-0.5 font-mono" style={{ color: 'var(--text-muted)' }}>{errorsModal.batchId}</p>
              </div>
              <button onClick={() => setErrorsModal(null)} className="p-1 rounded hover:bg-white/[0.06]">
                <X size={16} style={{ color: 'var(--text-muted)' }} />
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              {errorsLoading ? (
                <p className="px-5 py-8 text-sm text-center" style={{ color: 'var(--text-muted)' }}>Učitavanje…</p>
              ) : !errorsData?.errors?.length ? (
                <p className="px-5 py-8 text-sm text-center" style={{ color: 'var(--text-muted)' }}>
                  Nema grešaka za ovaj batch u bazi. (Greške se upisuju od sledećeg batch-a.)
                </p>
              ) : (
                <table className="w-full text-xs">
                  <thead style={{ background: 'var(--bg-elevated)' }}>
                    <tr>
                      {['Članak', 'Faza', 'Tip greške', 'Poruka', 'Vreme'].map(h => (
                        <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {errorsData.errors.map(e => (
                      <tr key={e.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                        <td className="px-4 py-2 tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                          {e.article_id ? (
                            <a href={`/articles/${e.article_id}`} target="_blank" rel="noreferrer"
                              className="underline decoration-dotted hover:opacity-80"
                              style={{ color: 'var(--accent)' }}>#{e.article_id}</a>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-2" style={{ color: 'var(--text-muted)' }}>{e.stage || '—'}</td>
                        <td className="px-4 py-2 font-mono" style={{ color: '#f87171' }}>{e.error_type || '—'}</td>
                        <td className="px-4 py-2 max-w-xs" style={{ color: 'var(--text-secondary)' }}>
                          <span title={e.error_message} className="block truncate">{e.error_message || '—'}</span>
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                          {e.created_at ? new Date(e.created_at).toLocaleTimeString('sr-Latn', { hour12: false }) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
