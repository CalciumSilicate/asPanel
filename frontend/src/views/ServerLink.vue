<template>
  <div class="sl-page">
    <div class="page-orbs" aria-hidden="true">
      <span class="page-orb page-orb-1"></span>
      <span class="page-orb page-orb-2"></span>
      <span class="page-orb page-orb-3"></span>
    </div>
    <!-- Toolbar -->
    <LinkToolbar
      :groups="groups"
      :active-group="activeGroup"
      @select-group="selectGroup"
      @create="handleCreateGroup"
    />

    <!-- Main area: grid lets skeleton & content overlap -->
    <div class="sl-main-wrap aurora-stage">

      <!-- Skeleton while loading -->
      <Transition name="pg-skeleton">
        <div v-if="!loaded" class="sk-sl-panel" aria-hidden="true">
          <div class="sk-sl-list">
            <div v-for="i in 5" :key="i" class="sk-sl-item">
              <div class="sk-sl-icon shimmer"></div>
              <div class="sk-sl-info">
                <div class="sk-line shimmer" :style="{ width: ['90px','110px','80px','120px','95px'][i-1], height: '14px' }"></div>
                <div class="sk-line shimmer" style="width:140px;height:10px;margin-top:6px"></div>
              </div>
              <div class="sk-sl-arrow shimmer"></div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Real content once loaded -->
      <Transition name="pg-content">
        <div v-if="loaded" class="sl-content-wrap">

          <!-- Non-admin placeholder -->
          <div v-if="!isPlatformAdmin" class="sl-glass-card pg-item" style="--delay: 0ms">
            <div class="shimmer-line" aria-hidden="true" />
            <div class="sl-empty">
              <el-empty description="此页面仅对平台管理员开放" />
            </div>
          </div>

          <!-- Group picker (no selection) -->
          <div v-else-if="!activeGroup" class="sl-placeholder pg-item" style="--delay: 0ms">
            <LinkGroupPicker :groups="groups" @select="selectGroup" />
          </div>

          <!-- Group editor -->
          <div v-else class="sl-glass-card is-editor pg-item" style="--delay: 0ms">
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

        </div><!-- end sl-content-wrap -->
      </Transition>
    </div><!-- end sl-main-wrap -->
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
  loaded,
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
  position: relative;
  height: calc(100vh - var(--el-header-height) - 44px);
  height: calc(100dvh - var(--el-header-height) - 44px);
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
  min-height: 0;
}

.page-orbs {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.page-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.42;
}

.page-orb-1 {
  width: 280px;
  height: 280px;
  top: -80px;
  right: -20px;
  background: rgba(119,181,254,0.20);
}

.page-orb-2 {
  width: 220px;
  height: 220px;
  left: -40px;
  bottom: 10%;
  background: rgba(239,183,186,0.18);
}

.page-orb-3 {
  width: 180px;
  height: 180px;
  right: 18%;
  bottom: -30px;
  background: rgba(166,200,240,0.18);
}

.aurora-stage {
  position: relative;
  z-index: 1;
}

/* ─── Placeholder (group picker) ──────────────────────────── */
.sl-placeholder {
  position: relative;
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
.sl-placeholder::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(119,181,254,0.04) 45%, rgba(239,183,186,0.08));
  pointer-events: none;
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

/* ─── Main wrap: grid lets skeleton & content overlap ─── */
.sl-main-wrap {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  overflow: hidden;
}
.sk-sl-panel,
.sl-content-wrap {
  grid-area: 1 / 1;
  min-height: 0;
}
.sl-content-wrap {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* ─── Page transitions ───────────────────────────────── */
.pg-skeleton-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
  pointer-events: none;
  z-index: 1;
}
.pg-skeleton-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
.pg-content-enter-active .pg-item {
  animation: pg-rise 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: var(--delay, 0ms);
}
@keyframes pg-rise {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ─── ServerLink skeleton ────────────────────────────── */
.sk-sl-panel {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:global(.dark) .sk-sl-panel {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
}
.sk-sl-list {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sk-sl-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(119, 181, 254, 0.04);
  border: 1px solid rgba(119, 181, 254, 0.08);
}
.sk-sl-icon {
  width: 40px; height: 40px;
  border-radius: 12px;
  flex-shrink: 0;
}
.sk-sl-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.sk-sl-arrow {
  width: 20px; height: 20px;
  border-radius: 6px;
  flex-shrink: 0;
}
.sk-line { display: block; border-radius: 6px; }

/* ─── Shimmer ────────────────────────────────────────── */
@keyframes shimmer-move {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
.shimmer {
  background: linear-gradient(90deg,
    rgba(128,128,128,0.08) 25%,
    rgba(128,128,128,0.18) 50%,
    rgba(128,128,128,0.08) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
}
:global(.dark) .shimmer {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.10) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
}
</style>
