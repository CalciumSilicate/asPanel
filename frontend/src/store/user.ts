import { computed, reactive, ref, watch } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'

const ACTIVE_GROUP_STORAGE_KEY = 'asPanel_activeGroupIds'

/**
 * 权限层级:
 * - OWNER: 超级管理员，可控制一切，包括 is_admin
 * - ADMIN: 平台管理员，可控制系统设置和所有服务器，但不能修改权限字段
 * - 组 ADMIN: 只能管理自己所属组的一切
 * - 组 HELPER: 只能在组内执行操作（插件、配置等）
 * - 组 USER: 只能查看组内的内容
 * 
 * 组之间完全隔离，用户只能看到自己有权限的组
 */

// 组权限等级
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
  // 全局权限
  is_owner: boolean
  is_admin: boolean
  // 组权限
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

// 当前选中的组ID（组上下文）
export const activeGroupIds = ref<number[]>([])

// 当前选中的单个组ID（便于使用）
export const activeGroupId = computed(() => activeGroupIds.value[0] ?? null)

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

// ============ 全局权限判断 ============

/**
 * 是否是 OWNER（超级管理员）
 * OWNER 可以控制一切，包括修改他人的 is_admin/is_owner
 */
export const isOwner = computed(() => user.is_owner)

/**
 * 是否是平台管理员（OWNER 或 ADMIN）
 * 平台管理员可以访问系统设置、所有服务器等
 * 但 ADMIN 不能修改 is_owner/is_admin 字段
 */
export const isPlatformAdmin = computed(() => user.is_owner || user.is_admin)

/**
 * @deprecated 使用 isPlatformAdmin 代替
 * 保留用于向后兼容
 */
export const isSuperUser = computed(() => isPlatformAdmin.value)

/**
 * @deprecated 使用 isPlatformAdmin 代替
 * 保留用于向后兼容
 */
export const isAdmin = computed(() => isPlatformAdmin.value)

// ============ 组权限判断 ============

/**
 * 获取当前选中组中用户的最高权限等级
 */
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

/**
 * 获取用户在指定组的权限等级
 */
export const getGroupRoleLevel = (groupId: number): number => {
  const perm = user.group_permissions.find(p => p.group_id === groupId)
  if (!perm) return 0
  return GROUP_ROLE_LEVELS[perm.role] ?? 0
}

/**
 * 检查用户是否在指定组有指定角色权限
 */
export const hasGroupRole = (groupId: number, requiredRole: GroupRole): boolean => {
  // OWNER 可以绕过组隔离
  if (user.is_owner) return true
  
  const userLevel = getGroupRoleLevel(groupId)
  const requiredLevel = GROUP_ROLE_LEVELS[requiredRole] ?? 0
  return userLevel >= requiredLevel
}

/**
 * 检查用户是否可以访问指定组
 */
export const canAccessGroup = (groupId: number): boolean => {
  // OWNER/ADMIN 可以访问所有组
  if (user.is_owner || user.is_admin) return true
  
  // 普通用户只能访问自己所属的组
  return user.group_permissions.some(p => p.group_id === groupId)
}

/**
 * 获取用户可访问的组列表
 */
export const accessibleGroups = computed(() => {
  // OWNER/ADMIN 返回所有已知组
  // 注意：这里只返回 group_permissions 中的组，完整列表需要从 API 获取
  return user.group_permissions
})

// ============ 有效权限等级（兼容旧代码） ============

/**
 * 获取有效权限等级
 * - 平台管理员返回 99
 * - 普通用户返回当前选中组的权限等级
 */
export const effectiveRoleLevel = computed(() => {
  if (user.is_owner || user.is_admin) return 99
  return currentGroupRoleLevel.value
})

// ============ 旧版兼容 ============

export type LegacyRole = 'GUEST' | 'USER' | 'HELPER' | 'ADMIN' | 'OWNER'
const LEGACY_ROLE_LEVELS: Record<LegacyRole, number> = {
  GUEST: 0,
  USER: 1,
  HELPER: 2,
  ADMIN: 3,
  OWNER: 99,
}

/**
 * 检查用户是否具有指定角色权限
 * 
 * 权限模型:
 * - OWNER: 需要 is_owner
 * - ADMIN: 平台管理员(is_owner/is_admin) 或 当前组内 ADMIN
 * - HELPER: 平台管理员 或 当前组内 HELPER+
 * - USER: 平台管理员 或 当前组内 USER+
 * - GUEST: 只需登录
 */
export const hasRole = (required: LegacyRole) => {
  // OWNER 权限只有 is_owner 才能满足
  if (required === 'OWNER') return user.is_owner
  
  // 平台管理员拥有所有权限
  if (user.is_owner || user.is_admin) return true
  
  // GUEST 只需要登录
  if (required === 'GUEST') return !!user.id
  
  // 对于 ADMIN/HELPER/USER，检查当前选中组的权限
  // 如果没有选中组，则需要检查用户是否有任何组权限满足要求
  const target = LEGACY_ROLE_LEVELS[required] ?? 0
  
  // 如果已选中组，使用 effectiveRoleLevel (基于当前组)
  if (activeGroupIds.value.length > 0) {
    return effectiveRoleLevel.value >= target
  }
  
  // 如果没有选中组（不应该发生），检查用户在任意组的最高权限
  let maxLevel = 0
  for (const perm of user.group_permissions) {
    const level = GROUP_ROLE_LEVELS[perm.role] ?? 0
    if (level > maxLevel) maxLevel = level
  }
  return maxLevel >= target
}

// ============ 用户数据操作 ============

/**
 * 从 localStorage 加载保存的组选择
 */
const loadSavedGroupIds = (): number[] => {
  try {
    const saved = localStorage.getItem(ACTIVE_GROUP_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.every(id => typeof id === 'number')) {
        return parsed
      }
    }
  } catch {
    // ignore
  }
  return []
}

/**
 * 保存组选择到 localStorage
 */
const saveGroupIds = (ids: number[]) => {
  try {
    localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // ignore
  }
}

// 监听 activeGroupIds 变化，自动保存（仅对非平台管理员）
watch(activeGroupIds, (newIds) => {
  // 只有非平台管理员才需要保存组选择
  if (!isPlatformAdmin.value && newIds.length > 0) {
    saveGroupIds(newIds)
  }
}, { deep: true })

export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me')
    Object.assign(user, response.data)
    
    // 平台管理员不需要选择组，直接看到所有内容
    if (isPlatformAdmin.value) {
      activeGroupIds.value = []
      return
    }
    
    // 普通用户：尝试恢复之前保存的组选择
    if (activeGroupIds.value.length === 0 && user.group_permissions.length > 0) {
      const savedIds = loadSavedGroupIds()
      // 验证保存的组ID是否仍然有效（用户仍有权限）
      const validIds = savedIds.filter(id => 
        user.group_permissions.some(p => p.group_id === id)
      )
      
      if (validIds.length > 0) {
        activeGroupIds.value = validIds
      } else {
        // 没有有效的保存选择，使用第一个组
        activeGroupIds.value = [user.group_permissions[0].group_id]
      }
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
  // 登出时清除保存的组选择
  try {
    localStorage.removeItem(ACTIVE_GROUP_STORAGE_KEY)
  } catch {
    // ignore
  }
}

// ============ Capabilities (能力检查) ============

export interface Capabilities {
  // 查看类
  canViewDashboard: boolean
  canViewStatistics: boolean
  canChat: boolean
  // 管理类（需要 HELPER+）
  canManageArchives: boolean
  canManagePlugins: boolean
  canSendAlert: boolean       // 发送全局通知（需要 HELPER+）
  // 管理员类（需要组 ADMIN 或平台管理员）
  canViewConsole: boolean
  canManageServers: boolean
  canManageSettings: boolean
  canManageServerGroups: boolean
  canManageMods: boolean      // 改为组 ADMIN 或平台管理员
  // OWNER 专属
  canManageUsers: boolean
  canManageGlobalPermissions: boolean
}

export const capabilities = computed<Capabilities>(() => {
  const level = effectiveRoleLevel.value
  const platformAdmin = isPlatformAdmin.value
  const owner = isOwner.value
  
  return {
    // 查看类：USER+ 或平台管理员
    canViewDashboard: level >= 1 || platformAdmin,
    canViewStatistics: level >= 1 || platformAdmin,
    canChat: level >= 1 || platformAdmin,
    
    // 管理类：HELPER+ 或平台管理员
    canManageArchives: level >= 2 || platformAdmin,
    canManagePlugins: level >= 2 || platformAdmin,
    canSendAlert: level >= 2 || platformAdmin,     // HELPER+ 才能发送 alert
    
    // 管理员类：组 ADMIN 或平台管理员
    canViewConsole: level >= 3 || platformAdmin,
    canManageServers: platformAdmin,          // 只有平台管理员可以创建/删除服务器
    canManageSettings: platformAdmin,
    canManageServerGroups: platformAdmin,
    canManageMods: level >= 3 || platformAdmin,    // 组 ADMIN 或平台管理员
    
    // OWNER 专属
    canManageUsers: platformAdmin,            // ADMIN 可以管理用户，但不能改权限
    canManageGlobalPermissions: owner,        // 只有 OWNER 可以修改 is_owner/is_admin
  }
})

/**
 * 检查用户是否有指定能力
 */
export const can = (capability: keyof Capabilities): boolean => {
  return capabilities.value[capability]
}
