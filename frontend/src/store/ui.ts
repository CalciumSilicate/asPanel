import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', () => {
  const asideCollapsed = ref(false)
  const asideCollapsing = ref(false)

  const toggleAside = () => {
    if (!asideCollapsed.value) {
      asideCollapsing.value = true
      requestAnimationFrame(() => {
        asideCollapsed.value = true
        setTimeout(() => {
          asideCollapsing.value = false
        }, 380)
      })
    } else {
      asideCollapsed.value = false
    }
  }

  const setAsideCollapsed = (value: boolean) => {
    asideCollapsed.value = !!value
  }

  const setAsideCollapsing = (value: boolean) => {
    asideCollapsing.value = !!value
  }

  return { asideCollapsed, asideCollapsing, toggleAside, setAsideCollapsed, setAsideCollapsing }
})
