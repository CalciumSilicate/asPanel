import { ref } from 'vue'

// 全局的侧边折叠状态（与 MainLayout 侧边栏同步）
export const asideCollapsed = ref(false)
export const asideCollapsing = ref(false)

export const toggleAside = () => {
  if (!asideCollapsed.value) {
    // 展开 -> 折叠：先标记 collapsing，再在下一帧收起，并在动画后清理
    asideCollapsing.value = true
    requestAnimationFrame(() => {
      asideCollapsed.value = true
      setTimeout(() => { asideCollapsing.value = false }, 380)
    })
  } else {
    // 折叠 -> 展开
    asideCollapsed.value = false
  }
}

export const setAsideCollapsed = (v) => { asideCollapsed.value = !!v }
export const setAsideCollapsing = (v) => { asideCollapsing.value = !!v }
