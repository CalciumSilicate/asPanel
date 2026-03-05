import { computed, reactive, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import apiClient, { isRequestCanceled } from '@/api'

const ACTIVE_GROUP_STORAGE_KEY = 'asPanel_activeGroupIds'

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
  is_owner: boolean
  is_admin: boolean
  group_permissions: GroupPermission[]
}

export type LegacyRole = 'GUEST' | 'USER' | 'HELPER' | 'ADMIN' | 'OWNER'

export interface Capabilities {
  canViewDashboard: boolean
  canViewStatistics: boolean
  canChat: boolean
  canManageArchives: boolean
  canManagePlugins: boolean
  canSendAlert: boolean
  canViewConsole: boolean
  canManageServers: boolean
  canManageSettings: boolean
  canManageServerGroups: boolean
  canManageMods: boolean
  canManageUsers: boolean
  canManageGlobalPermissions: boolean
}

const GROUP_ROLE_LEVELS: Record<GroupRole, number> = { USER: 1, HELPER: 2, ADMIN: 3 }
const LEGACY_ROLE_LEVELS: Record<LegacyRole, number> = { GUEST: 0, USER: 1, HELPER: 2, ADMIN: 3, OWNER: 99 }

export const useUserStore = defineStore('user', () => {
  const user = reactive<UserState>({
    id: null,
    username: '',
    email: '',
    avatar_url: '',
    is_owner: false,
    is_admin: false,
    group_permissions: [],
  })

  const activeGroupIds = ref<number[]>([])
  const avatarVersion = ref(0)

  const activeGroupId = computed(() => activeGroupIds.value[0] ?? null)

  const fullAvatarUrl = computed(() => {
    if (!user.avatar_url) return undefined
    const path = user.avatar_url.startsWith('/') ? user.avatar_url : `/${user.avatar_url}`
    return `${path}?v=${avatarVersion.value}`
  })

  const isOwner = computed(() => user.is_owner)
  const isPlatformAdmin = computed(() => user.is_owner || user.is_admin)
  /** @deprecated use isPlatformAdmin */
  const isSuperUser = computed(() => isPlatformAdmin.value)
  /** @deprecated use isPlatformAdmin */
  const isAdmin = computed(() => isPlatformAdmin.value)

  const currentGroupRoleLevel = computed(() => {
    if (activeGroupIds.value.length === 0) return 0
    let maxLevel = 0
    for (const gid of activeGroupIds.value) {
      const perm = user.group_permissions.find((p) => p.group_id === gid)
      if (perm) {
        const level = GROUP_ROLE_LEVELS[perm.role] ?? 0
        if (level > maxLevel) maxLevel = level
      }
    }
    return maxLevel
  })

  const getGroupRoleLevel = (groupId: number): number => {
    const perm = user.group_permissions.find((p) => p.group_id === groupId)
    if (!perm) return 0
    return GROUP_ROLE_LEVELS[perm.role] ?? 0
  }

  const hasGroupRole = (groupId: number, requiredRole: GroupRole): boolean => {
    if (user.is_owner) return true
    return getGroupRoleLevel(groupId) >= (GROUP_ROLE_LEVELS[requiredRole] ?? 0)
  }

  const canAccessGroup = (groupId: number): boolean => {
    if (user.is_owner || user.is_admin) return true
    return user.group_permissions.some((p) => p.group_id === groupId)
  }

  const accessibleGroups = computed(() => user.group_permissions)

  const effectiveRoleLevel = computed(() => {
    if (user.is_owner || user.is_admin) return 99
    return currentGroupRoleLevel.value
  })

  const hasRole = (required: LegacyRole): boolean => {
    if (required === 'OWNER') return user.is_owner
    if (user.is_owner || user.is_admin) return true
    if (required === 'GUEST') return !!user.id
    const target = LEGACY_ROLE_LEVELS[required] ?? 0
    if (activeGroupIds.value.length > 0) return effectiveRoleLevel.value >= target
    let maxLevel = 0
    for (const perm of user.group_permissions) {
      const level = GROUP_ROLE_LEVELS[perm.role] ?? 0
      if (level > maxLevel) maxLevel = level
    }
    return maxLevel >= target
  }

  const capabilities = computed<Capabilities>(() => {
    const level = effectiveRoleLevel.value
    const platformAdmin = isPlatformAdmin.value
    const owner = isOwner.value
    return {
      canViewDashboard: level >= 1 || platformAdmin,
      canViewStatistics: level >= 1 || platformAdmin,
      canChat: level >= 1 || platformAdmin,
      canManageArchives: level >= 2 || platformAdmin,
      canManagePlugins: level >= 2 || platformAdmin,
      canSendAlert: level >= 2 || platformAdmin,
      canViewConsole: level >= 3 || platformAdmin,
      canManageServers: platformAdmin,
      canManageSettings: platformAdmin,
      canManageServerGroups: platformAdmin,
      canManageMods: level >= 3 || platformAdmin,
      canManageUsers: platformAdmin,
      canManageGlobalPermissions: owner,
    }
  })

  const can = (capability: keyof Capabilities): boolean => capabilities.value[capability]

  const loadSavedGroupIds = (): number[] => {
    try {
      const saved = localStorage.getItem(ACTIVE_GROUP_STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.every((id) => typeof id === 'number')) return parsed
      }
    } catch { /* ignore */ }
    return []
  }

  const saveGroupIds = (ids: number[]) => {
    try { localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, JSON.stringify(ids)) } catch { /* ignore */ }
  }

  watch(activeGroupIds, (newIds) => {
    if (!isPlatformAdmin.value && newIds.length > 0) saveGroupIds(newIds)
  }, { deep: true })

  const fetchUser = async () => {
    try {
      const response = await apiClient.get('/api/users/me')
      Object.assign(user, response.data)
      if (isPlatformAdmin.value) { activeGroupIds.value = []; return }
      if (activeGroupIds.value.length === 0 && user.group_permissions.length > 0) {
        const savedIds = loadSavedGroupIds()
        const validIds = savedIds.filter((id) => user.group_permissions.some((p) => p.group_id === id))
        activeGroupIds.value = validIds.length > 0 ? validIds : [user.group_permissions[0].group_id]
      }
    } catch (error) {
      if (isRequestCanceled(error)) return
      console.error('Failed to fetch user:', error)
      clearUser()
    }
  }

  const refreshAvatar = () => { avatarVersion.value++ }

  const clearUser = () => {
    user.id = null
    user.username = ''
    user.email = ''
    user.avatar_url = ''
    user.is_owner = false
    user.is_admin = false
    user.group_permissions = []
    activeGroupIds.value = []
    avatarVersion.value = 0
    try { localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY) } catch { /* ignore */ }
  }

  return {
    user,
    activeGroupIds,
    activeGroupId,
    fullAvatarUrl,
    isOwner,
    isPlatformAdmin,
    isSuperUser,
    isAdmin,
    currentGroupRoleLevel,
    effectiveRoleLevel,
    accessibleGroups,
    capabilities,
    getGroupRoleLevel,
    hasGroupRole,
    canAccessGroup,
    hasRole,
    can,
    fetchUser,
    refreshAvatar,
    clearUser,
  }
})
