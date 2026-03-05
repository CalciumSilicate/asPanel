<template>
  <div class="online-panel">
    <div class="panel-header">
      <span class="panel-title">在线用户</span>
      <el-tag size="small" type="info">{{ users.length }}</el-tag>
    </div>
    <div class="panel-list">
      <div v-if="users.length === 0" class="panel-empty">暂无用户</div>
      <div class="panel-item" v-for="u in users" :key="u.username">
        <img
          v-if="u.avatar_url"
          class="user-avatar"
          :src="u.avatar_url"
          :alt="u.username"
          referrerpolicy="no-referrer"
        />
        <el-avatar v-else :size="24" :icon="UserFilled" class="user-avatar" />
        <span class="uname">{{ u.username }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'
import type { OnlineUser } from '@/composables/useChatRoom'

defineProps<{
  users: OnlineUser[]
}>()
</script>

<style scoped>
.online-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgba(255, 255, 255, 0.50);
  -webkit-backdrop-filter: saturate(160%) blur(12px);
  backdrop-filter: saturate(160%) blur(12px);
  border: 1px solid rgba(119, 181, 254, 0.16);
  border-radius: 14px;
  overflow: hidden;
}
:global(.dark) .online-panel {
  background: rgba(15, 23, 42, 0.55);
  border-color: rgba(119, 181, 254, 0.10);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
  flex-shrink: 0;
}
.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.panel-list {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 6px 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(200, 200, 200, 0.5) transparent;
}
.panel-list::-webkit-scrollbar { width: 4px; }
.panel-list::-webkit-scrollbar-thumb { background: rgba(200, 200, 200, 0.5); border-radius: 2px; }
.panel-list::-webkit-scrollbar-track { background: transparent; }
.panel-empty {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: 12px 0;
}
.panel-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 4px;
  border-radius: 8px;
  transition: background 0.18s ease;
}
.panel-item:hover {
  background: rgba(119, 181, 254, 0.08);
}
.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
}
.uname {
  font-size: 12px;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
</style>
