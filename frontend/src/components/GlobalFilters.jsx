import { useState, useRef, useEffect } from 'react'
import { Filter, X, Check, ChevronDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useFilters } from '../store/filters'
import api from '../lib/api'

function today() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function SourceDropdown({ sources, selectedSources, onToggle }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const label =
    selectedSources.length === 0
      ? 'Svi izvori'
      : selectedSources.length === 1
      ? (sources?.find((s) => s.source_id === selectedSources[0])?.name ?? selectedSources[0])
      : `${selectedSources.length} izvora`

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-colors"
        style={{
          background: 'var(--bg-base)',
          borderColor: selectedSources.length ? '#3b82f6' : 'var(--border)',
          color: selectedSources.length ? '#93c5fd' : 'var(--text-secondary)',
        }}
      >
        {label}
        <ChevronDown size={11} style={{ opacity: 0.6 }} />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-50 rounded-xl border shadow-2xl overflow-hidden"
          style={{
            background: 'var(--bg-elevated)',
            borderColor: 'var(--border)',
            minWidth: 200,
            maxHeight: 320,
            overflowY: 'auto',
          }}
        >
          {/* Brza akcija */}
          {selectedSources.length > 0 && (
            <div
              className="px-3 py-2 border-b"
              style={{ borderColor: 'var(--border)' }}
            >
              <button
                onClick={() => {
                  sources?.forEach((s) => {
                    if (selectedSources.includes(s.source_id))
                      onToggle(s.source_id)
                  })
                }}
                className="text-xs hover:text-white transition-colors"
                style={{ color: 'var(--text-muted)' }}
              >
                Poništi selekciju
              </button>
            </div>
          )}
          <div className="p-1.5">
            {sources?.map((s) => {
              const selected = selectedSources.includes(s.source_id)
              return (
                <button
                  key={s.source_id}
                  onClick={() => onToggle(s.source_id)}
                  className="flex items-center gap-2.5 w-full px-2.5 py-1.5 rounded-lg text-left hover:bg-white/5 transition-colors"
                  style={{ color: selected ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                >
                  <span
                    className="w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors"
                    style={{
                      borderColor: selected ? '#3b82f6' : 'var(--border)',
                      background: selected ? '#3b82f6' : 'transparent',
                    }}
                  >
                    {selected && <Check size={9} style={{ color: 'white' }} />}
                  </span>
                  <span className="text-xs">{s.name}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default function GlobalFilters() {
  const { dateFrom, dateTo, selectedSources, setDateFrom, setDateTo, toggleSource, reset } =
    useFilters()

  const { data: sources } = useQuery({
    queryKey: ['sources-list'],
    queryFn: () => api.get('/sources').then((r) => r.data.items),
    staleTime: 5 * 60 * 1000,
  })

  const activeCount =
    (dateFrom ? 1 : 0) + (dateTo ? 1 : 0) + (selectedSources.length ? 1 : 0)

  const setPreset = (n) => {
    setDateFrom(daysAgo(n))
    setDateTo(today())
  }

  return (
    <div
      className="flex items-center gap-3 px-6 py-2 border-b flex-wrap shrink-0"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {/* Label */}
      <div
        className="flex items-center gap-1.5 text-xs shrink-0"
        style={{ color: 'var(--text-muted)' }}
      >
        <Filter size={11} />
        <span>Filter</span>
        {activeCount > 0 && (
          <span
            className="px-1.5 py-0.5 rounded-full text-xs leading-none"
            style={{ background: '#3b82f6', color: 'white', fontSize: 10 }}
          >
            {activeCount}
          </span>
        )}
      </div>

      {/* Presets */}
      <div className="flex gap-1">
        {[7, 30, 90].map((n) => {
          const active = dateFrom === daysAgo(n) && dateTo === today()
          return (
            <button
              key={n}
              onClick={() => (active ? (setDateFrom(''), setDateTo('')) : setPreset(n))}
              className="px-2 py-1 rounded text-xs border transition-colors"
              style={{
                borderColor: active ? '#3b82f6' : 'var(--border)',
                color: active ? '#93c5fd' : 'var(--text-muted)',
                background: active ? 'rgba(59,130,246,0.1)' : 'transparent',
              }}
            >
              {n}d
            </button>
          )
        })}
      </div>

      <div className="w-px h-4 shrink-0" style={{ background: 'var(--border)' }} />

      {/* Date range */}
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => setDateFrom(e.target.value)}
        className="px-2 py-1.5 rounded-lg text-xs border outline-none"
        style={{
          background: 'var(--bg-base)',
          borderColor: dateFrom ? '#3b82f6' : 'var(--border)',
          color: 'var(--text-secondary)',
          colorScheme: 'dark',
        }}
      />
      <span className="text-xs shrink-0" style={{ color: 'var(--text-muted)' }}>
        —
      </span>
      <input
        type="date"
        value={dateTo}
        onChange={(e) => setDateTo(e.target.value)}
        className="px-2 py-1.5 rounded-lg text-xs border outline-none"
        style={{
          background: 'var(--bg-base)',
          borderColor: dateTo ? '#3b82f6' : 'var(--border)',
          color: 'var(--text-secondary)',
          colorScheme: 'dark',
        }}
      />

      <div className="w-px h-4 shrink-0" style={{ background: 'var(--border)' }} />

      {/* Sources */}
      <SourceDropdown
        sources={sources}
        selectedSources={selectedSources}
        onToggle={toggleSource}
      />

      {/* Reset */}
      {activeCount > 0 && (
        <button
          onClick={reset}
          className="flex items-center gap-1 text-xs hover:text-white transition-colors ml-1"
          style={{ color: 'var(--text-muted)' }}
        >
          <X size={11} />
          Resetuj
        </button>
      )}
    </div>
  )
}
