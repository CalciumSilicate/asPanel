import { ref } from 'vue'

export const asideCollapsed = ref(false)
export const asideCollapsing = ref(false)

export const toggleAside = () => {
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

export const setAsideCollapsed = (value: boolean) => {
  asideCollapsed.value = !!value
}

export const setAsideCollapsing = (value: boolean) => {
  asideCollapsing.value = !!value
}

