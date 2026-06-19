import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async e => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch {
      setError('Pogrešan email ili lozinka')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-base)' }}>
      <div className="w-80">
        <div className="text-center mb-8">
          <div className="text-xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>MediaScope</div>
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>SHARE Fondacija — Istraživački tim</div>
        </div>
        <form onSubmit={handleSubmit} className="rounded-xl p-6 space-y-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--text-secondary)' }}>Email</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border focus:border-white/30 transition-colors"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--text-secondary)' }}>Lozinka</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border focus:border-white/30 transition-colors"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            />
          </div>
          {error && <div className="text-xs text-red-400">{error}</div>}
          <button
            type="submit" disabled={loading}
            className="w-full py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            style={{ background: 'rgba(255,255,255,0.1)', color: 'var(--text-primary)' }}
          >
            {loading ? 'Prijavljivanje...' : 'Prijavi se'}
          </button>
        </form>
      </div>
    </div>
  )
}
