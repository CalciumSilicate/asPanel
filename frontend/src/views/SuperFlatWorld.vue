<template>
  <div class="superflat-page">
    <div class="left-wrap">
    <div class="table-card left-panel">
      <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-base font-medium">超平坦世界生成器</span>
          </div>
          <div class="flex items-center gap-2">
            <el-button-group>
              <el-button type="primary" :disabled="!canSubmit" @click="handleGenerateDownload">
                生成并下载 level.dat
              </el-button>
              <el-button type="success" :disabled="!canSubmit" @click="openApplyDialog"  v-if="hasRole('ADMIN')">
                应用到服务器
              </el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <el-form label-width="0" label-position="top" :model="form">
        <el-form-item>
          <div class="form-item-wrapper">
            <div class="form-item-label"><span>游戏版本</span><small>Minecraft Version</small></div>
            <div class="form-item-control">
              <div class="version-row">
                <el-select v-model="form.versionName" placeholder="从 Mojang API 加载版本..." filterable clearable :loading="isFetchingVersions">
                  <el-option v-for="v in sortedFilteredVersions" :key="v.id" :label="v.id" :value="v.id" />
                </el-select>
                <div class="version-checkboxes">
                  <el-checkbox v-model="showSnapshots" size="small">显示快照版</el-checkbox>
                  <el-checkbox v-model="showExperiments" size="small">显示实验版</el-checkbox>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <div class="form-item-wrapper">
            <div class="form-item-label"><span>种子</span><small>Seed</small></div>
            <div class="form-item-control">
              <el-input v-model="form.seed" placeholder="数字或任意字符串">
                <template #append>
                  <el-button @click="randomizeSeed">随机</el-button>
                </template>
              </el-input>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <div class="form-item-wrapper">
            <div class="form-item-label"><span>结构</span><small>Structure Overrides</small><small class="tip-muted">可直接输入自定义结构名并回车添加</small></div>
            <div class="form-item-control">
              <el-select v-model="form.structureOverrides" multiple filterable allow-create default-first-option placeholder="选择或输入结构（可多选）">
                <el-option v-for="s in structureOptions" :key="s" :label="s" :value="s" />
              </el-select>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <div class="form-item-wrapper">
            <div class="form-item-label"><span>群系</span><small>Biomes</small><small class="tip-muted">可直接输入自定义群系名并回车添加</small></div>
            <div class="form-item-control">
              <el-select v-model="form.biomes" multiple filterable allow-create default-first-option placeholder="选择或输入群系（可多选）">
                <el-option v-for="b in biomeOptions" :key="b" :label="b" :value="b" />
              </el-select>
            </div>
          </div>
        </el-form-item>

        <el-divider>layers（从底层到高层）</el-divider>


        <draggable v-model="form.layers" item-key="_id" handle=".drag-handle">
          <template #item="{ element, index }">
            <div class="layer-row">
              <el-icon class="drag-handle"><Rank/></el-icon>
              <el-input v-model="element.block" class="block-input" placeholder="minecraft:bedrock" />
              <el-input-number v-model="element.height" :min="1" :max="512" />
              <el-button type="danger" :icon="Delete" @click="removeLayer(index)" circle/>
            </div>
          </template>
        </draggable>

        <div class="mt-2">
          <el-button type="primary" :icon="Plus" @click="addLayer">添加</el-button>
          <el-button :icon="Refresh" @click="resetDefaultLayers">恢复默认</el-button>
        </div>
      </el-form>
    </el-card>

    </div>
  </div>

  <!-- 应用到服务器（前端占位，调用后端API待接入；脱离局部容器，附着到 body） -->
  <el-dialog v-model="applyDialogVisible" title="应用到服务器" width="520px" align-center :teleported="true" append-to-body>
    <el-form label-width="140px">
      <el-form-item label="选择服务器">
        <el-select v-model="apply.serverId" filterable placeholder="请选择服务器" :loading="isFetchingServers">
          <el-option
              v-for="s in servers"
              :key="s.id"
              :label="s.name"
              :value="s.id"
              :disabled="s.status === 'running'"
          >
            <div class="option-row">
              <span>{{ s.name }}</span>
              <el-tag v-if="s.status === 'running'" size="small" type="success">运行中</el-tag>
            </div>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="覆盖已有存档">
        <el-switch v-model="apply.forceOverwrite" />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="applyDialogVisible=false">取消</el-button>
        <el-button type="primary" :disabled="!canSubmit || !apply.serverId" @click="handleApplyToServer">确认应用</el-button>
      </span>
    </template>
  </el-dialog>
  </div>
  
</template>
<script setup>
// 前端页面：表单与占位调用后端 API（下载与应用暂未实现）
import {ref, computed, onMounted, watch} from 'vue'
import {ElMessage, ElMessageBox, ElNotification} from 'element-plus'
import draggable from 'vuedraggable'
import { Plus, Refresh, Delete, Rank } from '@element-plus/icons-vue'
import apiClient, { isRequestCanceled } from '@/api'
import { hasRole, activeGroupIds, activeGroupId, user, isPlatformAdmin } from '@/store/user';

// 表单状态
const form = ref({
  versionName: '',
  seed: '',
  biomes: ['minecraft:plains'],
  structureOverrides: ['minecraft:village'],
  layers: [
    {_id: 1, block: 'minecraft:bedrock', height: 1},
    {_id: 2, block: 'minecraft:dirt', height: 2},
    {_id: 3, block: 'minecraft:grass_block', height: 1}
  ]
})

// 提交由后端判定高度等细节
const canSubmit = computed(()=> form.value.layers.length>0 && form.value.layers.every(l=> l.block && l.height>=1) && !!form.value.versionName)

let nextId = 4
const addLayer = () => {
  form.value.layers.push({_id: nextId++, block: 'minecraft:air', height: 1})
}
const removeLayer = (idx) => {
  form.value.layers.splice(idx,1)
}
const resetDefaultLayers = () => {
  form.value.layers = [
    {_id: nextId++, block: 'minecraft:bedrock', height: 1},
    {_id: nextId++, block: 'minecraft:dirt', height: 2},
    {_id: nextId++, block: 'minecraft:grass_block', height: 1}
  ]
}

const randomizeSeed = () => {
  form.value.seed = String(Math.floor(Math.random()*2**31))
}

// --- 后端交互占位 ---
const mojangVersions = ref([])
const isFetchingVersions = ref(false)
const showSnapshots = ref(false)
const showExperiments = ref(false)
const sortedFilteredVersions = computed(()=>{
  const list = mojangVersions.value.filter(v=>{
    if (v.type === 'release') return true
    if (showSnapshots.value && v.type === 'snapshot') return true
    if (showExperiments.value && (v.type === 'old_beta' || v.type === 'old_alpha' || v.type === 'beta' || v.type === 'alpha')) return true
    return false
  })
  // 按发行时间倒序，后端字段可能为 releaseTime 或 release_time
  return list.slice().sort((a,b)=>{
    const ta = new Date(a.releaseTime || a.release_time || 0).getTime()
    const tb = new Date(b.releaseTime || b.release_time || 0).getTime()
    return (tb||0) - (ta||0)
  })
})

const handleGenerateDownload = async () => {
  if (!canSubmit.value) return ElMessage.error('请完善必填项')
  const payload = {
    versionName: form.value.versionName,
    seed: form.value.seed,
    structureOverrides: form.value.structureOverrides,
    biomes: form.value.biomes,
    layers: form.value.layers.map(l => ({ block: l.block, height: Number(l.height)||1 }))
  }
  try {
    const res = await apiClient.post('/api/tools/superflat/leveldat', payload, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'level.dat'
    a.click()
    URL.revokeObjectURL(url)
    ElNotification({ title: '已下载', message: 'level.dat 下载完成', type: 'success' })
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '下载失败'
    ElMessage.error(msg)
  }
}

const applyDialogVisible = ref(false)
const apply = ref({ serverId: '', forceOverwrite: false })
const servers = ref([])
const isFetchingServers = ref(false)

watch(() => apply.value.serverId, (id) => {
  if (!id) return
  const s = servers.value.find(x => String(x?.id) === String(id))
  const serverVer = s?.core_config?.core_version
  if (serverVer && form.value.versionName !== serverVer) {
    form.value.versionName = serverVer
    ElMessage.info(`已自动切换游戏版本为服务器版本：${serverVer}`)
  }
})

const openApplyDialog = async () => {
  applyDialogVisible.value = true
  if (servers.value.length === 0) {
    isFetchingServers.value = true
    try {
      const { data } = await apiClient.get('/api/servers')
      servers.value = data || []
    } finally {
      isFetchingServers.value = false
    }
  }
}

const handleApplyToServer = async () => {
  if (!canSubmit.value) return
  if (!apply.value.serverId) return ElMessage.warning('请选择服务器')
  // 询问覆盖
  if (apply.value.forceOverwrite) {
    await ElMessageBox.confirm('将删除原有存档后写入新的 level.dat', '覆盖确认', { type: 'warning' })
  } else {
    await ElMessageBox.confirm('如服务器已有存档，可能与新 level.dat 冲突', '提示', { type: 'info' })
  }
  applyDialogVisible.value = false
  const payload = {
    versionName: form.value.versionName,
    seed: form.value.seed,
    structureOverrides: form.value.structureOverrides,
    biomes: form.value.biomes,
    layers: form.value.layers.map(l => ({ block: l.block, height: Number(l.height)||1 })),
    server_id: apply.value.serverId,
    overwrite: apply.value.forceOverwrite
  }
  try {
    const { data } = await apiClient.post('/api/tools/superflat/apply', payload)
    ElNotification({ title: '已应用', message: `level.dat 已写入：${data?.path || ''}`.trim(), type: 'success' })
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '应用失败'
    ElMessage.error(msg)
  }
}

// 结构与群系选项（可根据需要扩展）
const structureOptions = [
  'minecraft:village','minecraft:pillager_outpost','minecraft:stronghold','minecraft:mineshaft','minecraft:buried_treasure',
  'minecraft:ruined_portal','minecraft:shipwreck','minecraft:ocean_ruin_cold','minecraft:ocean_ruin_warm','minecraft:monument',
  'minecraft:desert_pyramid','minecraft:igloo','minecraft:jungle_pyramid','minecraft:swamp_hut','minecraft:ancient_city'
]
const biomeOptions = [
  'minecraft:plains','minecraft:desert','minecraft:forest','minecraft:savanna','minecraft:taiga','minecraft:snowy_plains',
  'minecraft:swamp','minecraft:jungle','minecraft:badlands','minecraft:mushroom_fields','minecraft:windswept_hills',
  'minecraft:river','minecraft:beach'
]

onMounted(async ()=>{
  // 版本列表
  try {
    isFetchingVersions.value = true
    const { data } = await apiClient.get('/api/minecraft/versions')
    mojangVersions.value = data?.versions || []
  } catch (e) {
    if (!isRequestCanceled(e)) ElMessage.error('获取 Minecraft 版本列表失败')
  } finally {
    isFetchingVersions.value = false
  }
})
</script>

<style scoped>
.left-wrap { display: flex; justify-content: center; }
.left-panel { max-width: 820px; width: 820px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: 8px; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 500; }
.text-gray-500 { color: #909399; }
.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mb-2 { margin-bottom: 8px; }

/* 表单两行标签样式，参考 ServerList.vue */
.form-item-wrapper { display: flex; align-items: center; gap: 18px; }
.form-item-label { display: flex; flex-direction: column; width: 200px; min-width: 200px; row-gap: 2px; line-height: 1.2; flex-shrink: 0; }
.form-item-label > span { font-weight: 500; line-height: 1.2; margin: 0; }
.form-item-label > small { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.1; margin-top: 2px; }
.form-item-control { flex: 1; min-width: 0; }

.layer-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; }
.drag-handle { cursor: move; }
.block-input { width: 360px; }

.version-row { display: flex; align-items: center; gap: 12px; }
.version-checkboxes { display: flex; gap: 12px; }
.tip-muted { margin-top: 6px; color: #909399; font-size: 12px; }
.option-row { display: flex; align-items: center; justify-content: space-between; width: 100%; }
</style>
