import { ref } from 'vue'
import { defineStore } from 'pinia'

/** Must match the CSS sidebar collapse transition duration. */
export const ASIDE_COLLAPSE_MS = 380

export const useUiStore = defineStore('ui', () => {
  const asideCollapsed = ref(false)
  const asideCollapsing = ref(false)

  const toggleAside = () => {
    asideCollapsing.value = true
    requestAnimationFrame(() => {
      asideCollapsed.value = !asideCollapsed.value
      setTimeout(() => {
        asideCollapsing.value = false
      }, ASIDE_COLLAPSE_MS)
    })
  }

  const setAsideCollapsed = (value: boolean) => {
    asideCollapsed.value = !!value
  }

  const setAsideCollapsing = (value: boolean) => {
    asideCollapsing.value = !!value
  }

  return { asideCollapsed, asideCollapsing, toggleAside, setAsideCollapsed, setAsideCollapsing }
})
