<template>
  <div class="profile-page">
    <div class="profile-container">
      <!-- 左侧：个人资料卡片 -->
      <div class="profile-left">
        <!-- 头像与基本信息 -->
        <el-card shadow="never" class="profile-card avatar-card">
          <div class="avatar-section">
            <div class="avatar-wrapper" @click="showAvatarDialog = true">
              <el-avatar :size="120" :src="fullAvatarUrl" :icon="UserFilled" />
              <div class="avatar-overlay">
                <el-icon><Camera /></el-icon>
                <span>更换头像</span>
              </div>
            </div>
            <div class="user-info">
              <h2 class="username">{{ user.username }}</h2>
            </div>
          </div>
        </el-card>

        <!-- MC 玩家绑定信息 -->
        <el-card shadow="never" class="profile-card mc-card">
          <template #header>
            <div class="mc-header">
              <span>MC 玩家绑定</span>
              <el-button size="small" link @click="showBindDialog = true">
                {{ mcInfo.name ? '更换绑定' : '绑定玩家' }}
              </el-button>
            </div>
          </template>
          <div class="mc-info" v-if="mcInfo.name">
            <div class="mc-avatar-wrapper">
              <img :src="mcAvatarUrl" class="mc-avatar" alt="MC Avatar" />
            </div>
            <div class="mc-details">
              <div class="mc-name">{{ mcInfo.name }}</div>
              <div class="mc-uuid">{{ mcInfo.uuid }}</div>
            </div>
          </div>
          <el-empty v-else description="未绑定玩家" :image-size="60" />
        </el-card>

        <!-- 个人资料编辑 -->
        <el-card shadow="never" class="profile-card info-card">
          <template #header>
            <span>个人资料</span>
          </template>
          <el-form :model="profileForm" label-position="top" class="profile-form">
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="QQ">
              <el-input v-model="profileForm.qq" placeholder="请输入QQ号" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveProfile" :loading="saving">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 安全设置 -->
        <el-card shadow="never" class="profile-card security-card">
          <template #header>
            <span>安全设置</span>
          </template>
          <el-button @click="showPasswordDialog = true">修改密码</el-button>
        </el-card>

        <!-- 服务器组权限 -->
        <el-card shadow="never" class="profile-card groups-card" v-if="serverGroups.length > 0">
          <template #header>
            <span>可访问的服务器组</span>
          </template>
          <div class="server-groups">
            <el-tag v-for="group in serverGroups" :key="group.id" class="group-tag">
              {{ group.name }}
            </el-tag>
          </div>
        </el-card>
      </div>

      <!-- 右侧：统计信息 -->
      <div class="profile-right">
        <el-card shadow="never" class="profile-card stats-card">
          <template #header>
            <div class="stats-header">
              <span>游戏统计 (待完善)</span>
              <el-select v-model="statsRange" size="small" style="width: 120px;" @change="fetchStats">
                <el-option label="今天" value="1d" />
                <el-option label="本周" value="1w" />
                <el-option label="本月" value="1m" />
                <el-option label="今年" value="1y" />
                <el-option label="全部" value="all" />
              </el-select>
            </div>
          </template>

          <div v-if="statsLoading" class="stats-loading">
            <el-skeleton :rows="6" animated />
          </div>

          <template v-else-if="stats">
            <div class="stats-time-range">{{ stats.time_range?.label }}</div>

            <!-- 统计卡片网格 -->
            <div class="stats-grid" v-if="stats.totals && stats.totals.length > 0">
              <div class="stat-item" v-for="item in stats.totals" :key="item.label">
                <div class="stat-label">{{ item.label }}</div>
                <div class="stat-value">{{ item.label_total }}</div>
                <div class="stat-delta" :class="{ positive: item.delta > 0, negative: item.delta < 0 }" v-if="item.delta !== 0">
                  {{ item.delta > 0 ? '+' : '' }}{{ item.label_delta }}
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无统计数据" :image-size="80" />
          </template>

          <el-empty v-else-if="!mcInfo.name" description="未绑定玩家，无法查看统计" :image-size="80" />
          <el-empty v-else description="暂无统计数据" :image-size="80" />
        </el-card>
      </div>
    </div>

    <!-- 头像上传对话框 -->
    <AvatarUploader v-model:visible="showAvatarDialog" @success="handleAvatarSuccess" />

    <!-- 修改密码对话框 -->
    <el-dialog v-model="showPasswordDialog" title="修改密码" width="400px" @closed="resetPasswordForm">
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-position="top">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码（至少6位）" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="changePassword" :loading="changingPassword">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- 绑定玩家对话框 -->
    <el-dialog v-model="showBindDialog" title="绑定 MC 玩家" width="400px" @closed="resetBindForm">
      <!-- 待验证状态 -->
      <template v-if="pendingBind">
        <div class="pending-bind-info">
          <el-alert type="info" :closable="false" show-icon>
            <template #title>
              <span>正在验证玩家: <strong>{{ pendingBind.player_name }}</strong></span>
            </template>
          </el-alert>
          <div class="verification-code-section">
            <div class="verification-label">请在游戏内输入以下命令:</div>
            <div class="verification-command">
              <code class="command-text">!!bindcode {{ pendingBind.code }}</code>
            </div>
            <div class="verification-expire">
              验证码将在 {{ formatExpireTime(pendingBind) }} 后过期
            </div>
          </div>
        </div>
      </template>
      <!-- 请求绑定表单 -->
      <template v-else>
        <el-form :model="bindForm" :rules="bindRules" ref="bindFormRef" label-position="top">
          <el-form-item label="玩家名" prop="player_name">
            <el-input v-model="bindForm.player_name" placeholder="请输入 MC 玩家名" />
          </el-form-item>
          <div class="bind-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>请输入已在服务器中登录过的玩家名，提交后需在游戏内验证</span>
          </div>
        </el-form>
      </template>
      <template #footer>
        <template v-if="pendingBind">
          <el-button @click="cancelBindRequest" :loading="canceling">取消验证</el-button>
          <el-button type="primary" @click="showBindDialog = false">关闭</el-button>
        </template>
        <template v-else>
          <el-button @click="showBindDialog = false">取消</el-button>
          <el-button type="primary" @click="requestBindPlayer" :loading="binding">请求绑定</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { UserFilled, Camera, InfoFilled, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { user, fullAvatarUrl, fetchUser, refreshAvatar } from '@/store/user'
import AvatarUploader from '@/components/AvatarUploader.vue'
import apiClient, { bindApi } from '@/api'

// 头像对话框
const showAvatarDialog = ref(false)

// MC 信息
const mcInfo = reactive({
  name: '',
  uuid: ''
})

// 服务器组
const serverGroups = ref<{ id: number; name: string }[]>([])

// 个人资料表单
const profileForm = reactive({
  email: '',
  qq: ''
})
const saving = ref(false)

// 密码修改
const showPasswordDialog = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})
const changingPassword = ref(false)

// 玩家绑定
const showBindDialog = ref(false)
const bindFormRef = ref<FormInstance>()
const bindForm = reactive({
  player_name: ''
})
const binding = ref(false)
const canceling = ref(false)

// 待验证绑定信息
interface PendingBind {
  player_name: string
  code: string
  expires_at?: number  // Unix timestamp (seconds) - from getPending
  expires_in_seconds?: number  // from requestBind
}
const pendingBind = ref<PendingBind | null>(null)

const bindRules: FormRules = {
  player_name: [
    { required: true, message: '请输入玩家名', trigger: 'blur' },
    { min: 1, max: 16, message: '玩家名长度为1-16个字符', trigger: 'blur' }
  ]
}

const passwordRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 统计数据
const statsRange = ref('1w')
const statsLoading = ref(false)
const stats = ref<any>(null)

// 角色相关
const roleLabel = computed(() => {
  const labels: Record<string, string> = {
    GUEST: '访客',
    USER: '用户',
    HELPER: '助手',
    ADMIN: '管理员',
    OWNER: '所有者'
  }
  return labels[user.role] || user.role
})

const roleTagType = computed(() => {
  const types: Record<string, string> = {
    GUEST: 'info',
    USER: '',
    HELPER: 'success',
    ADMIN: 'warning',
    OWNER: 'danger'
  }
  return types[user.role] || ''
})

// MC 头像 URL
const mcAvatarUrl = computed(() => {
  if (!mcInfo.uuid) return ''
  return `/api/users/mc/avatar/${mcInfo.uuid}`
})

// 初始化
onMounted(async () => {
  await loadUserInfo()
  await checkPendingBind()
  await fetchStats()
})

async function loadUserInfo() {
  try {
    const res = await apiClient.get('/api/users/me')
    const data = res.data

    // 更新 MC 信息
    mcInfo.name = data.mc_name || ''
    mcInfo.uuid = data.mc_uuid || ''

    // 更新表单
    profileForm.email = data.email || ''
    profileForm.qq = data.qq || ''

    // 获取服务器组信息
    if (data.server_link_group_ids && data.server_link_group_ids.length > 0) {
      await loadServerGroups(data.server_link_group_ids)
    }
  } catch (e: any) {
    ElMessage.error('加载用户信息失败')
  }
}

async function loadServerGroups(ids: number[]) {
  try {
    const res = await apiClient.get('/api/server-groups')
    const allGroups = res.data || []
    serverGroups.value = allGroups.filter((g: any) => ids.includes(g.id))
  } catch (e) {
    // 静默失败
  }
}

async function fetchStats() {
  if (!mcInfo.uuid) return

  statsLoading.value = true
  try {
    const res = await apiClient.get('/api/users/me/stats', {
      params: { range: statsRange.value }
    })
    stats.value = res.data
  } catch (e: any) {
    if (e.response?.status !== 400) {
      ElMessage.error('加载统计数据失败')
    }
    stats.value = null
  } finally {
    statsLoading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  try {
    await apiClient.patch('/api/users/me', {
      email: profileForm.email || null,
      qq: profileForm.qq || null
    })
    ElMessage.success('保存成功')
    await fetchUser()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function handleAvatarSuccess() {
  fetchUser()
  refreshAvatar()
}

function resetPasswordForm() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordFormRef.value?.resetFields()
}

async function changePassword() {
  if (!passwordFormRef.value) return

  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  changingPassword.value = true
  try {
    await apiClient.post('/api/users/me/password', {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码修改成功')
    showPasswordDialog.value = false
    resetPasswordForm()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    changingPassword.value = false
  }
}

function resetBindForm() {
  bindForm.player_name = ''
  bindFormRef.value?.resetFields()
}

async function checkPendingBind() {
  try {
    const res = await bindApi.getPending()
    if (res.data && res.data.code) {
      pendingBind.value = res.data
    } else {
      pendingBind.value = null
    }
  } catch (e: any) {
    if (e.response?.status !== 404) {
      console.error('Failed to check pending bind:', e)
    }
    pendingBind.value = null
  }
}

async function requestBindPlayer() {
  if (!bindFormRef.value) return

  try {
    await bindFormRef.value.validate()
  } catch {
    return
  }

  binding.value = true
  try {
    const res = await bindApi.requestBind(bindForm.player_name.trim())
    pendingBind.value = res.data
    ElMessage.success('绑定请求已提交，请在游戏内验证')
    resetBindForm()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '请求绑定失败')
  } finally {
    binding.value = false
  }
}

async function cancelBindRequest() {
  canceling.value = true
  try {
    await bindApi.cancelBind()
    pendingBind.value = null
    ElMessage.success('已取消绑定请求')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '取消失败')
  } finally {
    canceling.value = false
  }
}

function formatExpireTime(pending: PendingBind): string {
  let expiresMs: number
  
  if (pending.expires_at) {
    // Unix timestamp (seconds) from getPending
    expiresMs = pending.expires_at * 1000
  } else if (pending.expires_in_seconds) {
    // Relative seconds from requestBind - calculate from now
    expiresMs = Date.now() + pending.expires_in_seconds * 1000
  } else {
    return '未知'
  }
  
  const diffMs = expiresMs - Date.now()
  if (diffMs <= 0) return '已过期'
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '不到1分钟'
  if (diffMin < 60) return `${diffMin}分钟`
  const diffHour = Math.floor(diffMin / 60)
  return `${diffHour}小时${diffMin % 60}分钟`
}

const copyBindCommand = async () => {
  if (!pendingBind.value?.code) return
  const command = `!!bindcode ${pendingBind.value.code}`
  try {
    await navigator.clipboard.writeText(command)
    ElMessage.success('命令已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style scoped>
.profile-page {
  padding: 0;
  height: calc(100vh - var(--el-header-height) - 40px);
  overflow-y: auto;
}

.profile-container {
  display: flex;
  gap: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.profile-left {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-right {
  flex: 1;
  min-width: 0;
}

.profile-card {
  border-radius: 12px;
}

.profile-card :deep(.el-card__header) {
  padding: 16px 20px;
  font-weight: 600;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.profile-card :deep(.el-card__body) {
  padding: 20px;
}

/* 头像卡片 */
.avatar-card :deep(.el-card__body) {
  padding: 24px;
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.avatar-wrapper {
  position: relative;
  cursor: pointer;
  border-radius: 50%;
  overflow: hidden;
}

.avatar-wrapper:hover .avatar-overlay {
  opacity: 1;
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #fff;
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s;
}

.avatar-overlay .el-icon {
  font-size: 24px;
}

.user-info {
  text-align: center;
}

.username {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.role-tag {
  font-size: 12px;
}

/* MC 卡片 */
.mc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mc-header .el-button {
  color: var(--el-color-primary);
}

.mc-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.mc-avatar-wrapper {
  flex-shrink: 0;
}

.mc-avatar {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  image-rendering: pixelated;
}

.mc-details {
  min-width: 0;
}

.mc-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.mc-uuid {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
  word-break: break-all;
}

/* 个人资料表单 */
.profile-form .el-form-item {
  margin-bottom: 16px;
}

.profile-form .el-form-item:last-child {
  margin-bottom: 0;
  margin-top: 8px;
}

/* 服务器组 */
.server-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-tag {
  font-size: 13px;
}

/* 统计卡片 */
.stats-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stats-time-range {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 16px;
}

.stats-loading {
  padding: 20px 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

.stat-item {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 16px;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.stat-delta {
  font-size: 12px;
  margin-top: 4px;
}

.stat-delta.positive {
  color: var(--el-color-success);
}

.stat-delta.negative {
  color: var(--el-color-danger);
}

/* 绑定提示 */
.bind-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: -8px;
}

.bind-tip .el-icon {
  font-size: 14px;
}

/* 待验证绑定信息 */
.pending-bind-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.verification-code-section {
  text-align: center;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.verification-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}

.verification-code {
  font-size: 32px;
  font-weight: 700;
  font-family: monospace;
  letter-spacing: 4px;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}

.verification-command {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
}

.command-text {
  font-size: 18px;
  font-weight: 600;
  font-family: monospace;
  color: var(--el-color-primary);
  background: var(--el-fill-color);
  padding: 8px 16px;
  border-radius: 6px;
  user-select: all;
}

.verification-expire {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 响应式 */
@media (max-width: 900px) {
  .profile-container {
    flex-direction: column;
  }

  .profile-left {
    flex: none;
    width: 100%;
  }
}
</style>
