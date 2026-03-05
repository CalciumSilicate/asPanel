<template>
  <div class="editor-scroll">
    <div class="editor-inner">
      <!-- Header bar -->
      <div class="editor-header">
        <div class="editor-title-row">
          <div class="title-icon-wrap">
            <el-icon :size="18"><EditPen /></el-icon>
          </div>
          <div class="title-text">
            <span class="editor-name">{{ group.name }}</span>
            <span class="editor-id">ID {{ group.id }}</span>
          </div>
          <div class="header-tags">
            <el-tag type="info" size="small">
              {{ group.serverIds?.length ?? 0 }} 台服务器
            </el-tag>
            <el-tag v-if="group.qqGroup" type="success" size="small">
              <span class="dot-green" />
              绑定 QQ {{ group.qqGroup }}
            </el-tag>
          </div>
          <div class="header-actions">
            <button class="btn-delete" @click="$emit('delete', group)" title="删除此服务器组">
              <el-icon><Delete /></el-icon>
              <span>删除</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Form sections -->
      <div class="sections">

        <!-- Section: Basic -->
        <div class="section-card">
          <div class="section-label">基本信息</div>
          <div class="field-row">
            <label class="field-label">组名 <span class="req">*</span></label>
            <el-input
              :model-value="group.name"
              placeholder="请输入组名"
              class="glass-input"
              @input="(v: string) => $emit('update:name', v)"
            />
          </div>
        </div>

        <!-- Section: Servers -->
        <div class="section-card">
          <div class="section-label">服务器配置</div>
          <div class="field-row">
            <label class="field-label">选择服务器 <span class="req">*</span></label>
            <el-select
              :model-value="group.serverIds"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              :max-collapse-tags="5"
              placeholder="请选择服务器"
              style="width: 100%"
              :loading="serversLoading"
              class="glass-select"
              @change="(v: number[]) => $emit('update:serverIds', v)"
            >
              <el-option
                v-for="s in servers"
                :key="s.id"
                :label="s.name"
                :value="s.id"
                :disabled="(s.core_config?.server_type || s.core_config?.serverType) === 'velocity'"
              />
            </el-select>
          </div>

          <div class="field-row">
            <label class="field-label">数据来源</label>
            <el-select
              :model-value="group.dataSourceIds"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              :max-collapse-tags="5"
              placeholder="默认使用所有选中的服务器"
              style="width: 100%"
              class="glass-select"
              @change="(v: number[]) => $emit('update:dataSourceIds', v)"
            >
              <el-option
                v-for="s in dataSourceOptions"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
            <span class="field-hint">若留空，则默认统计该组内所有服务器的数据。</span>
          </div>
        </div>

        <!-- Section: Bindings -->
        <div class="section-card">
          <div class="section-label">聊天绑定</div>
          <div class="field-row">
            <label class="field-label">QQ 群号</label>
            <el-input
              :model-value="group.qqGroup"
              placeholder="请输入QQ群号（留空表示不绑定）"
              clearable
              style="max-width: 360px"
              class="glass-input"
              @input="(v: string) => $emit('qq-input', v)"
              @blur="$emit('qq-blur')"
            />
            <span class="field-hint">留空表示不绑定QQ群。</span>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { EditPen, Delete } from '@element-plus/icons-vue'
import type { ServerLinkGroup, ServerItem } from '@/composables/useServerLink'

defineProps<{
  group: ServerLinkGroup
  servers: ServerItem[]
  serversLoading: boolean
  dataSourceOptions: ServerItem[]
}>()

defineEmits<{
  delete: [group: ServerLinkGroup]
  'update:name': [v: string]
  'update:serverIds': [v: number[]]
  'update:dataSourceIds': [v: number[]]
  'qq-input': [v: string]
  'qq-blur': []
}>()
</script>

<style scoped>
.editor-scroll {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(119,181,254,0.25) transparent;
  box-sizing: border-box;
}
.editor-scroll::-webkit-scrollbar { width: 5px; }
.editor-scroll::-webkit-scrollbar-thumb { background: rgba(119,181,254,0.30); border-radius: 3px; }

.editor-inner {
  padding: 28px 36px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 820px;
}

/* ─── Header ──────────────────────────────────────────────── */
.editor-header {
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
}
.editor-title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.title-icon-wrap {
  width: 42px; height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(119,181,254,0.18), rgba(167,139,250,0.14));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-primary);
  flex-shrink: 0;
}
.title-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.editor-name {
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  line-height: 1.2;
}
.editor-id {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.header-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.dot-green {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #34d399;
  margin-right: 4px;
  vertical-align: middle;
}
.header-actions { margin-left: auto; }

.btn-delete {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border-radius: 22px;
  border: 1px solid rgba(239, 68, 68, 0.30);
  background: rgba(239, 68, 68, 0.06);
  color: #ef4444;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.22s ease,
    border-color 0.22s ease,
    color 0.22s ease,
    transform 0.22s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.22s ease;
}
.btn-delete:hover {
  background: linear-gradient(135deg, #ef4444, #f97316);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.40);
  transform: translateY(-1px) scale(1.04);
}
.btn-delete:active {
  transform: scale(0.97);
}

/* ─── Section cards ───────────────────────────────────────── */
.sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-card {
  background: rgba(255, 255, 255, 0.45);
  -webkit-backdrop-filter: saturate(160%) blur(12px);
  backdrop-filter: saturate(160%) blur(12px);
  border: 1px solid rgba(119, 181, 254, 0.14);
  border-radius: 16px;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.section-card:hover {
  border-color: rgba(119, 181, 254, 0.24);
  box-shadow: 0 4px 20px rgba(119, 181, 254, 0.07);
}
:global(.dark) .section-card {
  background: rgba(15, 23, 42, 0.50);
  border-color: rgba(119, 181, 254, 0.10);
}

.section-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--brand-primary);
  opacity: 0.85;
}

/* ─── Field rows ──────────────────────────────────────────── */
.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.req { color: #ef4444; margin-left: 2px; }
.field-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

/* Tags: single-line, no wrap, clip overflow */
.glass-select :deep(.el-select__tags) {
  flex-wrap: nowrap !important;
  overflow: hidden !important;
}
.glass-select :deep(.el-select__tags-text) {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* ─── Glass input overrides ───────────────────────────────── */
.glass-input :deep(.el-input__wrapper),
.glass-select :deep(.el-input__wrapper) {
  border-radius: 12px !important;
  background: rgba(255, 255, 255, 0.55) !important;
  border: 1px solid rgba(119, 181, 254, 0.20) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.glass-input :deep(.el-input__wrapper:hover),
.glass-select :deep(.el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.38) !important;
  background: rgba(255, 255, 255, 0.72) !important;
}
.glass-input :deep(.el-input__wrapper.is-focus),
.glass-select :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.58) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.85) !important;
}
:global(.dark) .glass-input :deep(.el-input__wrapper),
:global(.dark) .glass-select :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.55) !important;
  border-color: rgba(119, 181, 254, 0.16) !important;
}
:global(.dark) .glass-input :deep(.el-input__wrapper:hover),
:global(.dark) .glass-select :deep(.el-input__wrapper:hover) {
  background: rgba(15, 23, 42, 0.75) !important;
  border-color: rgba(119, 181, 254, 0.28) !important;
}
:global(.dark) .glass-input :deep(.el-input__wrapper.is-focus),
:global(.dark) .glass-select :deep(.el-input__wrapper.is-focus) {
  background: rgba(15, 23, 42, 0.90) !important;
}
</style>
