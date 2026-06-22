import { X } from 'lucide-react'
import { useToastStore } from '../store/toast'

export default function ToastContainer() {
  const { toasts, dismiss } = useToastStore()
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map(t => (
        <div key={t.id}
          className="flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg pointer-events-auto"
          style={{
            background: t.type === 'error' ? 'rgba(239,68,68,0.12)' : 'var(--bg-elevated)',
            borderColor: t.type === 'error' ? 'rgba(239,68,68,0.35)' : 'var(--border)',
            color: t.type === 'error' ? '#f87171' : 'var(--text-primary)',
          }}>
          <span className="flex-1 text-xs leading-relaxed">{t.message}</span>
          <button onClick={() => dismiss(t.id)} className="shrink-0 mt-0.5 hover:opacity-70">
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}
