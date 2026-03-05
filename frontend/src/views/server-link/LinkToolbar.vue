<template>
  <div class="link-toolbar">
    <!-- Decorative blobs -->
    <div class="deco" aria-hidden="true">
      <span class="deco-blob deco-1" />
      <span class="deco-blob deco-2" />
    </div>

    <div class="toolbar-left">
      <!-- Group selector -->
      <el-select
        :model-value="activeGroupId"
        placeholder="选择服务器组"
        filterable
        clearable
        style="width: 220px"
        @change="(id: number | null) => onGroupChange(id)"
        :loading="groups.length === 0"
      >
        <template #prefix>
          <el-icon style="color: var(--brand-primary); margin-right: 2px"><Link /></el-icon>
        </template>
        <el-option
          v-for="g in groups"
          :key="g.id"
          :label="g.name"
          :value="g.id"
        >
          <div class="group-option">
            <span>{{ g.name }}</span>
            <el-tag size="small" type="info" class="group-count-tag">
              {{ g.serverIds?.length ?? 0 }} 台
            </el-tag>
          </div>
        </el-option>
      </el-select>
    </div>

    <div class="toolbar-right">
      <!-- Create button -->
      <button class="btn-create" @click="$emit('create')" title="新建服务器组">
        <el-icon><Plus /></el-icon>
        <span>新建组</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Link, Plus, Monitor } from '@element-plus/icons-vue'
import type { ServerLinkGroup } from '@/composables/useServerLink'

const props = defineProps<{
  groups: ServerLinkGroup[]
  activeGroup: ServerLinkGroup | null
}>()

const emit = defineEmits<{
  create: []
  'select-group': [group: ServerLinkGroup | null]
}>()

const activeGroupId = computed(() => props.activeGroup?.id ?? null)

const onGroupChange = (id: number | null) => {
  if (id === null) { emit('select-group', null); return }
  const found = props.groups.find((g) => g.id === id)
  if (found) emit('select-group', found)
}
</script>

<style scoped>
.link-toolbar {
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
.link-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .link-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Decorative blobs */
.deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.deco-blob { position: absolute; border-radius: 50%; filter: blur(28px); }
.deco-1 {
  width: 120px; height: 120px;
  background: radial-gradient(circle, rgba(119,181,254,0.22), transparent 70%);
  right: -20px; top: -40px;
}
.deco-2 {
  width: 80px; height: 80px;
  background: radial-gradient(circle, rgba(167,139,250,0.18), transparent 70%);
  right: 140px; bottom: -20px;
}

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

/* Glass pill select */
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
.toolbar-left :deep(.el-select .el-input__prefix) {
  color: var(--brand-primary) !important;
}
.toolbar-left :deep(.el-select .el-icon.el-select__caret) {
  color: var(--brand-primary) !important;
  transition: transform 0.25s cubic-bezier(.34,1.56,.64,1) !important;
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
}

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
.server-tag, .qq-tag {
  display: inline-flex;
  align-items: center;
}
.online-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 5px rgba(52,211,153,0.7);
  margin-right: 5px;
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
.group-count-tag { flex-shrink: 0; }

/* Create button */
.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 16px;
  border-radius: 22px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.40);
  transition:
    box-shadow 0.25s ease,
    transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.btn-create:hover {
  box-shadow: 0 6px 22px rgba(119, 181, 254, 0.65);
  transform: translateY(-1px) scale(1.04);
}
.btn-create:active {
  transform: scale(0.97);
  box-shadow: 0 2px 8px rgba(119, 181, 254, 0.30);
}
</style>
