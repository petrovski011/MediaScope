import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Pencil, Trash2, Check, X, ShieldCheck, Eye } from 'lucide-react'
import api from '../lib/api'

const ROLES = ['admin', 'analyst', 'viewer']

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

export default function Admin() {
  const qc = useQueryClient()
  const [editUser, setEditUser] = useState(null)
  const [deleteUser, setDeleteUser] = useState(null)
  const [isNewUser, setIsNewUser] = useState(false)

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => api.get('/admin/users').then(r => r.data),
  })

  const { data: runs = [] } = useQuery({
    queryKey: ['admin-scraper-runs'],
    queryFn: () => api.get('/admin/scraper/runs?limit=20').then(r => r.data.items),
  })

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

  const handleSaveEdit = async (data) => {
    await updateMutation.mutateAsync({ id: editUser.id, ...data })
  }

  const handleSaveNew = async (data) => {
    await createMutation.mutateAsync(data)
  }

  const thCls = "px-4 py-2 text-left text-xs font-medium uppercase tracking-wide"

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Admin panel</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Upravljanje korisnicima i monitoring</p>
        </div>
      </div>

      {/* Korisnici */}
      <section className="mb-8">
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
                <tr>
                  {['Ime', 'Email', 'Uloga', 'Status', 'Zadnja prijava', ''].map(h => (
                    <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <UserRow key={u.id} user={u}
                    currentUserId={users.find(x => x.role === 'admin')?.id}
                    onEdit={setEditUser}
                    onDelete={setDeleteUser}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Scraper logovi */}
      <section>
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Scraper logovi (zadnjih 20)</h2>
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <table className="w-full text-sm">
            <thead style={{ background: 'var(--bg-elevated)' }}>
              <tr>
                {['Izvor', 'Status', 'Novi', 'Ažurirani', 'Trajanje', 'Pokrenuto'].map(h => (
                  <th key={h} className={thCls} style={{ color: 'var(--text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Nema logova</td></tr>
              ) : runs.map(r => (
                <tr key={r.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{r.source_id}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      r.status === 'success' ? 'bg-green-500/20 text-green-300' :
                      r.status === 'error'   ? 'bg-red-500/20 text-red-300' :
                                              'bg-yellow-500/20 text-yellow-300'
                    }`}>{r.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>{r.articles_new ?? '—'}</td>
                  <td className="px-4 py-2.5 text-sm" style={{ color: 'var(--text-secondary)' }}>{r.articles_updated ?? '—'}</td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {r.started_at ? new Date(r.started_at).toLocaleString('sr-Latn') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Modali */}
      {(editUser || isNewUser) && (
        <EditModal
          user={isNewUser ? null : editUser}
          onClose={() => { setEditUser(null); setIsNewUser(false) }}
          onSave={isNewUser ? handleSaveNew : handleSaveEdit}
        />
      )}
      {deleteUser && (
        <ConfirmModal
          user={deleteUser}
          onClose={() => setDeleteUser(null)}
          onConfirm={() => deleteMutation.mutate(deleteUser.id)}
        />
      )}
    </div>
  )
}
