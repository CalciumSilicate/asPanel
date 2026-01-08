<template>
  <div class="pb-page">
    <div class="left-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
      <div class="right-panel">
        <div class="center-wrap">
          <el-card shadow="never" class="settings-card">
            <template #header>
              <div class="flex items-center justify-between">
                <span>系统设置</span>
                <span class="muted" v-if="savedAt">已自动保存 {{ savedAt }}</span>
              </div>
            </template>

            <el-form label-position="left" label-width="320px" :model="form" class="cfg-form">
              <el-divider content-position="left">服务器配置</el-divider>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>服务器 Python 路径</span>
                    <small>建议将虚拟环境放在服务器目录 .venv；相对路径以服务器目录为基准。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-input v-model="form.python_executable" placeholder="例如：.venv/bin/python 或 /usr/bin/python3" />
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>服务器 Java 命令</span>
                    <small>保存后，服务器配置中的 start_command 将使用该 Java 命令。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-select
                    v-model="form.java_command"
                    filterable
                    allow-create
                    default-first-option
                    clearable
                    style="width: 360px;"
                    placeholder="例如：java 或 /usr/bin/java"
                  >
                    <el-option v-for="cmd in javaOptions" :key="cmd" :label="cmd" :value="cmd" />
                  </el-select>
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>文件复制速度限制</span>
                    <small>限制备份、存档等操作的文件复制速度（MB/s）。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-input-number v-model="form.copy_limit_mbps" :min="1" :max="10240" :step="128" style="width: 180px;" />
                  <span style="margin-left: 8px;">MB/s</span>
                </div>
              </el-form-item>

              <el-divider content-position="left">用户与安全</el-divider>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>允许新用户注册</span>
                    <small>关闭后，新用户将无法通过注册页面创建账号。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-switch v-model="form.allow_register" />
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>注册时 QQ 为必填</span>
                    <small>关闭后，注册时 QQ 可留空；若填写，仍需为纯数字。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-switch v-model="form.register_require_qq" />
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>注册时QQ为必填</span>
                    <small>关闭后，注册时QQ可不填。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-switch v-model="form.register_require_qq" />
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>新用户默认角色</span>
                    <small>新注册用户的默认权限角色。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-select v-model="form.default_user_role" style="width: 200px;">
                    <el-option v-for="role in userRoles" :key="role.value" :label="role.label" :value="role.value" />
                  </el-select>
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>Token 有效期</span>
                    <small>登录凭证的有效时间，过期后需要重新登录。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-select v-model="form.token_expire_minutes" style="width: 200px;">
                    <el-option label="1 天" :value="1440" />
                    <el-option label="3 天" :value="4320" />
                    <el-option label="7 天" :value="10080" />
                    <el-option label="14 天" :value="20160" />
                    <el-option label="30 天" :value="43200" />
                  </el-select>
                </div>
              </el-form-item>

              <el-divider content-position="left">显示与统计</el-divider>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>时间时区</span>
                    <small>用于前端显示时间（聊天室、存档管理、Prime Backup 等）。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-select v-model="form.timezone" filterable style="width: 280px;">
                    <el-option v-for="tz in tzOptions" :key="tz.value" :label="tz.label" :value="tz.value" />
                  </el-select>
                </div>
              </el-form-item>

              <el-form-item>
                <template #label>
                  <div class="form-item-label">
                    <span>统计忽略的服务器ID</span>
                    <small>以英文逗号分隔，例如：1,2,3。入库时跳过这些服务器。</small>
                  </div>
                </template>
                <div class="form-item-control">
                  <el-input v-model="form.stats_ignore_server_text" placeholder="例如：1,2,3" style="width: 280px;" />
                </div>
              </el-form-item>
            </el-form>
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import apiClient from '@/api'
import { settings, loadSettings, updateSettings, COMMON_TIMEZONES, USER_ROLES } from '@/store/settings'
import { asideCollapsed, asideCollapsing } from '@/store/ui'

const form = reactive({
  python_executable: settings.python_executable,
  java_command: settings.java_command,
  timezone: settings.timezone,
  stats_ignore_server_text: '',
  // 新增
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
          .map(s => s.trim())
          .filter(s => s.length > 0)
          .map(s => parseInt(s, 10))
          .filter(n => !Number.isNaN(n)),
        // 新增
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
  }, 600)
}

onMounted(async () => {
  await loadSettings()
  Object.assign(form, settings)
  try {
    const { data } = await apiClient.get('/api/settings/java-options')
    javaOptions.value = Array.isArray(data) ? data : []
  } catch (e) { /* no-op */ }
  try {
    const arr = Array.isArray(settings.stats_ignore_server) ? settings.stats_ignore_server : []
    form.stats_ignore_server_text = arr.join(',')
  } catch (e) { /* no-op */ }
})

watch(() => ({...form}), autoSave, { deep: true })
</script>

<style scoped>
.pb-page { }
.left-wrap { display: flex; gap: 16px; align-items: stretch; height: calc(100vh - var(--el-header-height) - 48px); overflow: hidden; min-height: 0; }
.left-panel { width: 320px; flex-shrink: 0; align-self: flex-start; }
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }
.right-panel { flex: 1 1 auto; min-height: 0; overflow: auto; }
.center-wrap { max-width: 820px; margin: 0 auto; padding: 12px 0; }
.settings-card { }
.muted { color: #909399; font-size: 12px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.help { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 6px; }
/* 参考 PrimeBackupConfig 的表单布局样式 */
.cfg-form :deep(.el-form-item) { margin-bottom: 18px; padding-bottom: 10px; display: flex; flex-wrap: wrap; }
.form-item-label { display: flex; flex-direction: column; align-items: flex-start; justify-content: center; padding-left: 3%; padding-right: 12px; white-space: normal; }
.form-item-label > span { font-size: 14px; color: var(--el-text-color-regular); line-height: 1.3; }
.form-item-label > small { margin-top: 2px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.2; }
.form-item-control { display: inline-flex; align-items: center; }
.cfg-form :deep(.el-divider) { margin: 24px 0 16px 0; }
.cfg-form :deep(.el-divider__text) { font-size: 14px; font-weight: 500; color: var(--el-text-color-primary); }
</style>
