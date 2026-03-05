<template>
  <div class="chat-toolbar">
    <!-- Decorative blobs -->
    <div class="deco" aria-hidden="true">
      <span class="deco-blob deco-1" />
      <span class="deco-blob deco-2" />
    </div>

    <div class="toolbar-left">
      <el-select
        :model-value="activeGroupId"
        placeholder="选择服务器组"
        filterable
        style="width: 210px"
        @change="(id: number) => onGroupChange(id)"
        :loading="groups.length === 0"
      >
        <!-- Prefix: group icon -->
        <template #prefix>
          <el-icon style="color: var(--brand-primary); margin-right: 2px"><Grid /></el-icon>
        </template>
        <el-option
          v-for="g in groups"
          :key="g.id"
          :label="g.name"
          :value="g.id"
        >
          <div class="group-option">
            <span>{{ g.name }}</span>
            <el-tag size="small" type="success" class="group-online-tag">{{ onlineCount(g) }}</el-tag>
          </div>
        </el-option>
      </el-select>

      <template v-if="activeGroup">
        <div class="toolbar-divider" />
        <div class="active-group-info">
          <span class="group-name">{{ activeGroup.name }}</span>
          <el-tag type="success" size="small" class="online-tag">
            <span class="online-dot" />
            在线 {{ onlineCount(activeGroup) }} 台
          </el-tag>
        </div>
      </template>
    </div>

    <div class="toolbar-right">
      <!-- Alert button -->
      <button
        v-if="canSendAlert"
        class="alert-btn"
        @click="$emit('alert')"
        title="向所有服务器组广播紧急通知"
      >
        <el-icon class="alert-icon"><BellFilled /></el-icon>
        <span>全局通知</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Grid, BellFilled } from '@element-plus/icons-vue'
import type { Group } from '@/composables/useChatRoom'

const props = defineProps<{
  groups: Group[]
  activeGroup: Group | null
  canSendAlert: boolean
  onlineCount: (g: Group) => number
}>()

const emit = defineEmits<{
  alert: []
  'select-group': [group: Group]
}>()

const activeGroupId = computed(() => props.activeGroup?.id ?? null)

const onGroupChange = (id: number) => {
  const found = props.groups.find((g) => g.id === id)
  if (found) emit('select-group', found)
}
</script>

<style scoped>
.chat-toolbar {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow:
    0 4px 24px rgba(119, 181, 254, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.chat-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .chat-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* ─── Decorative blobs ───────────────────────────────────── */
.deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.deco-blob { position: absolute; border-radius: 50%; filter: blur(28px); }
.deco-1 {
  width: 120px; height: 120px;
  background: radial-gradient(circle, rgba(119,181,254,0.22), transparent 70%);
  right: -20px; top: -40px;
}
.deco-2 {
  width: 80px; height: 80px;
  background: radial-gradient(circle, rgba(239,183,186,0.20), transparent 70%);
  right: 120px; bottom: -20px;
}

/* ─── Left section ───────────────────────────────────────── */
.toolbar-left {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  z-index: 1;
}
.toolbar-right {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  z-index: 1;
}

/* ─── Select input styling ───────────────────────────────── */
.toolbar-left :deep(.el-select .el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
  padding-left: 10px !important;
}
.toolbar-left :deep(.el-select .el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.42) !important;
  background: rgba(255, 255, 255, 0.78) !important;
}
.toolbar-left :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .toolbar-left :deep(.el-select .el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}
:global(.dark) .toolbar-left :deep(.el-select .el-input__wrapper:hover) {
  background: rgba(15, 23, 42, 0.80) !important;
  border-color: rgba(119, 181, 254, 0.32) !important;
}
/* Prefix icon colour */
.toolbar-left :deep(.el-select .el-input__prefix) {
  color: var(--brand-primary) !important;
}
/* Suffix arrow */
.toolbar-left :deep(.el-select .el-icon.el-select__caret) {
  color: var(--brand-primary) !important;
  transition: transform 0.25s cubic-bezier(.34,1.56,.64,1) !important;
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
}

/* Active group info */
.active-group-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.group-name {
  font-size: 14px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.online-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.online-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 5px rgba(52,211,153,0.7);
  animation: dot-pulse 2.2s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(52,211,153,0.55); }
  50%       { box-shadow: 0 0 9px rgba(52,211,153,0.90), 0 0 18px rgba(52,211,153,0.28); }
}

/* Group option in dropdown */
.group-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}
.group-online-tag { flex-shrink: 0; }

/* ─── Alert button ───────────────────────────────────────── */
.alert-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 16px;
  border-radius: 22px;
  border: 1px solid rgba(239, 68, 68, 0.32);
  background: rgba(239, 68, 68, 0.07);
  color: #ef4444;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.25s ease,
    border-color 0.25s ease,
    color 0.25s ease,
    box-shadow 0.25s ease,
    transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.alert-btn:hover {
  background: linear-gradient(135deg, #ef4444, #f97316);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 18px rgba(239, 68, 68, 0.45), 0 0 0 1px rgba(239,68,68,0.15);
  transform: translateY(-1px) scale(1.04);
}
.alert-btn:active {
  transform: scale(0.97);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.25);
}
:global(.dark) .alert-btn {
  background: rgba(239, 68, 68, 0.10);
  border-color: rgba(239, 68, 68, 0.25);
}
:global(.dark) .alert-btn:hover {
  background: linear-gradient(135deg, #ef4444, #f97316);
  border-color: transparent;
  box-shadow: 0 4px 22px rgba(239, 68, 68, 0.55), 0 0 0 1px rgba(239,68,68,0.20);
}

/* Bell ring animation */
.alert-icon {
  animation: bell-ring 4s ease-in-out infinite;
  transform-origin: top center;
}
@keyframes bell-ring {
  0%, 80%, 100% { transform: rotate(0deg); }
  83%  { transform: rotate(-14deg); }
  86%  { transform: rotate(14deg); }
  89%  { transform: rotate(-10deg); }
  92%  { transform: rotate(8deg); }
  95%  { transform: rotate(-4deg); }
  98%  { transform: rotate(2deg); }
}
</style>
