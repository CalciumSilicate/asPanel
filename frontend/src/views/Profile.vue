<template>
  <div class="profile-page">
    <div class="profile-shell">
      <section class="profile-hero profile-card">
        <div class="hero-orb hero-orb--blue" aria-hidden="true" />
        <div class="hero-orb hero-orb--pink" aria-hidden="true" />

        <div class="hero-main">
          <button class="avatar-hero" type="button" @click="showAvatarDialog = true">
            <el-avatar :size="104" :src="fullAvatarUrl" :icon="UserFilled" />
            <span class="avatar-hero__hint">
              <el-icon><Camera /></el-icon>
              更换头像
            </span>
          </button>

          <div class="hero-copy">
            <div class="hero-title-row">
              <div>
                <h1 class="hero-title">{{ user.username }}</h1>
                <p class="hero-subtitle">管理你的账号信息、绑定状态与游戏统计</p>
              </div>
              <el-tag class="role-pill" :type="roleTagType || 'info'" effect="dark">{{ roleLabel }}</el-tag>
            </div>

            <div class="hero-meta">
              <span class="meta-chip">
                <el-icon><Message /></el-icon>
                {{ profileForm.email || '未填写邮箱' }}
              </span>
              <span class="meta-chip">
                <el-icon><ChatDotRound /></el-icon>
                {{ profileForm.qq || '未填写 QQ' }}
              </span>
              <span class="meta-chip">
                <el-icon><FolderOpened /></el-icon>
                {{ serverGroups.length }} 个服务器组
              </span>
            </div>
          </div>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat__label">账号安全</span>
            <strong>{{ showPasswordDialog ? '处理中' : '已启用密码登录' }}</strong>
          </div>
          <div class="hero-stat">
            <span class="hero-stat__label">MC 绑定</span>
            <strong>{{ mcInfo.name || '未绑定玩家' }}</strong>
          </div>
          <div class="hero-stat">
            <span class="hero-stat__label">统计范围</span>
            <strong>{{ rangeLabelMap[statsRange] }}</strong>
          </div>
        </div>
      </section>

      <div class="profile-layout">
        <div class="profile-main-column">
          <el-card shadow="never" class="profile-card section-card">
            <template #header>
              <div class="section-head">
                <div>
                  <span class="section-title">个人资料</span>
                  <p class="section-subtitle">完善联系信息，方便接收通知与身份识别。</p>
                </div>
                <el-button type="primary" @click="saveProfile" :loading="saving">保存修改</el-button>
              </div>
            </template>

            <el-form :model="profileForm" label-position="top" class="profile-form two-col-form">
              <el-form-item label="邮箱">
                <el-input v-model="profileForm.email" placeholder="请输入邮箱" clearable />
              </el-form-item>
              <el-form-item label="QQ">
                <el-input v-model="profileForm.qq" placeholder="请输入 QQ 号" clearable />
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="profile-card section-card">
            <template #header>
              <div class="section-head">
                <div>
                  <span class="section-title">MC 玩家绑定</span>
                  <p class="section-subtitle">将账号与游戏内身份关联，用于统计与权限联动。</p>
                </div>
                <el-button link type="primary" @click="showBindDialog = true">
                  {{ mcInfo.name ? '更换绑定' : '绑定玩家' }}
                </el-button>
              </div>
            </template>

            <div v-if="mcInfo.name" class="mc-panel">
              <div class="mc-player-card">
                <div class="mc-player-card__avatar">
                  <img :src="mcAvatarUrl" class="mc-avatar" alt="MC Avatar" />
                </div>
                <div class="mc-player-card__info">
                  <div class="mc-player-card__name">{{ mcInfo.name }}</div>
                  <div class="mc-player-card__uuid">{{ mcInfo.uuid }}</div>
                </div>
                <el-button text type="primary" @click="showBindDialog = true">重新绑定</el-button>
              </div>
            </div>
            <div v-else class="inline-empty-state">
              <el-empty description="还没有绑定 MC 玩家" :image-size="72">
                <el-button type="primary" @click="showBindDialog = true">立即绑定</el-button>
              </el-empty>
            </div>
          </el-card>

          <el-card shadow="never" class="profile-card section-card stats-card">
            <template #header>
              <div class="section-head section-head--wrap">
                <div>
                  <span class="section-title">游戏统计</span>
                  <p class="section-subtitle">按时间范围查看你的关键数据表现。</p>
                </div>
                <el-select v-model="statsRange" size="default" class="stats-range" @change="fetchStats">
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

            <template v-else-if="stats && stats.totals && stats.totals.length > 0">
              <div class="stats-time-range">{{ stats.time_range?.label || rangeLabelMap[statsRange] }}</div>
              <div class="stats-grid">
                <div class="stat-item" v-for="item in stats.totals" :key="item.label">
                  <div class="stat-label">{{ item.label }}</div>
                  <div class="stat-value">{{ item.label_total }}</div>
                  <div
                    v-if="item.delta !== 0"
                    class="stat-delta"
                    :class="{ positive: item.delta > 0, negative: item.delta < 0 }"
                  >
                    {{ item.delta > 0 ? '+' : '' }}{{ item.label_delta }}
                  </div>
                  <div v-else class="stat-delta neutral">较上一周期无变化</div>
                </div>
              </div>
            </template>

            <div v-else class="inline-empty-state stats-empty">
              <el-empty
                :description="!mcInfo.name ? '绑定玩家后即可查看统计' : '当前范围内暂无统计数据'"
                :image-size="76"
              >
                <el-button v-if="!mcInfo.name" type="primary" @click="showBindDialog = true">去绑定玩家</el-button>
              </el-empty>
            </div>
          </el-card>
        </div>

        <div class="profile-side-column">
          <el-card shadow="never" class="profile-card side-card">
            <template #header>
              <div class="side-title-wrap">
                <span class="section-title">账号安全</span>
                <p class="section-subtitle">建议定期更新密码。</p>
              </div>
            </template>
            <div class="security-panel">
              <div class="security-row">
                <div>
                  <div class="security-row__title">登录密码</div>
                  <div class="security-row__desc">用于登录 ASPanel 管理后台</div>
                </div>
                <el-button @click="showPasswordDialog = true">修改密码</el-button>
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="profile-card side-card" v-if="serverGroups.length > 0">
            <template #header>
              <div class="side-title-wrap">
                <span class="section-title">可访问的服务器组</span>
                <p class="section-subtitle">你的账号当前拥有以下分组权限。</p>
              </div>
            </template>
            <div class="server-groups">
              <el-tag v-for="group in serverGroups" :key="group.id" class="group-tag" effect="plain">
                {{ group.name }}
              </el-tag>
            </div>
          </el-card>
        </div>
      </div>
    </div>

    <AvatarUploader v-model:visible="showAvatarDialog" @success="handleAvatarSuccess" />

    <el-dialog v-model="showPasswordDialog" title="修改密码" width="420px" @closed="resetPasswordForm">
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

    <el-dialog v-model="showBindDialog" title="绑定 MC 玩家" width="440px" @closed="resetBindForm">
      <template v-if="pendingBind">
        <div class="pending-bind-info">
          <el-alert type="info" :closable="false" show-icon>
            <template #title>
              <span>正在验证玩家：<strong>{{ pendingBind.player_name }}</strong></span>
            </template>
          </el-alert>
          <div class="verification-code-section">
            <div class="verification-label">请在游戏内输入以下命令</div>
            <div class="verification-command">
              <code class="command-text">!!bindcode {{ pendingBind.code }}</code>
              <el-button circle plain @click="copyBindCommand">
                <el-icon><CopyDocument /></el-icon>
              </el-button>
            </div>
            <div class="verification-expire">验证码将在 {{ formatExpireTime(pendingBind) }} 后过期</div>
          </div>
        </div>
      </template>
      <template v-else>
        <el-form :model="bindForm" :rules="bindRules" ref="bindFormRef" label-position="top">
          <el-form-item label="玩家名" prop="player_name">
            <el-input v-model="bindForm.player_name" placeholder="请输入 MC 玩家名" />
          </el-form-item>
          <div class="bind-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>请输入已在服务器中登录过的玩家名，提交后需在游戏内验证。</span>
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
import {
  UserFilled, Camera, InfoFilled, CopyDocument,
  Message, ChatDotRound, FolderOpened,
} from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'
import AvatarUploader from '@/components/AvatarUploader.vue'
import apiClient from '@/api'
import { bindApi } from '@/api/bind'

const userStore = useUserStore()
const user = userStore.user
const { fullAvatarUrl } = storeToRefs(userStore)
const { fetchUser, refreshAvatar } = userStore

const showAvatarDialog = ref(false)

const mcInfo = reactive({
  name: '',
  uuid: '',
})

const serverGroups = ref<{ id: number; name: string }[]>([])

const profileForm = reactive({
  email: '',
  qq: '',
})
const saving = ref(false)

const showPasswordDialog = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const changingPassword = ref(false)

const showBindDialog = ref(false)
const bindFormRef = ref<FormInstance>()
const bindForm = reactive({
  player_name: '',
})
const binding = ref(false)
const canceling = ref(false)

interface PendingBind {
  player_name: string
  code: string
  expires_at?: number
  expires_in_seconds?: number
}
const pendingBind = ref<PendingBind | null>(null)

const bindRules: FormRules = {
  player_name: [
    { required: true, message: '请输入玩家名', trigger: 'blur' },
    { min: 1, max: 16, message: '玩家名长度为1-16个字符', trigger: 'blur' },
  ],
}

const passwordRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' },
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
      trigger: 'blur',
    },
  ],
}

const statsRange = ref('1w')
const statsLoading = ref(false)
const stats = ref<any>(null)

const rangeLabelMap: Record<string, string> = {
  '1d': '今天',
  '1w': '本周',
  '1m': '本月',
  '1y': '今年',
  all: '全部',
}

const inferredRole = computed(() => {
  if (user.is_owner) return 'OWNER'
  if (user.is_admin) return 'ADMIN'
  const groupRoles = user.group_permissions.map((item) => item.role)
  if (groupRoles.includes('ADMIN')) return 'ADMIN'
  if (groupRoles.includes('HELPER')) return 'HELPER'
  if (groupRoles.includes('USER')) return 'USER'
  return 'GUEST'
})

const roleLabel = computed(() => {
  const labels: Record<string, string> = {
    GUEST: '访客',
    USER: '用户',
    HELPER: '助手',
    ADMIN: '管理员',
    OWNER: '所有者',
  }
  return labels[inferredRole.value] || inferredRole.value
})

const roleTagType = computed(() => {
  const types: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    GUEST: 'info',
    USER: '',
    HELPER: 'success',
    ADMIN: 'warning',
    OWNER: 'danger',
  }
  return types[inferredRole.value] || 'info'
})

const mcAvatarUrl = computed(() => {
  if (!mcInfo.uuid) return ''
  return `/api/users/mc/avatar/${mcInfo.uuid}`
})

onMounted(async () => {
  await loadUserInfo()
  await checkPendingBind()
  await fetchStats()
})

async function loadUserInfo() {
  try {
    const res = await apiClient.get('/api/users/me')
    const data = res.data

    mcInfo.name = data.mc_name || ''
    mcInfo.uuid = data.mc_uuid || ''

    profileForm.email = data.email || ''
    profileForm.qq = data.qq || ''

    if (data.server_link_group_ids && data.server_link_group_ids.length > 0) {
      await loadServerGroups(data.server_link_group_ids)
    }
  } catch {
    ElMessage.error('加载用户信息失败')
  }
}

async function loadServerGroups(ids: number[]) {
  try {
    const res = await apiClient.get('/api/server-groups')
    const allGroups = res.data || []
    serverGroups.value = allGroups.filter((g: any) => ids.includes(g.id))
  } catch {
    serverGroups.value = []
  }
}

async function fetchStats() {
  if (!mcInfo.uuid) {
    stats.value = null
    return
  }

  statsLoading.value = true
  try {
    const res = await apiClient.get('/api/users/me/stats', {
      params: { range: statsRange.value },
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
      qq: profileForm.qq || null,
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
      new_password: passwordForm.new_password,
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
    expiresMs = pending.expires_at * 1000
  } else if (pending.expires_in_seconds) {
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
  min-height: calc(100vh - var(--el-header-height) - 40px);
}

.profile-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.profile-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.7fr);
  gap: 20px;
  align-items: start;
}

.profile-main-column,
.profile-side-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.profile-card {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
}

.profile-card :deep(.el-card__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.10);
}

.profile-card :deep(.el-card__body) {
  padding: 22px 24px 24px;
}

.profile-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 28px;
  background:
    radial-gradient(circle at 10% 18%, rgba(119,181,254,0.15), transparent 26%),
    radial-gradient(circle at 92% 20%, rgba(239,183,186,0.18), transparent 24%),
    rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(22px);
  backdrop-filter: saturate(180%) blur(22px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 24px 60px rgba(119, 181, 254, 0.12), inset 0 1px 0 rgba(255,255,255,0.88);
}

:global(.dark) .profile-hero {
  background:
    radial-gradient(circle at 10% 18%, rgba(119,181,254,0.14), transparent 28%),
    radial-gradient(circle at 92% 20%, rgba(239,183,186,0.12), transparent 24%),
    rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.14);
  box-shadow: 0 24px 70px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.04);
}

.hero-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(38px);
  pointer-events: none;
}

.hero-orb--blue {
  width: 180px;
  height: 180px;
  right: -30px;
  top: -36px;
  background: rgba(119, 181, 254, 0.18);
}

.hero-orb--pink {
  width: 140px;
  height: 140px;
  left: 40%;
  bottom: -40px;
  background: rgba(239, 183, 186, 0.14);
}

.hero-main {
  position: relative;
  display: flex;
  align-items: center;
  gap: 24px;
  z-index: 1;
}

.avatar-hero {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 118px;
  height: 118px;
  border: none;
  border-radius: 32px;
  background: rgba(255,255,255,0.48);
  box-shadow: 0 10px 30px rgba(119,181,254,0.16);
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
  overflow: hidden;
  flex-shrink: 0;
}

.avatar-hero:hover {
  transform: translateY(-3px);
  box-shadow: 0 18px 36px rgba(119,181,254,0.24);
}

.avatar-hero__hint {
  position: absolute;
  inset: auto 10px 10px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: rgba(15, 23, 42, 0.62);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}

.hero-copy {
  flex: 1;
  min-width: 0;
}

.hero-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.hero-title {
  margin: 0;
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.hero-subtitle {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.role-pill {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 0 12px;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  color: var(--el-text-color-regular);
  background: rgba(255,255,255,0.48);
  border: 1px solid rgba(119,181,254,0.14);
}

:global(.dark) .meta-chip {
  background: rgba(15,23,42,0.44);
}

.hero-stats {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hero-stat {
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.44);
  border: 1px solid rgba(119,181,254,0.12);
}

:global(.dark) .hero-stat {
  background: rgba(15,23,42,0.42);
}

.hero-stat__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.hero-stat strong {
  font-size: 15px;
  color: var(--color-text);
}

.section-card {
  background: rgba(255,255,255,0.52);
}

:global(.dark) .section-card,
:global(.dark) .side-card {
  background: rgba(15, 23, 42, 0.60);
}

.section-head,
.side-title-wrap {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-head--wrap {
  flex-wrap: wrap;
}

.section-title {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

.section-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.two-col-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.two-col-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.mc-panel,
.security-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mc-player-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(119,181,254,0.10), rgba(239,183,186,0.08));
  border: 1px solid rgba(119,181,254,0.14);
}

.mc-player-card__avatar {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  border-radius: 18px;
  background: rgba(255,255,255,0.55);
}

.mc-avatar {
  width: 58px;
  height: 58px;
  border-radius: 12px;
  image-rendering: pixelated;
}

.mc-player-card__name {
  font-size: 17px;
  font-weight: 700;
}

.mc-player-card__uuid {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-family: ui-monospace, SFMono-Regular, monospace;
  word-break: break-all;
  font-size: 12px;
}

.inline-empty-state {
  padding: 8px 0;
}

.stats-range {
  width: 132px;
}

.stats-time-range {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 16px;
}

.stats-loading {
  padding: 12px 0 4px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
}

.stat-item {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(119,181,254,0.10), rgba(119,181,254,0.04));
  border: 1px solid rgba(119,181,254,0.14);
}

:global(.dark) .stat-item {
  background: linear-gradient(180deg, rgba(119,181,254,0.12), rgba(119,181,254,0.05));
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
}

.stat-value {
  font-size: 26px;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.stat-delta {
  margin-top: 10px;
  font-size: 12px;
  font-weight: 600;
}

.stat-delta.positive { color: var(--el-color-success); }
.stat-delta.negative { color: var(--el-color-danger); }
.stat-delta.neutral { color: var(--el-text-color-secondary); }

.server-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.group-tag {
  padding: 4px 12px;
}

.security-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(119,181,254,0.06);
  border: 1px solid rgba(119,181,254,0.12);
}

.security-row__title {
  font-size: 15px;
  font-weight: 700;
}

.security-row__desc {
  margin-top: 5px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.bind-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: -6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.pending-bind-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.verification-code-section {
  padding: 18px;
  text-align: center;
  border-radius: 16px;
  background: rgba(119,181,254,0.08);
  border: 1px solid rgba(119,181,254,0.14);
}

.verification-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
}

.verification-command {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.command-text {
  font-size: 18px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, monospace;
  color: var(--brand-primary);
  background: rgba(119,181,254,0.10);
  border: 1px solid rgba(119,181,254,0.16);
  padding: 10px 14px;
  border-radius: 12px;
  user-select: all;
}

.verification-expire {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 1100px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }

  .profile-side-column {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
  }
}

@media (max-width: 820px) {
  .profile-shell {
    gap: 16px;
  }

  .profile-hero {
    padding: 22px;
  }

  .hero-main {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-title-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-stats,
  .two-col-form,
  .profile-side-column {
    grid-template-columns: 1fr;
  }

  .mc-player-card,
  .security-row {
    grid-template-columns: 1fr;
    justify-items: start;
  }
}

@media (max-width: 560px) {
  .profile-card :deep(.el-card__header),
  .profile-card :deep(.el-card__body) {
    padding-left: 18px;
    padding-right: 18px;
  }

  .profile-hero {
    border-radius: 20px;
    padding: 18px;
  }

  .avatar-hero {
    width: 98px;
    height: 98px;
    border-radius: 26px;
  }

  .hero-meta {
    gap: 8px;
  }

  .meta-chip {
    width: 100%;
    justify-content: flex-start;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stats-range {
    width: 100%;
  }
}
</style>
