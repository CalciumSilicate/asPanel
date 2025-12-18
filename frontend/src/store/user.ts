import { computed, reactive, ref } from 'vue'
import apiClient from '@/api'

export type UserRole = 'GUEST' | 'USER' | 'HELPER' | 'ADMIN' | 'OWNER'

export interface UserState {
  id: number | null
  username: string
  email: string
  avatar_url: string
  role: UserRole
}

export const user = reactive<UserState>({
  id: null,
  username: '',
  email: '',
  avatar_url: '',
  role: 'GUEST',
})

const avatarVersion = ref(0)

export const fullAvatarUrl = computed(() => {
  if (!user.avatar_url) return undefined
  const path = user.avatar_url.startsWith('/') ? user.avatar_url : `/${user.avatar_url}`
  return `${path}?v=${avatarVersion.value}`
})

const ROLE_LEVELS: Record<UserRole, number> = {
  GUEST: 0,
  USER: 1,
  HELPER: 2,
  ADMIN: 3,
  OWNER: 4,
}

export const roleLevel = computed(() => ROLE_LEVELS[user.role] ?? 0)

export const hasRole = (required: UserRole) => {
  const target = ROLE_LEVELS[required] ?? 0
  return roleLevel.value >= target
}

export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me')
    Object.assign(user, response.data)
  } catch (error) {
    console.error('Failed to fetch user:', error)
    clearUser()
  }
}

export const refreshAvatar = () => {
  avatarVersion.value++
}

export const clearUser = () => {
  user.id = null
  user.username = ''
  user.email = ''
  user.avatar_url = ''
  user.role = 'GUEST'
  avatarVersion.value = 0
}

