import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Newspaper, Radio, TrendingUp, LogOut, Activity, Settings, Bell, Layers, Hash } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../store/auth'
import GlobalFilters from './GlobalFilters'
import api from '../lib/api'

const nav = [
  { to: '/',           icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/articles',   icon: Newspaper,       label: 'Članci' },
  { to: '/sources',    icon: Radio,           label: 'Izvori' },
  { to: '/narratives', icon: TrendingUp,      label: 'Narativi' },
  { to: '/topics',     icon: Hash,            label: 'Teme' },
  { to: '/framing',    icon: Layers,          label: 'Framing' },
]

function PipelineStatus() {
  const { data } = useQuery({
    queryKey: ['pipeline-count'],
    queryFn: () => Promise.all([
      api.get('/articles?per_page=1').then(r => r.data.total),
      api.get('/articles?per_page=1&has_analysis=true').then(r => r.data.total),
    ]).then(([total, analyzed]) => ({ total, analyzed })),
    refetchInterval: 15_000,
  })

  if (!data) return null
  const pct = data.total ? Math.round(data.analyzed / data.total * 100) : 0
  const done = pct === 100

  return (
    <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <Activity size={11} style={{ color: done ? '#22c55e' : '#f59e0b' }} />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {done ? 'Pipeline završen' : 'Pipeline u toku'}
          </span>
        </div>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{pct}%</span>
      </div>
      <div className="h-1 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
        <div className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: done ? '#22c55e' : '#f59e0b' }} />
      </div>
      <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
        {data.analyzed.toLocaleString()} / {data.total.toLocaleString()}
      </div>
    </div>
  )
}

function AlertsNavItem() {
  const { data } = useQuery({
    queryKey: ['alerts-unread'],
    queryFn: () => api.get('/alerts?limit=1').then(r => r.data.unread_count || 0),
    refetchInterval: 60_000,
  })
  const unread = data || 0

  return (
    <NavLink to="/alerts"
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
          isActive ? 'bg-white/10 text-white' : 'text-[var(--text-secondary)] hover:text-white hover:bg-white/5'
        }`}>
      <div className="relative">
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 text-[10px] leading-none px-1 py-0.5 rounded-full font-medium"
            style={{ background: '#ef4444', color: '#fff', minWidth: 14, textAlign: 'center' }}>
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </div>
      Upozorenja
    </NavLink>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-base)' }}>
      <aside className="w-56 flex flex-col border-r shrink-0" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>MediaScope</div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>SHARE Fondacija</div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'text-[var(--text-secondary)] hover:text-white hover:bg-white/5'
                }`}>
              <Icon size={15} />{label}
            </NavLink>
          ))}
          <AlertsNavItem />
          {user?.role === 'admin' && (
            <NavLink to="/admin"
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? 'bg-white/10 text-white' : 'text-[var(--text-secondary)] hover:text-white hover:bg-white/5'
                }`}>
              <Settings size={15} />Admin
            </NavLink>
          )}
        </nav>

        <PipelineStatus />

        <div className="px-4 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="text-xs mb-1 truncate" style={{ color: 'var(--text-muted)' }}>{user?.email}</div>
          <button onClick={handleLogout}
            className="flex items-center gap-2 text-xs hover:text-white transition-colors"
            style={{ color: 'var(--text-secondary)' }}>
            <LogOut size={13} /> Odjavi se
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-hidden flex flex-col">
        <GlobalFilters />
        <div className="flex-1 overflow-y-auto"><Outlet /></div>
      </main>
    </div>
  )
}
