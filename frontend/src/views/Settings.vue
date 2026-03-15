<template>
  <div class="settings-page">
    <section class="settings-hero settings-shell-card">
      <div class="hero-copy">
        <span class="hero-kicker">ASPanel / 系统设置</span>
        <h1>全局配置中心</h1>
        <p>统一管理运行环境、注册策略与时间显示。修改后会自动保存到面板配置。</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <span class="metric-label">保存状态</span>
          <strong>{{ saving ? '正在保存…' : '自动保存已开启' }}</strong>
        </div>
        <div class="metric-card">
          <span class="metric-label">最近保存</span>
          <strong>{{ savedAt || '尚未保存' }}</strong>
        </div>
        <div class="metric-card">
          <span class="metric-label">当前时区</span>
          <strong>{{ currentTimezoneLabel }}</strong>
        </div>
      </div>
    </section>

    <div class="settings-layout">
      <aside class="settings-overview settings-shell-card">
        <div class="overview-head">
          <span class="panel-title">配置概览</span>
          <span class="save-chip" :class="{ 'is-saving': saving }">
            <span class="save-dot" />
            {{ saving ? '保存中' : '已同步' }}
          </span>
        </div>

        <div class="overview-list">
          <div class="overview-item">
            <span class="overview-item__label">Python 路径</span>
            <strong>{{ form.python_executable || '未设置' }}</strong>
          </div>
          <div class="overview-item">
            <span class="overview-item__label">Java 命令</span>
            <strong>{{ form.java_command || 'java' }}</strong>
          </div>
          <div class="overview-item">
            <span class="overview-item__label">注册入口</span>
            <strong>{{ form.allow_register ? '已开放' : '已关闭' }}</strong>
          </div>
          <div class="overview-item">
            <span class="overview-item__label">默认角色</span>
            <strong>{{ currentRoleLabel }}</strong>
          </div>
          <div class="overview-item">
            <span class="overview-item__label">Token 有效期</span>
            <strong>{{ tokenExpireLabel }}</strong>
          </div>
          <div class="overview-item">
            <span class="overview-item__label">复制限速</span>
            <strong>{{ form.copy_limit_mbps }} MB/s</strong>
          </div>
        </div>
      </aside>

      <div class="settings-main">
        <el-card shadow="never" class="settings-card section-card">
          <template #header>
            <div class="section-head">
              <div>
                <span class="panel-title">服务器运行环境</span>
                <p class="panel-subtitle">定义面板默认使用的 Python / Java 运行时与文件复制策略。</p>
              </div>
            </div>
          </template>

          <el-form label-position="top" :model="form" class="settings-form two-col-grid">
            <el-form-item class="full-span">
              <template #label>
                <div class="field-label">
                  <span>服务器 Python 路径</span>
                  <small>建议将虚拟环境放在服务器目录 .venv；相对路径以服务器目录为基准。</small>
                </div>
              </template>
              <el-input v-model="form.python_executable" placeholder="例如：.venv/bin/python 或 /usr/bin/python3" />
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>服务器 Java 命令</span>
                  <small>保存后，服务器配置中的 start_command 将使用该 Java 命令。</small>
                </div>
              </template>
              <el-select
                v-model="form.java_command"
                filterable
                allow-create
                default-first-option
                clearable
                placeholder="例如：java 或 /usr/bin/java"
              >
                <el-option v-for="cmd in javaOptions" :key="cmd" :label="cmd" :value="cmd" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>文件复制速度限制</span>
                  <small>限制备份、存档等操作的文件复制速度（MB/s）。</small>
                </div>
              </template>
              <div class="inline-field">
                <el-input-number v-model="form.copy_limit_mbps" :min="1" :max="10240" :step="128" />
                <span class="unit-chip">MB/s</span>
              </div>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never" class="settings-card section-card">
          <template #header>
            <div class="section-head">
              <div>
                <span class="panel-title">用户与安全</span>
                <p class="panel-subtitle">控制新用户注册、默认权限以及登录凭证有效时间。</p>
              </div>
            </div>
          </template>

          <el-form label-position="top" :model="form" class="settings-form two-col-grid">
            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>允许新用户注册</span>
                  <small>关闭后，新用户将无法通过注册页面创建账号。</small>
                </div>
              </template>
              <div class="switch-card" :class="{ active: form.allow_register }">
                <div>
                  <strong>{{ form.allow_register ? '开放注册' : '关闭注册' }}</strong>
                  <p>{{ form.allow_register ? '新用户可以直接注册登录。' : '仅现有管理员可创建账号。' }}</p>
                </div>
                <el-switch v-model="form.allow_register" />
              </div>
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>注册时 QQ 为必填</span>
                  <small>关闭后，注册时 QQ 可留空；若填写，仍需为纯数字。</small>
                </div>
              </template>
              <div class="switch-card" :class="{ active: form.register_require_qq }">
                <div>
                  <strong>{{ form.register_require_qq ? '需要填写 QQ' : 'QQ 可选填' }}</strong>
                  <p>适用于需要额外身份信息的社群环境。</p>
                </div>
                <el-switch v-model="form.register_require_qq" />
              </div>
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>新用户默认角色</span>
                  <small>新注册用户的默认权限角色。</small>
                </div>
              </template>
              <el-select v-model="form.default_user_role">
                <el-option v-for="role in userRoles" :key="role.value" :label="role.label" :value="role.value" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>Token 有效期</span>
                  <small>登录凭证过期后需要重新登录。</small>
                </div>
              </template>
              <el-select v-model="form.token_expire_minutes">
                <el-option label="1 天" :value="1440" />
                <el-option label="3 天" :value="4320" />
                <el-option label="7 天" :value="10080" />
                <el-option label="14 天" :value="20160" />
                <el-option label="30 天" :value="43200" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never" class="settings-card section-card">
          <template #header>
            <div class="section-head">
              <div>
                <span class="panel-title">显示与统计</span>
                <p class="panel-subtitle">配置时间显示偏好，以及统计系统需要忽略的服务器。</p>
              </div>
            </div>
          </template>

          <el-form label-position="top" :model="form" class="settings-form two-col-grid">
            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>时间时区</span>
                  <small>用于聊天室、存档管理、Prime Backup 等前端时间显示。</small>
                </div>
              </template>
              <el-select v-model="form.timezone" filterable>
                <el-option v-for="tz in tzOptions" :key="tz.value" :label="tz.label" :value="tz.value" />
              </el-select>
            </el-form-item>

            <el-form-item>
              <template #label>
                <div class="field-label">
                  <span>统计忽略的服务器 ID</span>
                  <small>以英文逗号分隔，例如：1,2,3。入库时将跳过这些服务器。</small>
                </div>
              </template>
              <el-input v-model="form.stats_ignore_server_text" placeholder="例如：1,2,3" clearable />
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted, ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import apiClient from '@/api'
import { useSettingsStore, COMMON_TIMEZONES, USER_ROLES } from '@/store/settings'

const settingsStore = useSettingsStore()
const settings = settingsStore.settings
const { loadSettings, updateSettings } = settingsStore

const form = reactive({
  python_executable: settings.python_executable,
  java_command: settings.java_command,
  timezone: settings.timezone,
  stats_ignore_server_text: '',
  token_expire_minutes: settings.token_expire_minutes,
  allow_register: settings.allow_register,
  register_require_qq: settings.register_require_qq,
  default_user_role: settings.default_user_role,
  copy_limit_mbps: settings.copy_limit_mbps,
})

const tzOptions = COMMON_TIMEZONES
const userRoles = USER_ROLES
const saving = ref(false)
const savedAt = ref('')
const javaOptions = ref([])

const currentTimezoneLabel = computed(() => {
  const hit = tzOptions.find((item) => item.value === form.timezone)
  return hit?.label || form.timezone || '未设置'
})

const currentRoleLabel = computed(() => {
  const hit = userRoles.find((item) => item.value === form.default_user_role)
  return hit?.label || form.default_user_role || '未设置'
})

const tokenExpireLabel = computed(() => {
  const map = {
    1440: '1 天',
    4320: '3 天',
    10080: '7 天',
    20160: '14 天',
    43200: '30 天',
  }
  return map[form.token_expire_minutes] || `${form.token_expire_minutes} 分钟`
})

let timer = null
const autoSave = () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(async () => {
    try {
      saving.value = true
      await updateSettings({
        python_executable: form.python_executable,
        java_command: form.java_command,
        timezone: form.timezone,
        stats_ignore_server: (form.stats_ignore_server_text || '')
          .split(',')
          .map((s) => s.trim())
          .filter((s) => s.length > 0)
          .map((s) => parseInt(s, 10))
          .filter((n) => !Number.isNaN(n)),
        token_expire_minutes: form.token_expire_minutes,
        allow_register: form.allow_register,
        register_require_qq: form.register_require_qq,
        default_user_role: form.default_user_role,
        copy_limit_mbps: form.copy_limit_mbps,
      })
      const d = new Date()
      savedAt.value = d.toLocaleTimeString('zh-CN')
    } catch (e) {
      ElMessage.error(e?.response?.data?.detail || '自动保存失败')
    } finally {
      saving.value = false
    }
  }, 650)
}

onMounted(async () => {
  await loadSettings()
  Object.assign(form, settings)
  try {
    const { data } = await apiClient.get('/api/settings/java-options')
    javaOptions.value = Array.isArray(data) ? data : []
  } catch {
    javaOptions.value = []
  }
  try {
    const arr = Array.isArray(settings.stats_ignore_server) ? settings.stats_ignore_server : []
    form.stats_ignore_server_text = arr.join(',')
  } catch {
    form.stats_ignore_server_text = ''
  }
})

watch(() => ({ ...form }), autoSave, { deep: true })
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.settings-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-shell-card {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  background: rgba(255,255,255,0.58);
  -webkit-backdrop-filter: saturate(180%) blur(22px);
  backdrop-filter: saturate(180%) blur(22px);
  border: 1px solid rgba(119,181,254,0.18);
  box-shadow: 0 20px 56px rgba(119,181,254,0.10), inset 0 1px 0 rgba(255,255,255,0.88);
}

:global(.dark) .settings-shell-card,
:global(.dark) .section-card {
  background: rgba(15,23,42,0.64);
  border-color: rgba(119,181,254,0.14);
  box-shadow: 0 20px 60px rgba(0,0,0,0.34), inset 0 1px 0 rgba(255,255,255,0.04);
}

.settings-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  padding: 28px;
  background:
    radial-gradient(circle at 10% 18%, rgba(119,181,254,0.14), transparent 26%),
    radial-gradient(circle at 88% 24%, rgba(239,183,186,0.16), transparent 22%),
    rgba(255,255,255,0.60);
}

.hero-kicker {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-primary);
  font-weight: 700;
}

.settings-hero h1 {
  margin: 0;
  font-size: clamp(28px, 3vw, 36px);
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.settings-hero p {
  margin: 10px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  max-width: 680px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-width: min(100%, 420px);
}

.metric-card {
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.46);
  border: 1px solid rgba(119,181,254,0.12);
}

:global(.dark) .metric-card {
  background: rgba(15,23,42,0.46);
}

.metric-label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.metric-card strong {
  font-size: 15px;
  color: var(--color-text);
}

.settings-overview {
  padding: 20px;
}

.overview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-title {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

.panel-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.save-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--brand-primary);
  background: rgba(119,181,254,0.10);
  border: 1px solid rgba(119,181,254,0.16);
}

.save-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 4px rgba(119,181,254,0.12);
}

.is-saving .save-dot {
  animation: pulse 1.2s ease-in-out infinite;
}

.overview-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-item {
  padding: 14px 14px 15px;
  border-radius: 16px;
  background: rgba(119,181,254,0.06);
  border: 1px solid rgba(119,181,254,0.10);
}

.overview-item__label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.overview-item strong {
  display: block;
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}

.settings-card {
  border-radius: 22px;
}

.settings-card :deep(.el-card__header) {
  padding: 22px 24px 14px;
  border-bottom: 1px solid rgba(119,181,254,0.10);
}

.settings-card :deep(.el-card__body) {
  padding: 22px 24px 24px;
}

.two-col-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 18px;
}

.two-col-grid :deep(.el-form-item) {
  margin-bottom: 18px;
}

.full-span {
  grid-column: 1 / -1;
}

.field-label {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.field-label span {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.field-label small {
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  font-size: 12px;
}

.inline-field {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.unit-chip {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(119,181,254,0.14);
  background: rgba(119,181,254,0.08);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 700;
}

.switch-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(119,181,254,0.12);
  background: rgba(119,181,254,0.05);
  min-height: 88px;
}

.switch-card.active {
  background: linear-gradient(135deg, rgba(119,181,254,0.10), rgba(167,139,250,0.08));
  border-color: rgba(119,181,254,0.18);
}

.switch-card strong {
  display: block;
  font-size: 15px;
  color: var(--color-text);
}

.switch-card p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.65; transform: scale(0.9); }
}

@media (max-width: 1120px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }

  .settings-overview {
    order: 2;
  }
}

@media (max-width: 860px) {
  .settings-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-metrics,
  .two-col-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .settings-page {
    gap: 16px;
  }

  .settings-hero {
    padding: 20px;
  }

  .settings-card :deep(.el-card__header),
  .settings-card :deep(.el-card__body) {
    padding-left: 18px;
    padding-right: 18px;
  }

  .switch-card {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
