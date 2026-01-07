import { computed, reactive, ref } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'

// 组权限等级（新版本）
export type GroupRole = 'USER' | 'HELPER' | 'ADMIN'

export interface GroupPermission {
  group_id: number
  group_name: string
  role: GroupRole
}

export interface UserState {
  id: number | null
  username: string
  email: string
  avatar_url: string
  // 新权限模型
  is_owner: boolean
  is_admin: boolean
  group_permissions: GroupPermission[]
}

export const user = reactive<UserState>({
  id: null,
  username: '',
  email: '',
  avatar_url: '',
  is_owner: false,
  is_admin: false,
  group_permissions: [],
})

export const activeGroupIds = ref<number[]>([])

const avatarVersion = ref(0)

export const fullAvatarUrl = computed(() => {
  if (!user.avatar_url) return undefined
  const path = user.avatar_url.startsWith('/') ? user.avatar_url : `/${user.avatar_url}`
  return `${path}?v=${avatarVersion.value}`
})

// 组权限等级
const GROUP_ROLE_LEVELS: Record<GroupRole, number> = {
  USER: 1,
  HELPER: 2,
  ADMIN: 3,
}

// 判断是否是超级用户（OWNER 或 ADMIN）
export const isSuperUser = computed(() => user.is_owner || user.is_admin)

// 判断是否是 OWNER
export const isOwner = computed(() => user.is_owner)

// 判断是否是 ADMIN（包括 OWNER）
export const isAdmin = computed(() => user.is_owner || user.is_admin)

// 获取当前选中组中的最高权限等级
export const currentGroupRoleLevel = computed(() => {
  if (activeGroupIds.value.length === 0) return 0
  
  let maxLevel = 0
  for (const gid of activeGroupIds.value) {
    const perm = user.group_permissions.find(p => p.group_id === gid)
    if (perm) {
      const level = GROUP_ROLE_LEVELS[perm.role] ?? 0
      if (level > maxLevel) {
        maxLevel = level
      }
    }
  }
  return maxLevel
})

// 获取有效权限等级（超级用户有最高权限）
export const effectiveRoleLevel = computed(() => {
  if (user.is_owner || user.is_admin) return 99 // 超级用户
  return currentGroupRoleLevel.value
})

// 向后兼容：hasRole 函数
// 对于旧的路由守卫，映射到新权限模型
export type LegacyRole = 'GUEST' | 'USER' | 'HELPER' | 'ADMIN' | 'OWNER'
const LEGACY_ROLE_LEVELS: Record<LegacyRole, number> = {
  GUEST: 0,
  USER: 1,
  HELPER: 2,
  ADMIN: 3,
  OWNER: 99,
}

export const hasRole = (required: LegacyRole) => {
  // OWNER 权限只有 is_owner 才能满足
  if (required === 'OWNER') return user.is_owner
  // ADMIN 权限只有 is_owner 或 is_admin 才能满足
  if (required === 'ADMIN') return user.is_owner || user.is_admin
  // 其他权限检查组权限或超级用户
  if (user.is_owner || user.is_admin) return true
  
  const target = LEGACY_ROLE_LEVELS[required] ?? 0
  return effectiveRoleLevel.value >= target
}

export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me')
    Object.assign(user, response.data)
    
    // Auto-select first group if none selected and not super user
    if (!isSuperUser.value && activeGroupIds.value.length === 0 && user.group_permissions.length > 0) {
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
  user.is_owner = false
  user.is_admin = false
  user.group_permissions = []
  activeGroupIds.value = []
  avatarVersion.value = 0
}

// --- Capabilities ---
export interface Capabilities {
  canManageUsers: boolean
  canManageServers: boolean
  canManagePlugins: boolean
  canViewConsole: boolean
  canManageArchives: boolean
  canViewStatistics: boolean
  canChat: boolean
  canManageSettings: boolean
  canManageServerGroups: boolean
  canManageMods: boolean
  canViewDashboard: boolean
}

export const capabilities = computed<Capabilities>(() => {
  const level = effectiveRoleLevel.value
  const superUser = isSuperUser.value
  return {
    canViewDashboard: level >= 1 || superUser,
    canViewStatistics: level >= 1 || superUser,
    canChat: level >= 1 || superUser,
    canManageArchives: level >= 2 || superUser,
    canManagePlugins: level >= 2 || superUser,
    canViewConsole: superUser,            // 只有超级用户
    canManageServers: superUser,          // 只有超级用户
    canManageUsers: user.is_owner,        // 只有 OWNER
    canManageSettings: superUser,         // 只有超级用户
    canManageServerGroups: superUser,     // 只有超级用户
    canManageMods: superUser,             // 只有超级用户
  }
})

// Helper to check capability
export const can = (capability: keyof Capabilities): boolean => {
  return capabilities.value[capability]
}
