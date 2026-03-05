import { ref } from 'vue'
import { defineStore } from 'pinia'

export const ACTIVE_GROUP_STORAGE_KEY = 'asPanel_activeGroupIds'

export const useActiveGroupStore = defineStore('activeGroup', () => {
  const activeGroupIds = ref<number[]>([])

  const getActiveGroupId = (): number | null => activeGroupIds.value[0] ?? null

  const loadSavedGroupIds = (): number[] => {
    try {
      const saved = localStorage.getItem(ACTIVE_GROUP_STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.every((id: unknown) => typeof id === 'number')) return parsed
      }
    } catch { /* ignore */ }
    return []
  }

  const saveGroupIds = (ids: number[]) => {
    try { localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, JSON.stringify(ids)) } catch { /* ignore */ }
  }

  const clearGroupIds = () => {
    try { localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY) } catch { /* ignore */ }
    activeGroupIds.value = []
  }

  return { activeGroupIds, getActiveGroupId, loadSavedGroupIds, saveGroupIds, clearGroupIds }
})
