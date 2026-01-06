import { computed, reactive, ref } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'

export type UserRole = 'GUEST' | 'USER' | 'HELPER' | 'ADMIN' | 'OWNER'

export interface GroupPermission {
  group_id: number
  group_name: string
  role: UserRole
}

export interface UserState {
  id: number | null
  username: string
  email: string
  avatar_url: string
  role: UserRole
  group_permissions: GroupPermission[]
}

export const user = reactive<UserState>({
  id: null,
  username: '',
  email: '',
  avatar_url: '',
  role: 'GUEST',
  group_permissions: [],
})

export const activeGroupIds = ref<number[]>([])

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

export const currentRole = computed(() => {
  // OWNER always has full access
  if (user.role === 'OWNER') return 'OWNER'
  
  // If no group selected, fall back to global role or GUEST
  if (activeGroupIds.value.length === 0) return 'GUEST'

  // Find max role among selected groups
  let maxLevel = -1
  let maxRole: UserRole = 'GUEST'

  for (const gid of activeGroupIds.value) {
    const perm = user.group_permissions.find(p => p.group_id === gid)
    if (perm) {
      const level = ROLE_LEVELS[perm.role] ?? 0
      if (level > maxLevel) {
        maxLevel = level
        maxRole = perm.role
      }
    }
  }
  return maxRole
})

export const roleLevel = computed(() => ROLE_LEVELS[currentRole.value] ?? 0)

export const hasRole = (required: UserRole) => {
  const target = ROLE_LEVELS[required] ?? 0
  return roleLevel.value >= target
}

export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me')
    Object.assign(user, response.data)
    
    // Auto-select first group if none selected and not OWNER
    if (user.role !== 'OWNER' && activeGroupIds.value.length === 0 && user.group_permissions.length > 0) {
      // Default to selecting the first one (or all? usually single context is clearer, let's pick first)
      activeGroupIds.value = [user.group_permissions[0].group_id]
    }
  } catch (error) {
    if (isRequestCanceled(error)) return
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
  user.group_permissions = []
  activeGroupIds.value = []
  avatarVersion.value = 0
}
