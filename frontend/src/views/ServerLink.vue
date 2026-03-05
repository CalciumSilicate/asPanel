<template>
  <div class="sl-page">
    <!-- Toolbar -->
    <LinkToolbar
      :groups="groups"
      :active-group="activeGroup"
      @select-group="selectGroup"
      @create="handleCreateGroup"
    />

    <!-- Non-admin placeholder -->
    <div v-if="!isPlatformAdmin" class="sl-glass-card">
      <div class="shimmer-line" aria-hidden="true" />
      <div class="sl-empty">
        <el-empty description="此页面仅对平台管理员开放" />
      </div>
    </div>

    <!-- Group picker (no selection) -->
    <div v-else-if="!activeGroup" class="sl-placeholder">
      <LinkGroupPicker :groups="groups" @select="selectGroup" />
    </div>

    <!-- Group editor -->
    <div v-else class="sl-glass-card is-editor">
      <div class="shimmer-line" aria-hidden="true" />
      <LinkGroupEditor
        :group="activeGroup"
        :servers="servers"
        :servers-loading="serversLoading"
        :data-source-options="dataSourceOptions"
        @delete="deleteGroup"
        @update:name="activeGroup.name = $event"
        @update:server-ids="activeGroup.serverIds = $event"
        @update:data-source-ids="activeGroup.dataSourceIds = $event"
        @qq-input="onQQInput"
        @qq-blur="onQQBlur"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useServerLink } from '@/composables/useServerLink'
import LinkToolbar from './server-link/LinkToolbar.vue'
import LinkGroupPicker from './server-link/LinkGroupPicker.vue'
import LinkGroupEditor from './server-link/LinkGroupEditor.vue'

const {
  isPlatformAdmin,
  groups,
  activeGroup,
  servers,
  serversLoading,
  dataSourceOptions,
  selectGroup,
  handleCreateGroup,
  deleteGroup,
  onQQInput,
  onQQBlur,
} = useServerLink()
</script>

<style scoped>
/* ─── Page layout ─────────────────────────────────────────── */
.sl-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
  min-height: 0;
}

/* ─── Placeholder (group picker) ──────────────────────────── */
.sl-placeholder {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.50);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(16px);
  border: 1px solid rgba(119, 181, 254, 0.14);
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .sl-placeholder {
  background: rgba(15, 23, 42, 0.60);
  border-color: rgba(119, 181, 254, 0.10);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.30), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

/* ─── Glass card (editor + empty) ────────────────────────── */
.sl-glass-card {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow:
    0 4px 24px rgba(119, 181, 254, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  overflow: hidden;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.sl-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .sl-glass-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Shimmer line (matches WelcomeCard / ChatRoom) */
.shimmer-line {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(119, 181, 254, 0.7),
    rgba(239, 183, 186, 0.6),
    rgba(167, 139, 250, 0.5),
    transparent
  );
  background-size: 200% 100%;
  animation: shimmer 5s linear infinite;
  z-index: 2;
  pointer-events: none;
}
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* Empty state centering */
.sl-empty {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ─── Editor mode: constrained width ─────────────────────── */
.sl-glass-card.is-editor {
  max-width: 900px;
  width: 100%;
  align-self: center;
}
</style>
