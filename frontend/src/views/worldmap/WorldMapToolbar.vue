<template>
  <div class="wm-toolbar">
    <!-- Decorative blobs -->
    <div class="deco" aria-hidden="true">
      <span class="deco-blob deco-1" />
      <span class="deco-blob deco-2" />
    </div>

    <div class="toolbar-left">
      <el-select
        :model-value="selectedServerId"
        placeholder="选择服务器"
        style="width: 160px"
        :loading="serversLoading"
        @change="(v) => { $emit('update:selectedServerId', v); $emit('server-change') }"
      >
        <el-option v-for="s in servers" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>

      <el-radio-group
        :model-value="activeDim"
        size="small"
        :disabled="!selectedServerId"
        @change="(v) => { $emit('update:activeDim', v); $emit('dim-change') }"
      >
        <el-radio-button value="nether">下界/主世界</el-radio-button>
        <el-radio-button value="end">末地</el-radio-button>
      </el-radio-group>

      <div class="toolbar-divider" />

      <el-button
        v-if="selectedServerId && !mapLoading && !hasMapData"
        size="small"
        type="primary"
        class="btn-create-map"
        @click="$emit('create-blank-map')"
      >新建空白地图</el-button>

      <el-button-group size="small">
        <el-button :type="layout === 'left'  ? 'primary' : ''" @click="$emit('update:layout', 'left')"  title="仅显示地图">
          <el-icon><Grid /></el-icon>
        </el-button>
        <el-button :type="layout === 'split' ? 'primary' : ''" @click="$emit('update:layout', 'split')" title="双栏">双栏</el-button>
        <el-button :type="layout === 'right' ? 'primary' : ''" @click="$emit('update:layout', 'right')" title="仅显示 BlueMap">BlueMap</el-button>
      </el-button-group>
    </div>

    <div class="toolbar-right">
      <el-checkbox
        :model-value="showOfflinePlayers"
        label="离线玩家"
        size="small"
        @change="(v) => $emit('update:showOfflinePlayers', v)"
      />

      <div class="toolbar-divider" />

      <el-date-picker
        :model-value="trajectoryFromTime"
        type="datetime"
        placeholder="轨迹起始时间"
        size="small"
        style="width: 168px"
        clearable
        format="MM-DD HH:mm"
        value-format="YYYY-MM-DDTHH:mm:ss"
        :disabled="!selectedServerId"
        @update:modelValue="$emit('update:trajectoryFromTime', $event)"
        @change="$emit('trajectory-from-time-change')"
      />

      <div class="toolbar-divider" />

      <el-switch
        :model-value="editMode"
        active-text="编辑"
        inactive-text="查看"
        size="small"
        :disabled="!selectedServerId"
        @change="(v) => { $emit('update:editMode', v); $emit('edit-mode-change', v) }"
      />

      <template v-if="editMode">
        <el-button
          size="small"
          :type="connectMode ? 'warning' : ''"
          @click="$emit('toggle-connect-mode')"
          title="连线模式：起点→终点节点，或终点→已有线段（垂直插入）"
        >
          {{ connectMode ? (connectSourceKey ? '点击终点/线段…' : '点击起点…') : '连线' }}
        </el-button>
        <el-button
          size="small"
          :type="addVirtualMode ? 'info' : ''"
          @click="$emit('toggle-add-virtual-mode')"
          title="切换后双击放置虚拟节点（也可 Shift+双击）"
        >虚拟节点</el-button>
        <el-button size="small" type="danger" :disabled="!canDelete" @click="$emit('delete-selected')">删除</el-button>
        <el-button size="small" type="primary" :disabled="!dirty" :loading="saving" @click="$emit('save-map')">保存</el-button>
      </template>

      <div class="toolbar-divider" />

      <el-input
        :model-value="bluemapUrlInput"
        placeholder="BlueMap 地址（如 http://localhost:8100）"
        size="small"
        style="width: 260px"
        clearable
        @change="(v) => { $emit('update:bluemapUrlInput', v); $emit('save-bluemap-url') }"
      >
        <template #prefix><el-icon><MapLocation /></el-icon></template>
      </el-input>
    </div>
  </div>
</template>

<script setup>
import { Grid, MapLocation } from '@element-plus/icons-vue'

defineProps({
  servers:            { type: Array,   default: () => [] },
  serversLoading:     { type: Boolean, default: false },
  selectedServerId:   { default: null },
  activeDim:          { type: String,  default: 'nether' },
  layout:             { type: String,  default: 'left' },
  mapLoading:         { type: Boolean, default: false },
  hasMapData:         { type: Boolean, default: false },
  showOfflinePlayers: { type: Boolean, default: false },
  trajectoryFromTime: { default: null },
  editMode:           { type: Boolean, default: false },
  connectMode:        { type: Boolean, default: false },
  connectSourceKey:   { default: null },
  addVirtualMode:     { type: Boolean, default: false },
  canDelete:          { type: Boolean, default: false },
  dirty:              { type: Boolean, default: false },
  saving:             { type: Boolean, default: false },
  bluemapUrlInput:    { type: String,  default: '' },
})

defineEmits([
  'update:selectedServerId', 'server-change',
  'update:activeDim',        'dim-change',
  'update:layout',
  'create-blank-map',
  'update:showOfflinePlayers',
  'update:trajectoryFromTime', 'trajectory-from-time-change',
  'update:editMode',           'edit-mode-change',
  'toggle-connect-mode',
  'toggle-add-virtual-mode',
  'delete-selected',
  'save-map',
  'update:bluemapUrlInput',    'save-bluemap-url',
])
</script>

<style scoped>
.wm-toolbar {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow:
    0 4px 24px rgba(119, 181, 254, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  flex-wrap: wrap;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.wm-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .wm-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* ─── Decorative blobs ─────────────────────────────────── */
.deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.deco-blob { position: absolute; border-radius: 50%; filter: blur(28px); }
.deco-1 {
  width: 160px; height: 120px;
  background: radial-gradient(circle, rgba(119,181,254,0.20), transparent 70%);
  right: -30px; top: -40px;
}
.deco-2 {
  width: 80px; height: 80px;
  background: radial-gradient(circle, rgba(167,139,250,0.18), transparent 70%);
  right: 200px; bottom: -20px;
}

/* ─── Layout ───────────────────────────────────────────── */
.toolbar-left,
.toolbar-right {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  z-index: 1;
}
.toolbar-right { flex-shrink: 0; }

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
  flex-shrink: 0;
}

/* ─── Select pill styling ──────────────────────────────── */
.toolbar-left :deep(.el-select .el-input__wrapper),
.toolbar-right :deep(.el-select .el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.toolbar-left :deep(.el-select .el-input__wrapper:hover),
.toolbar-right :deep(.el-select .el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.42) !important;
  background: rgba(255, 255, 255, 0.78) !important;
}
.toolbar-left :deep(.el-select .el-input__wrapper.is-focus),
.toolbar-right :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .toolbar-left :deep(.el-select .el-input__wrapper),
:global(.dark) .toolbar-right :deep(.el-select .el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}
:global(.dark) .toolbar-left :deep(.el-select .el-input__wrapper:hover),
:global(.dark) .toolbar-right :deep(.el-select .el-input__wrapper:hover) {
  background: rgba(15, 23, 42, 0.80) !important;
  border-color: rgba(119, 181, 254, 0.32) !important;
}

/* ─── Input pill styling (date-picker, url input) ──────── */
.toolbar-right :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.toolbar-right :deep(.el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.42) !important;
  background: rgba(255, 255, 255, 0.78) !important;
}
.toolbar-right :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .toolbar-right :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}
:global(.dark) .toolbar-right :deep(.el-input__wrapper:hover) {
  background: rgba(15, 23, 42, 0.80) !important;
  border-color: rgba(119, 181, 254, 0.32) !important;
}

/* ─── Create map button ────────────────────────────────── */
.btn-create-map {
  border-radius: 22px !important;
}
</style>
