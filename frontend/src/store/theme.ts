import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'theme'

export const isDark = ref(false)

function applyToDom(dark: boolean) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', dark)
}

export function setTheme(mode: ThemeMode) {
  const dark = mode === 'dark'
  isDark.value = dark
  applyToDom(dark)
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // ignore
  }
}

export function initTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
    if (saved === 'light' || saved === 'dark') {
      setTheme(saved)
      return
    }
  } catch {
    // ignore
  }

  setTheme('light')
}

export function toggleTheme() {
  setTheme(isDark.value ? 'light' : 'dark')
}

