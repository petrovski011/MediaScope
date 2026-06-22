import { create } from 'zustand'

let _nextId = 1

export const useToastStore = create(set => ({
  toasts: [],
  push: (message, type = 'error') => {
    const id = _nextId++
    set(s => ({ toasts: [...s.toasts, { id, message, type }] }))
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), 5000)
  },
  dismiss: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
}))
