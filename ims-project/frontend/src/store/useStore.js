import { create } from 'zustand'
import { fetchWorkItems, fetchDashboardStats, fetchHealth, fetchQueueStats } from '../services/api'

export const useStore = create((set, get) => ({
  // Work items
  workItems: [],
  workItemsLoading: false,
  workItemsError: null,

  // Stats
  stats: null,
  statsLoading: false,

  // Health
  health: null,

  // Queue stats (from WS or polling)
  queueStats: null,

  // Selected work item
  selectedWorkItemId: null,

  // Filters
  statusFilter: null,
  priorityFilter: null,

  setFilter: (type, val) => {
    set(type === 'status'
      ? { statusFilter: val }
      : { priorityFilter: val }
    )
    get().loadWorkItems()
  },

  loadWorkItems: async () => {
    const { statusFilter, priorityFilter } = get()
    set({ workItemsLoading: true, workItemsError: null })
    try {
      const data = await fetchWorkItems({
        ...(statusFilter && { status: statusFilter }),
        ...(priorityFilter && { priority: priorityFilter }),
      })
      set({ workItems: data.work_items, workItemsLoading: false })
    } catch (e) {
      set({ workItemsError: e.message, workItemsLoading: false })
    }
  },

  loadStats: async () => {
    set({ statsLoading: true })
    try {
      const data = await fetchDashboardStats()
      set({ stats: data, statsLoading: false })
    } catch {
      set({ statsLoading: false })
    }
  },

  loadHealth: async () => {
    try {
      const data = await fetchHealth()
      set({ health: data })
    } catch {
      set({ health: { status: 'unreachable' } })
    }
  },

  loadQueueStats: async () => {
    try {
      const data = await fetchQueueStats()
      set({ queueStats: data })
    } catch {}
  },

  refreshAll: async () => {
    await Promise.all([get().loadWorkItems(), get().loadStats()])
  },

  selectWorkItem: (id) => set({ selectedWorkItemId: id }),
}))
