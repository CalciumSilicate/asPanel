import { computed, reactive, ref } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'

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
 * @deprecated 使用新的权限检查函数
 * 
 * 旧版角色检查，映射到新权限模型:
 * - OWNER: 需要 is_owner
 * - ADMIN: 需要 is_owner 或 is_admin
 * - HELPER/USER/GUEST: 检查组权限或平台管理员
 */
export const hasRole = (required: LegacyRole) => {
  // OWNER 权限只有 is_owner 才能满足
  if (required === 'OWNER') return user.is_owner
  // ADMIN 权限只有 is_owner 或 is_admin 才能满足
  if (required === 'ADMIN') return user.is_owner || user.is_admin
  // 平台管理员拥有所有低级权限
  if (user.is_owner || user.is_admin) return true
  // GUEST 只需要登录
  if (required === 'GUEST') return !!user.id
  // USER/HELPER 需要有组权限
  // 如果用户已登录但没有任何组权限，允许基本访问（USER 级别）
  if (required === 'USER' && user.id) return true
  
  const target = LEGACY_ROLE_LEVELS[required] ?? 0
  return effectiveRoleLevel.value >= target
}

// ============ 用户数据操作 ============

export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me')
    Object.assign(user, response.data)
    
    // 非平台管理员：自动选择第一个组
    if (!isPlatformAdmin.value && activeGroupIds.value.length === 0 && user.group_permissions.length > 0) {
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

// ============ Capabilities (能力检查) ============

export interface Capabilities {
  // 查看类
  canViewDashboard: boolean
  canViewStatistics: boolean
  canChat: boolean
  // 管理类（需要 HELPER+）
  canManageArchives: boolean
  canManagePlugins: boolean
  // 管理员类（需要组 ADMIN 或平台管理员）
  canViewConsole: boolean
  canManageServers: boolean
  canManageSettings: boolean
  canManageServerGroups: boolean
  canManageMods: boolean
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
    
    // 管理员类：组 ADMIN 或平台管理员
    canViewConsole: level >= 3 || platformAdmin,
    canManageServers: platformAdmin,          // 只有平台管理员可以创建/删除服务器
    canManageSettings: platformAdmin,
    canManageServerGroups: platformAdmin,
    canManageMods: level >= 2 || platformAdmin,
    
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
