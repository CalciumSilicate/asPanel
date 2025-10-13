<template>
  <div>
    <!-- 移除容器外多余的“直接编辑配置”按钮，避免重复显示 -->

    <el-card v-if="!naked" shadow="never" class="config-card">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-base font-medium">{{ serverName || '配置' }}</span>
          <div class="flex items-center gap-2">
            <el-tag size="small" type="info">文件格式：{{ fmt.toUpperCase() }}</el-tag>
            <el-button v-if="showRawButton" type="primary" size="small" @click="handleRawClick" :disabled="!serverId">直接编辑配置</el-button>
          </div>
        </div>
      </template>

      <el-form label-position="left" label-width="320px" :model="dummy" class="cfg-form">
        <template v-for="f in fields" :key="f.path">
          <el-form-item>
            <template #label>
              <div class="form-item-label"><span>{{ f.label || f.path }}</span><small>{{ f.path }}</small></div>
            </template>
            <component :is="resolveComp(f)"
                       :model-value="getVal(f.path)"
                       @update:model-value="v => setVal(f.path, v)"
                       :options="f.type==='role_level' ? roleOptions : (f.path==='serverList' ? serverNameOptions : [])"
                       />
          </el-form-item>
        </template>
      </el-form>
    </el-card>

    <div v-else class="config-container">
      <el-form label-position="left" label-width="320px" :model="dummy" class="cfg-form">
        <template v-for="f in fields" :key="f.path">
          <el-form-item>
            <template #label>
              <div class="form-item-label"><span>{{ f.label || f.path }}</span><small>{{ f.path }}</small></div>
            </template>
            <component :is="resolveComp(f)"
                       :model-value="getVal(f.path)"
                       @update:model-value="v => setVal(f.path, v)"
                       :options="f.type==='role_level' ? roleOptions : (f.path==='serverList' ? serverNameOptions : [])"
                       />
          </el-form-item>
        </template>
      </el-form>
    </div>

    <ConfigEditor
      v-if="showRawButton && !useExternalRaw"
      v-model:visible="raw.visible"
      :loading="raw.loading"
      :is-saving="raw.saving"
      :title="`编辑配置 (${fmt.toUpperCase()})`"
      :initial-content="raw.content"
      :language="editorLanguage"
      @save="saveRaw"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, h, defineComponent, resolveComponent } from 'vue'
import ConfigEditor from '@/components/ConfigEditor.vue'
import apiClient from '@/api'

const props = defineProps({
  pluginKey: { type: String, required: true },
  serverId: { type: Number, required: true },
  showRawButton: { type: Boolean, default: true },
  naked: { type: Boolean, default: false },
  serverName: { type: String, default: '' },
  useExternalRaw: { type: Boolean, default: false }
})

const cfg = ref({}) // 完整配置对象
const fmt = ref('json')
const fields = ref([]) // 后端提供的 ui_fields
const pending = ref({})
let timer = null

const roleOptions = [
  { label: 'GUEST(0)', value: 0 },
  { label: 'USER(1)', value: 1 },
  { label: 'HELPER(2)', value: 2 },
  { label: 'ADMIN(3)', value: 3 },
  { label: 'OWNER(4)', value: 4 },
]

const serverNameOptions = ref([])

const getVal = (path) => {
  const parts = path.split('.')
  let cur = cfg.value
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = cur[p]
  }
  return cur
}
const setVal = (path, value) => {
  // 深设值
  const parts = path.split('.')
  let cur = cfg.value
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i]
    if (!(p in cur) || typeof cur[p] !== 'object') cur[p] = {}
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = value
  // 记录待提交
  pending.value[path] = value
  scheduleSubmit()
}

const scheduleSubmit = () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(submitChanges, 500)
}

const submitChanges = async () => {
  if (!props.serverId || !Object.keys(pending.value).length) return
  const payload = { updates: rebuildNested(pending.value) }
  try {
    await apiClient.patch(`/api/configs/${props.pluginKey}/${props.serverId}`, payload)
  } catch (e) {
    console.error(e)
  } finally {
    pending.value = {}
  }
}

// 将扁平 path->value 还原为嵌套对象
const rebuildNested = (flat) => {
  const out = {}
  for (const [path, val] of Object.entries(flat)) {
    const parts = path.split('.')
    let cur = out
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i]
      if (!(p in cur) || typeof cur[p] !== 'object') cur[p] = {}
      cur = cur[p]
    }
    cur[parts[parts.length - 1]] = val
  }
  return out
}

const dummy = ref({}) // el-form 需要 model

// 动态字段组件解析
const resolveComp = (f) => {
  if (f.type === 'bool') return BoolInput
  if (f.type === 'int' || f.type === 'number') return NumberInput
  if (f.type === 'role_level') return RoleLevelInput
  if (f.type === 'string') return StringInput
  if (f.type === 'date') return DateInput
  if (f.type === 'string_array') return StringArrayInput
  return StringInput
}

const editorLanguage = computed(() => {
  if (fmt.value === 'yaml') return 'yaml'
  if (fmt.value === 'toml') return 'toml'
  return 'text'
})

const raw = reactive({ visible: false, loading: false, saving: false, content: '' })
const openRawEditor = async () => {
  if (props.useExternalRaw) { emit('open-raw'); return }
  raw.visible = true
  raw.loading = true
  try {
    const { data } = await apiClient.get(`/api/configs/${props.pluginKey}/${props.serverId}/raw`, { transformResponse: [(d)=>d] })
    raw.content = data
  } catch (e) {
    raw.content = ''
  } finally { raw.loading = false }
}
const handleRawClick = () => openRawEditor()
const saveRaw = async (content) => {
  raw.saving = true
  try {
    await apiClient.post(`/api/configs/${props.pluginKey}/${props.serverId}/raw`, { content })
  } catch (e) {
    // ignore
  } finally { raw.saving = false; raw.visible = false; await load() }
}

const load = async () => {
  if (!props.serverId) return
  try {
    const { data } = await apiClient.get(`/api/configs/${props.pluginKey}/${props.serverId}`)
    cfg.value = data.config || {}
    fields.value = data.ui_fields || []
    fmt.value = data.format || 'json'
  } catch (e) {
    cfg.value = {}
    fields.value = []
  }
}

watch(() => props.serverId, () => load())

onMounted(async () => {
  // 准备服务器名选项（用于 joinMOTD.serverList 便捷添加）
  try {
    const { data } = await apiClient.get('/api/servers')
    serverNameOptions.value = (data || []).map(s => ({ label: s.name, value: s.name }))
  } catch {}
  await load()
})

// 内部输入子组件
const BoolInput = defineComponent({
  name: 'BoolInput',
  props: { modelValue: { type: [Boolean, Number, String], default: false } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElSwitch'),
      {
        modelValue: props.modelValue,
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      }
    )
  }
})
const NumberInput = defineComponent({
  name: 'NumberInput',
  props: { modelValue: { type: [Number, String], default: 0 } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElInputNumber'),
      {
        modelValue: props.modelValue,
        min: 0,
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      }
    )
  }
})
const StringInput = defineComponent({
  name: 'StringInput',
  props: { modelValue: { type: [String, Number, null], default: '' } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElInput'),
      {
        modelValue: props.modelValue,
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      }
    )
  }
})
const DateInput = defineComponent({
  name: 'DateInput',
  props: { modelValue: { type: [String, Date, null], default: null } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElDatePicker'),
      {
        type: 'date',
        valueFormat: 'YYYY-MM-DD',
        modelValue: props.modelValue,
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      }
    )
  }
})
const StringArrayInput = defineComponent({
  name: 'StringArrayInput',
  props: { modelValue: { type: Array, default: () => [] }, options: { type: Array, default: () => [] } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElSelect'),
      {
        multiple: true,
        filterable: true,
        allowCreate: true,
        defaultFirstOption: true,
        modelValue: props.modelValue || [],
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      },
      () => (props.options || []).map(opt => h(
        resolveComponent('ElOption'),
        { key: opt.value, label: opt.label, value: opt.value }
      ))
    )
  }
})
const RoleLevelInput = defineComponent({
  name: 'RoleLevelInput',
  props: { modelValue: { type: [Number, String], default: null }, options: { type: Array, default: () => [] } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h(
      resolveComponent('ElSelect'),
      {
        modelValue: props.modelValue,
        placeholder: '选择权限',
        'onUpdate:modelValue': (val) => emit('update:modelValue', val)
      },
      () => (props.options || []).map(opt => h(
        resolveComponent('ElOption'),
        { key: opt.value, label: opt.label, value: opt.value }
      ))
    )
  }
})
</script>

<style scoped>
.mb-2 { margin-bottom: 8px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 600; }
.gap-2 { gap: 8px; }
.config-container { padding: 0; }
.cfg-form :deep(.el-form-item) { margin-bottom: 12px; padding-bottom: 8px; display: flex; flex-wrap: wrap; }

.form-item-label { display: flex; flex-direction: column; align-items: flex-start; justify-content: center; padding-left: 3%; padding-right: 20px; white-space: normal; }
.form-item-label > span { font-size: 14px; color: var(--el-text-color-regular); line-height: 1.4; }
.form-item-label > small { margin-left: 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.3; }
</style>
