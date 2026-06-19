import { create } from 'zustand'

export const useFilters = create((set) => ({
  dateFrom: '',
  dateTo: '',
  selectedSources: [],

  setDateFrom: (v) => set({ dateFrom: v }),
  setDateTo: (v) => set({ dateTo: v }),
  toggleSource: (id) =>
    set((s) => ({
      selectedSources: s.selectedSources.includes(id)
        ? s.selectedSources.filter((x) => x !== id)
        : [...s.selectedSources, id],
    })),
  reset: () => set({ dateFrom: '', dateTo: '', selectedSources: [] }),
}))

export function toParams({ dateFrom, dateTo, selectedSources }) {
  const p = {}
  if (dateFrom) p.date_from = dateFrom
  if (dateTo) p.date_to = dateTo
  if (selectedSources?.length) p.source_ids = selectedSources.join(',')
  return p
}
