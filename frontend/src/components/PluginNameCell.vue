<template>
  <div class="pnc-cell">
    <el-tag v-if="id" type="primary" effect="plain" size="small" class="pnc-id">{{ id }}</el-tag>
    <div class="pnc-text">
      <div class="pnc-name">{{ name || '未知名称' }}</div>
      <div v-if="description || filename" class="pnc-desc">{{ description || filename }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  id?: string
  name?: string
  description?: string
  filename?: string
}>()
</script>

<style scoped>
.pnc-cell {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.pnc-id {
  flex-shrink: 0;
  font-family: 'Maple Mono', ui-monospace, monospace !important;
  font-size: 11px !important;
}
.pnc-text {
  min-width: 0;
  flex: 1;
}
.pnc-name {
  font-weight: 600;
  font-size: 13px;
  line-height: 1.35;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pnc-desc {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
  line-height: 1.3;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 380px;
}
</style>
