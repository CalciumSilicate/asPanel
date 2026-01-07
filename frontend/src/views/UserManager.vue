<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="header-bar">
          <div class="flex items-center header-title">
            <span class="text-base font-medium">用户管理</span>
            <el-tag type="info" class="title-count">共 {{ filteredRows.length }} 个用户</el-tag>
          </div>
          <div class="header-actions">
            <el-button-group>
              <el-button type="success" :icon="Refresh" @click="load">刷新</el-button>
              <el-button type="danger" :icon="Delete" :disabled="selection.length===0" @click="batchDelete">批量删除</el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <div class="toolbar mb-2">
        <el-input v-model="query" placeholder="搜索 用户名/邮箱/QQ/玩家/UUID" clearable style="max-width: 320px;">
          <template #prefix><el-icon><Search/></el-icon></template>
        </el-input>
        <el-select v-model="adminFilter" clearable placeholder="筛选权限" style="width: 160px;">
          <el-option label="管理员" :value="true" />
          <el-option label="普通用户" :value="false" />
        </el-select>
      </div>

      <div class="table-container">
        <el-table
          :data="pagedRows"
          size="small"
          stripe
          :height="'100%'"
          @selection-change="(rows:any[])=>selection=rows"
          row-key="id"
        >
          <el-table-column type="selection" width="45" />
          <el-table-column label="ID" width="70" prop="id" sortable />
          <el-table-column label="头像" width="90" align="center">
            <template #default="{ row }">
              <div class="avatar-wrap" @click="openAvatar(row)">
                <img v-if="avatarSrc(row)" class="avatar" :src="avatarSrc(row)" alt="avatar" />
                <div v-else class="avatar placeholder"/>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="用户名" min-width="160">
            <template #default="{ row }">
              <template v-if="editing.rowId===row.id && editing.field==='username'">
                <el-input v-model="editing.value" size="small" @keyup.enter.native="submitEdit(row,'username')" @blur="cancelEdit" />
              </template>
              <template v-else>
                <span class="clickable" @click="startEdit(row, 'username', row.username)">{{ row.username }}</span>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="绑定玩家" min-width="260">
            <template #default="{ row }">
              <template v-if="editing.rowId===row.id && editing.field==='bound_player'">
                <el-select v-model="editing.value" filterable clearable placeholder="选择玩家" style="width: 220px;" @change="submitEdit(row,'bound_player')" @blur="cancelEdit">
                  <el-option
                    v-for="p in players"
                    :key="p.id"
                    :label="p.player_name ? `${p.player_name} (${p.uuid})` : p.uuid"
                    :value="p.id"
                  />
                </el-select>
              </template>
              <template v-else>
                <div class="name-cell" @click="startEdit(row, 'bound_player', row.bound_player_id)">
                  <div class="pname">{{ row.mc_name || '（未绑定）' }}</div>
                  <div class="uuid">{{ row.mc_uuid || '' }}</div>
                </div>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="QQ" min-width="150">
            <template #default="{ row }">
              <template v-if="editing.rowId===row.id && editing.field==='qq'">
                <el-input v-model="editing.value" size="small" @keyup.enter.native="submitEdit(row,'qq')" @blur="cancelEdit" />
              </template>
              <template v-else>
                <span class="clickable" @click="startEdit(row,'qq', row.qq || '')">{{ row.qq || '—' }}</span>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="邮箱" min-width="200">
            <template #default="{ row }">
              <template v-if="editing.rowId===row.id && editing.field==='email'">
                <el-input v-model="editing.value" size="small" @keyup.enter.native="submitEdit(row,'email')" @blur="cancelEdit" />
              </template>
              <template v-else>
                <span class="clickable" @click="startEdit(row,'email', row.email || '')">{{ row.email || '—' }}</span>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="全局权限" width="180" align="center">
            <template #default="{ row }">
              <div class="global-perm-cell">
                <el-tag v-if="row.is_owner" type="danger" size="small">OWNER</el-tag>
                <el-tag v-else-if="row.is_admin" type="warning" size="small">ADMIN</el-tag>
                <el-tag v-else type="info" size="small">普通用户</el-tag>
              </div>
              <el-button v-if="isOwner" size="small" type="primary" link @click="openGlobalPermDialog(row)">编辑</el-button>
            </template>
          </el-table-column>
          <el-table-column label="组权限" min-width="200" align="center">
            <template #default="{ row }">
              <div class="group-perms-cell">
                <template v-if="row.group_permissions && row.group_permissions.length > 0">
                  <el-tag 
                    v-for="perm in row.group_permissions.slice(0, 2)" 
                    :key="perm.group_id" 
                    size="small" 
                    :type="groupRoleTagType(perm.role)"
                    class="group-perm-tag"
                  >
                    {{ perm.group_name }}: {{ perm.role }}
                  </el-tag>
                  <el-tag v-if="row.group_permissions.length > 2" size="small" type="info">
                    +{{ row.group_permissions.length - 2 }}
                  </el-tag>
                </template>
                <span v-else class="no-perm">无组权限</span>
              </div>
              <el-button size="small" type="primary" link @click="openGroupPermDialog(row)">编辑</el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center">
            <template #default="{ row }">
              <el-button-group>
                <el-button type="warning" :icon="Key" @click="resetPassword(row)">重设密码</el-button>
                <el-button type="danger" :icon="Delete" @click="deleteOne(row)">删除</el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="um-pagination">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          :total="filteredRows.length"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <AvatarUploader v-model:visible="avatarVisible" :target-user-id="avatarUserId" @success="load" />

    <!-- 组权限编辑弹窗 -->
    <el-dialog v-model="groupPermDialogVisible" title="编辑组权限" width="600px">
      <el-table :data="editingGroupPerms" size="small" max-height="400">
        <el-table-column label="服务器组" prop="group_name" min-width="150" />
        <el-table-column label="权限" width="180" align="center">
          <template #default="{ row, $index }">
            <el-select v-model="editingGroupPerms[$index].role" size="small" style="width: 140px;">
              <el-option v-for="r in GROUP_ROLES" :key="r" :label="r" :value="r" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="groupPermDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGroupPerms">保存</el-button>
      </template>
    </el-dialog>

    <!-- 全局权限编辑弹窗 -->
    <el-dialog v-model="globalPermDialogVisible" title="编辑全局权限" width="400px">
      <el-form label-width="100px">
        <el-form-item label="用户名">
          <span>{{ editingGlobalPermUser?.username }}</span>
        </el-form-item>
        <el-form-item label="OWNER">
          <el-switch v-model="editingIsOwner" :disabled="editingGlobalPermUser?.id === currentUserId" />
          <span class="perm-desc">超级管理员，可管理所有权限</span>
        </el-form-item>
        <el-form-item label="ADMIN">
          <el-switch v-model="editingIsAdmin" />
          <span class="perm-desc">管理员，可管理组权限</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="globalPermDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGlobalPerm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh, Delete, Key } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import AvatarUploader from '@/components/AvatarUploader.vue'
import { isOwner } from '@/store/user'

// 组权限等级（新版本，不含 GUEST 和 OWNER）
type GroupRole = 'USER' | 'HELPER' | 'ADMIN'

type GroupPermission = {
  group_id: number
  group_name: string
  role: GroupRole
}

type UserRow = {
  id: number
  username: string
  avatar_url?: string | null
  is_owner: boolean
  is_admin: boolean
  email?: string | null
  qq?: string | null
  bound_player_id?: number | null
  mc_uuid?: string | null
  mc_name?: string | null
  group_permissions?: GroupPermission[]
}

type ServerGroup = {
  id: number
  name: string
}

type Player = { id: number, uuid: string, player_name?: string | null }

// 组权限等级选项（新版本）
const GROUP_ROLES: GroupRole[] = ['USER', 'HELPER', 'ADMIN']

const rows = ref<UserRow[]>([])
const players = ref<Player[]>([])
const serverGroups = ref<ServerGroup[]>([])
const query = ref('')
const adminFilter = ref<boolean | undefined>()
const page = ref(1)
const pageSize = ref(20)
const onPageChange = (p: number) => { page.value = p }
const onPageSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
}
const selection = ref<UserRow[]>([])

const load = async () => {
  const { data } = await api.get('/api/users')
  rows.value = (data || []).slice().sort((a:UserRow,b:UserRow)=>a.id-b.id)
}
const loadPlayers = async () => {
  const { data } = await api.get('/api/players', { params: { scope: 'all' } })
  players.value = data || []
}
const loadServerGroups = async () => {
  const { data } = await api.get('/api/tools/server-link/groups')
  serverGroups.value = data || []
}

const filteredRows = computed(() => {
  let base = rows.value
  if (adminFilter.value !== undefined) {
    base = base.filter(r => adminFilter.value ? (r.is_owner || r.is_admin) : (!r.is_owner && !r.is_admin))
  }
  const q = query.value.trim().toLowerCase()
  if (!q) return base
  return base.filter(r => {
    const fields = [r.username, r.email||'', r.qq||'', r.mc_name||'', r.mc_uuid||'']
    return fields.some(v => (v||'').toLowerCase().includes(q))
  })
})

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

// 组权限标签颜色
const groupRoleTagType = (role: string): 'primary' | 'success' | 'info' | 'warning' | 'danger' => {
  switch (role) {
    case 'USER': return 'primary'
    case 'HELPER': return 'success'
    case 'ADMIN': return 'warning'
    default: return 'info'
  }
}

// 当前用户 ID
import { user as currentUser } from '@/store/user'
const currentUserId = computed(() => currentUser.id)

// 编辑逻辑
const editing = ref<{rowId:number|null, field:string|null, value:any}>({ rowId: null, field: null, value: '' })
const startEdit = (row:UserRow, field:string, value:any) => {
  editing.value = { rowId: row.id, field, value }
}
const cancelEdit = () => { editing.value = { rowId: null, field: null, value: '' } }
const submitEdit = async (row:UserRow, field:string) => {
  const body: any = {}
  if (field === 'username') body.username = (editing.value.value||'').trim()
  if (field === 'email') body.email = (editing.value.value||'').trim()
  if (field === 'qq') body.qq = (editing.value.value||'').trim()
  if (field === 'bound_player') body.bound_player_id = editing.value.value || null
  try {
    await api.patch(`/api/users/${row.id}`, body)
    await load()
  } catch (e:any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    cancelEdit()
  }
}

// 头像
const avatarVisible = ref(false)
const avatarUserId = ref<number|null>(null)
const avatarSrc = (row:UserRow) => {
  if (row.avatar_url) return row.avatar_url.startsWith('/') ? row.avatar_url : `/${row.avatar_url}`
  if (row.mc_uuid) return `/api/users/mc/avatar/${encodeURIComponent(row.mc_uuid)}`
  if (row.mc_name) return `/api/users/mc/avatar/${encodeURIComponent(row.mc_name)}`
  return ''
}
const openAvatar = (row:UserRow) => {
  avatarUserId.value = row.id
  avatarVisible.value = true
}

// 全局权限编辑
const globalPermDialogVisible = ref(false)
const editingGlobalPermUser = ref<UserRow | null>(null)
const editingIsOwner = ref(false)
const editingIsAdmin = ref(false)

const openGlobalPermDialog = (row: UserRow) => {
  editingGlobalPermUser.value = row
  editingIsOwner.value = row.is_owner
  editingIsAdmin.value = row.is_admin
  globalPermDialogVisible.value = true
}

const saveGlobalPerm = async () => {
  if (!editingGlobalPermUser.value) return
  try {
    await api.patch(`/api/users/${editingGlobalPermUser.value.id}`, {
      is_owner: editingIsOwner.value,
      is_admin: editingIsAdmin.value
    })
    ElMessage.success('全局权限已更新')
    globalPermDialogVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存全局权限失败')
  }
}

// 操作
const resetPassword = async (row:UserRow) => {
  try {
    const { data } = await api.post(`/api/users/${row.id}/reset-password`)
    await ElMessageBox.alert(`新密码：${data.new_password}`, '已生成新密码', { confirmButtonText: '知道了' })
  } catch (e:any) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}
const deleteOne = async (row:UserRow) => {
  try {
    await ElMessageBox.confirm(`确认删除用户 ${row.username}？`, '删除确认', { type: 'warning' })
    await api.delete(`/api/users/${row.id}`)
    await load()
  } catch (e:any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}
const batchDelete = async () => {
  try {
    const ids = selection.value.map(r => r.id)
    await ElMessageBox.confirm(`确认批量删除 ${ids.length} 个用户？`, '批量删除', { type: 'warning' })
    await api.delete('/api/users', { data: { ids } })
    await load()
    selection.value = []
  } catch (e:any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '批量删除失败')
  }
}

// 组权限编辑
const groupPermDialogVisible = ref(false)
const editingGroupPermsUserId = ref<number | null>(null)
const editingGroupPerms = ref<GroupPermission[]>([])

const getUserGroupRole = (row: UserRow, groupId: number): string => {
  const perm = row.group_permissions?.find(p => p.group_id === groupId)
  return perm?.role || '—'
}

const openGroupPermDialog = (row: UserRow) => {
  editingGroupPermsUserId.value = row.id
  // 初始化：为每个服务器组设置当前权限（如果有）
  editingGroupPerms.value = serverGroups.value.map(g => {
    const existing = row.group_permissions?.find(p => p.group_id === g.id)
    return {
      group_id: g.id,
      group_name: g.name,
      role: existing?.role || 'USER'
    } as GroupPermission
  })
  groupPermDialogVisible.value = true
}

const saveGroupPerms = async () => {
  if (!editingGroupPermsUserId.value) return
  try {
    // 过滤掉没有设置的（保持默认USER的也发送）
    const perms = editingGroupPerms.value.map(p => ({
      group_id: p.group_id,
      group_name: p.group_name,
      role: p.role
    }))
    await api.patch(`/api/users/${editingGroupPermsUserId.value}`, {
      group_permissions: perms
    })
    ElMessage.success('组权限已更新')
    groupPermDialogVisible.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存组权限失败')
  }
}

onMounted(async () => {
  await Promise.all([load(), loadPlayers(), loadServerGroups()])
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow: hidden; }
.mb-2 { margin-bottom: 8px; }
.header-title .title-count { margin-left: 8px; }
.header-actions { display:flex; align-items:center; gap:8px; white-space: nowrap; }
.header-bar { display:flex; align-items:center; justify-content: space-between; flex-wrap: nowrap; }
.header-title { display:flex; align-items:center; }

:deep(.el-card) { height: 100%; display: flex; flex-direction: column; }
:deep(.el-card__body) { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.table-container { flex: 1 1 auto; min-height: 0; overflow: hidden; }

:deep(.el-table--small .el-table__cell) { padding-top: 4px; padding-bottom: 4px; }
:deep(.el-table .cell) { padding-top: 0; padding-bottom: 0; }
.clickable { cursor: pointer; }
.name-cell { display: flex; flex-direction: column; }
.name-cell .pname { font-weight: 600; color: var(--el-text-color-primary); }
.name-cell .uuid { color: var(--el-text-color-secondary); font-size: 12px; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: #bbb; }
.avatar.placeholder { background: #e5e7eb; }
.avatar-wrap { display: inline-flex; align-items:center; justify-content:center; width:36px; height:36px; margin: 2px auto; }
.um-pagination { display: flex; justify-content: flex-end; margin-top: 8px; }
.group-perms-cell { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; margin-bottom: 4px; }
.group-perm-tag { margin: 1px; }
.no-perm { color: var(--el-text-color-secondary); font-size: 12px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.global-perm-cell { margin-bottom: 4px; }
.perm-desc { margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
