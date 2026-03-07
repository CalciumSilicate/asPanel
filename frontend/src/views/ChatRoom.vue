<template>
  <div class="chat-page">
    <div class="page-orbs" aria-hidden="true">
      <span class="page-orb page-orb-1"></span>
      <span class="page-orb page-orb-2"></span>
      <span class="page-orb page-orb-3"></span>
    </div>
    <!-- Toolbar: group selector + alert -->
    <ChatToolbar
      :groups="groups"
      :active-group="activeGroup"
      :can-send-alert="canSendAlert"
      :online-count="onlineCount"
      @select-group="selectGroup"
      @alert="sendAlert"
    />

    <!-- Main area: grid container lets skeleton & content overlap cleanly -->
    <div class="chat-main-wrap aurora-stage">

      <!-- Skeleton while loading -->
      <Transition name="pg-skeleton">
        <div v-if="!loaded" class="sk-chat-panel" aria-hidden="true">
          <div class="sk-messages">
            <div v-for="i in 7" :key="i" class="sk-msg-row" :class="{ 'sk-compact': i % 3 !== 1 }">
              <div class="sk-avatar-col">
                <div v-if="i % 3 === 1" class="sk-avatar shimmer"></div>
              </div>
              <div class="sk-bubble-col">
                <div v-if="i % 3 === 1" class="sk-meta shimmer"></div>
                <div class="sk-text shimmer" :style="{ width: ['72%','52%','83%','61%','44%','78%','57%'][i-1] }"></div>
              </div>
            </div>
          </div>
          <div class="sk-chat-input">
            <div class="sk-input-box shimmer"></div>
            <div class="sk-send-btn shimmer"></div>
          </div>
        </div>
      </Transition>

      <!-- Real content once loaded -->
      <Transition name="pg-content">
        <div v-if="loaded" class="chat-content-wrap">

          <!-- Placeholder: group picker -->
          <div v-if="!activeGroup" class="chat-placeholder pg-item" style="--delay: 0ms">
            <ChatGroupPicker :groups="groups" :online-count="onlineCount" @select="selectGroup" />
          </div>

          <!-- Main chat panel -->
          <div v-else class="chat-glass-card pg-item" style="--delay: 0ms">
      <!-- Shimmer line (like WelcomeCard) -->
      <div class="shimmer-line" aria-hidden="true" />

      <div class="chat-wrapper">
        <!-- Message area + input -->
        <div class="chat-left">
          <div class="chat-main" ref="chatMainRef" @scroll="onScroll">
            <!-- Load older -->
            <div class="load-older">
              <el-button
                v-if="hasMoreOlder"
                class="btn-load-older"
                size="small"
                :loading="loadingOlder"
                @click="loadMoreHistory"
              >
                <el-icon v-if="!loadingOlder"><ArrowUp /></el-icon>
                加载更多
              </el-button>
              <div v-else-if="noMoreOlder" class="no-more">· 以上是全部记录 ·</div>
            </div>

            <!-- Messages -->
            <template v-for="(m, i) in messages" :key="m.id ?? 'm-' + i">
              <div
                class="msg-row"
                :class="['src-' + m.source, { compact: isCompact(i), 'is-alert': m.level === 'ALERT' }]"
              >
                <div class="avatar-col">
                  <div v-if="!isCompact(i)" class="avatar-ring" :class="'ring-' + m.source">
                    <el-avatar class="avatar" :src="m.avatar ?? undefined" :icon="UserFilled" />
                  </div>
                </div>
                <div class="bubble">
                  <div v-if="!isCompact(i)" class="meta">
                    <span class="sender-name">{{ m.display }}</span>
                    <span class="time">{{ formatTime(m.created_at) }}</span>
                    <el-tag v-if="m.level === 'ALERT'" size="small" type="danger" effect="light">ALERT</el-tag>
                  </div>
                  <div class="content" :class="{ alert: m.level === 'ALERT' }">
                    <template v-if="m.segments && m.segments.length">
                      <template v-for="(seg, idx) in m.segments" :key="idx">
                        <span v-if="seg.kind === 'text'" class="cq-text">{{ seg.text }}</span>
                        <span v-else-if="seg.kind === 'tag'" class="cq-tag" :class="{ 'is-unsupported': seg.unsupported }">{{ seg.label }}</span>
                        <span v-else-if="seg.kind === 'reply'" class="cq-reply">{{ seg.label }}</span>
                        <span v-else-if="seg.kind === 'share'" class="cq-share">
                          <span class="cq-tag">{{ seg.label }}</span>
                          <a v-if="seg.url" :href="seg.url" target="_blank" rel="noopener noreferrer">{{ seg.displayUrl || seg.url }}</a>
                          <span v-else class="cq-tag is-unsupported">链接缺失</span>
                          <span v-if="seg.title" class="cq-share-title">{{ seg.title }}</span>
                        </span>
                        <a v-else-if="seg.kind === 'image' && seg.url" class="cq-image-link" :href="seg.url" target="_blank" rel="noopener noreferrer">
                          <img class="cq-image" :src="seg.url" alt="图片" loading="lazy" referrerpolicy="no-referrer" />
                        </a>
                        <div v-else-if="seg.kind === 'record'" class="cq-record-bubble">
                          <span class="cq-tag">[语音]</span>
                          <audio v-if="seg.url" class="cq-audio" :src="seg.url" controls preload="none" />
                          <span v-else class="cq-tag is-unsupported">音频缺失</span>
                        </div>
                        <span v-else-if="seg.kind === 'image'" class="cq-tag is-unsupported">[图片缺失]</span>
                        <details v-else-if="seg.kind === 'data'" class="cq-data" :title="seg.content">
                          <summary>{{ seg.label }}</summary>
                          <pre>{{ seg.content }}</pre>
                        </details>
                      </template>
                    </template>
                    <template v-else>{{ m.content }}</template>
                  </div>
                </div>
              </div>
            </template>

          </div>

          <!-- Jump-to-bottom FAB: outside chat-main to avoid affecting scroll height -->
          <transition name="fab-pop">
            <button
              v-if="showJumpBottom"
              class="jump-bottom-fab"
              @click="scrollToBottom"
              title="跳到最新消息"
            >
              <el-icon :size="18"><ArrowDown /></el-icon>
            </button>
          </transition>

          <!-- Input bar -->
          <div class="chat-input">
            <el-input
              v-model="draft"
              placeholder="输入消息，按 Enter 发送…"
              @keyup.enter="doSend"
              clearable
              class="msg-input"
            />
            <button
              class="btn-send"
              :disabled="!draft.trim()"
              @click="doSend"
              title="发送"
            >
              <el-icon :size="16"><Promotion /></el-icon>
              <span>发送</span>
            </button>
          </div>
        </div>

        <!-- Online users side panel -->
        <ChatOnlineUsers :users="users" />
      </div>
    </div>
        </div><!-- end chat-content-wrap -->
      </Transition>
    </div><!-- end chat-main-wrap -->
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown, ArrowUp, Promotion, UserFilled } from '@element-plus/icons-vue'
import { useChatRoom } from '@/composables/useChatRoom'
import ChatToolbar from './chatroom/ChatToolbar.vue'
import ChatOnlineUsers from './chatroom/ChatOnlineUsers.vue'
import ChatGroupPicker from './chatroom/ChatGroupPicker.vue'

const chatMainRef = ref<HTMLElement | null>(null)

const {
  groups,
  users,
  activeGroup,
  messages,
  draft,
  showJumpBottom,
  hasMoreOlder,
  noMoreOlder,
  loadingOlder,
  loaded,
  canSendAlert,
  onlineCount,
  selectGroup,
  loadMoreHistory,
  doSend,
  sendAlert,
  onScroll,
  scrollToBottom,
  isCompact,
  formatTime,
} = useChatRoom(chatMainRef)
</script>

<style scoped>
/* ─── Page layout ───────────────────────────────────────── */
.chat-page {
  position: relative;
  height: 100%;
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

/* ─── Placeholder: group picker container ────────────────── */
.chat-placeholder {
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
.chat-placeholder::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(119,181,254,0.04) 45%, rgba(239,183,186,0.08));
  pointer-events: none;
}
:global(.dark) .chat-placeholder {
  background: rgba(15, 23, 42, 0.60);
  border-color: rgba(119, 181, 254, 0.10);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.30), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

/* ─── Glass card (main chat area) ───────────────────────── */
.chat-glass-card {
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
.chat-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .chat-glass-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Shimmer line (matches WelcomeCard) */
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

/* ─── Chat wrapper grid ─────────────────────────────────── */
.chat-wrapper {
  display: grid;
  grid-template-columns: 1fr 220px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.chat-wrapper > :last-child {
  border-left: 1px solid rgba(119, 181, 254, 0.10);
}

/* ─── Left: message list + input ───────────────────────── */
.chat-left {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.chat-main {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 16px 20px 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(119, 181, 254, 0.25) transparent;
}
.chat-main::-webkit-scrollbar { width: 5px; }
.chat-main::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(119,181,254,0.40), rgba(167,139,250,0.35));
  border-radius: 3px;
}
.chat-main::-webkit-scrollbar-track { background: transparent; }

/* ─── Load older ────────────────────────────────────────── */
.load-older {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4px 0 12px;
}
.btn-load-older {
  border-radius: 999px !important;
  background: rgba(119, 181, 254, 0.12) !important;
  border-color: rgba(119, 181, 254, 0.25) !important;
  color: var(--brand-primary) !important;
  font-size: 12px !important;
  padding: 4px 14px !important;
  transition: all 0.2s ease !important;
}
.btn-load-older:hover {
  background: rgba(119, 181, 254, 0.22) !important;
  box-shadow: 0 2px 12px rgba(119, 181, 254, 0.30) !important;
}
.no-more {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.08em;
}

/* ─── Jump-to-bottom FAB (outside scroll area) ──────────── */
.chat-left { position: relative; }
.jump-bottom-fab {
  position: absolute;
  bottom: 72px; /* clears the ~60px input bar */
  right: 20px;
  z-index: 10;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  color: #fff;
  box-shadow:
    0 4px 18px rgba(119, 181, 254, 0.55),
    0 0 0 2px rgba(255, 255, 255, 0.25) inset;
  animation: fab-bounce 2.4s ease-in-out infinite;
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.jump-bottom-fab:hover {
  box-shadow: 0 6px 26px rgba(119, 181, 254, 0.80), 0 0 0 2px rgba(255, 255, 255, 0.35) inset;
  animation: none;
  transform: scale(1.12) translateY(-2px);
}
@keyframes fab-bounce {
  0%, 100% { transform: translateY(0); box-shadow: 0 4px 18px rgba(119,181,254,0.55), 0 0 0 2px rgba(255,255,255,0.25) inset; }
  50%       { transform: translateY(-5px); box-shadow: 0 8px 28px rgba(119,181,254,0.75), 0 0 0 2px rgba(255,255,255,0.30) inset; }
}
/* FAB pop transition */
.fab-pop-enter-active { transition: opacity 0.22s ease, transform 0.22s cubic-bezier(.34,1.56,.64,1); }
.fab-pop-leave-active { transition: opacity 0.16s ease, transform 0.16s ease; }
.fab-pop-enter-from   { opacity: 0; transform: scale(0.5) translateY(8px); }
.fab-pop-leave-to     { opacity: 0; transform: scale(0.8); }

/* ─── Message rows ──────────────────────────────────────── */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 2px;
  padding: 3px 6px;
  border-radius: 12px;
  transition: background 0.18s ease;
}
.msg-row:hover { background: rgba(119, 181, 254, 0.05); }
.msg-row.compact { margin-bottom: 1px; }
.msg-row.compact .avatar-col { opacity: 0; }
.msg-row.is-alert { margin-bottom: 10px; }

/* ─── Avatar ring (source-tinted) ──────────────────────── */
.avatar-col { width: 38px; flex-shrink: 0; }
.avatar-ring {
  border-radius: 50%;
  padding: 2px;
  background: linear-gradient(135deg, rgba(119,181,254,0.5), rgba(167,139,250,0.4));
}
.avatar-ring.ring-game {
  background: linear-gradient(135deg, rgba(34,197,94,0.6), rgba(16,185,129,0.4));
}
.avatar-ring.ring-qq {
  background: linear-gradient(135deg, rgba(251,191,36,0.6), rgba(245,158,11,0.4));
}
.avatar-ring .avatar { display: block; width: 34px; height: 34px; border-radius: 50%; }

/* ─── Bubble ────────────────────────────────────────────── */
.bubble { min-width: 0; max-width: 100%; }
.meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.sender-name {
  font-weight: 700;
  color: var(--brand-primary);
}
.src-game .sender-name { color: #22c55e; }
.src-qq  .sender-name { color: #f59e0b; }
.time { font-size: 11px; color: var(--el-text-color-secondary); }

.content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-text);
}
.content.alert {
  color: #c62828;
  font-weight: 700;
  background: rgba(255, 60, 60, 0.07);
  border: 1px solid rgba(255, 60, 60, 0.20);
  border-radius: 10px;
  padding: 7px 12px;
  display: inline-block;
}
:global(.dark) .content.alert {
  color: #ff8a80;
  background: rgba(255, 60, 60, 0.10);
  border-color: rgba(255, 60, 60, 0.18);
}

/* ─── CQ segments ───────────────────────────────────────── */
.cq-text { white-space: pre-wrap; }
.cq-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  background: rgba(119, 181, 254, 0.10);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 6px;
  margin: 0 3px 3px 0;
  font-size: 12px;
  color: var(--brand-primary);
}
.cq-tag.is-unsupported {
  background: rgba(248, 113, 113, 0.08);
  border-color: rgba(248, 113, 113, 0.18);
  color: #e05252;
}
:global(.dark) .cq-tag { background: rgba(119, 181, 254, 0.12); border-color: rgba(119,181,254,0.20); }
:global(.dark) .cq-tag.is-unsupported { background: rgba(248,113,113,0.12); color: #f87171; }
.cq-reply { display: inline-block; margin: 0 6px 3px 0; color: var(--el-text-color-secondary); font-size: 12px; }
.cq-record-bubble {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(119, 181, 254, 0.07);
  border: 1px solid rgba(119, 181, 254, 0.15);
  border-radius: 16px;
  padding: 5px 12px;
  margin: 4px 0;
}
.cq-audio { width: 160px; height: 28px; }
.cq-share { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 3px 6px 3px 0; }
.cq-share a { color: var(--brand-primary); text-decoration: none; font-size: 13px; }
.cq-share a:hover { text-decoration: underline; }
.cq-share-title { font-size: 12px; color: var(--el-text-color-secondary); }
.cq-image-link { display: inline-block; margin: 6px 8px 4px 0; }
.cq-image {
  max-width: 220px;
  max-height: 220px;
  border-radius: 10px;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12);
  object-fit: cover;
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1), box-shadow 0.2s ease;
}
.cq-image:hover {
  transform: scale(1.03);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.20);
}
.cq-data {
  display: inline-block;
  margin: 4px 6px 4px 0;
  background: rgba(119, 181, 254, 0.06);
  border: 1px solid rgba(119, 181, 254, 0.14);
  border-radius: 10px;
  padding: 5px 10px;
}
.cq-data summary { cursor: pointer; color: var(--brand-primary); font-size: 13px; }
.cq-data pre {
  margin-top: 6px;
  max-width: 320px;
  max-height: 200px;
  overflow: auto;
  background: rgba(255, 255, 255, 0.70);
  padding: 6px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}
:global(.dark) .cq-data pre { background: rgba(15, 23, 42, 0.80); }

/* ─── Input bar ─────────────────────────────────────────── */
.chat-input {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid rgba(119, 181, 254, 0.10);
  background: rgba(255, 255, 255, 0.40);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
:global(.dark) .chat-input {
  background: rgba(15, 23, 42, 0.40);
}

/* Pill-shaped glass input */
.chat-input .msg-input :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.65) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  padding: 0 14px !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
:global(.dark) .chat-input .msg-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}
.chat-input .msg-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.55) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.82) !important;
}
:global(.dark) .chat-input .msg-input :deep(.el-input__wrapper.is-focus) {
  background: rgba(15, 23, 42, 0.80) !important;
}
.chat-input :deep(.el-input) { flex: 1 1 auto; }

/* Gradient send button */
.btn-send {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 18px;
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
    transform 0.25s cubic-bezier(.34,1.56,.64,1),
    opacity 0.2s ease;
}
.btn-send:hover:not(:disabled) {
  box-shadow: 0 6px 22px rgba(119, 181, 254, 0.65);
  transform: translateY(-1px) scale(1.04);
}
.btn-send:active:not(:disabled) {
  transform: scale(0.97);
  box-shadow: 0 2px 8px rgba(119, 181, 254, 0.30);
}
.btn-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

/* ─── Main wrap: grid lets skeleton & content overlap ─── */
.chat-main-wrap {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
}
.sk-chat-panel,
.chat-content-wrap {
  grid-area: 1 / 1;
  min-height: 0;
}
.chat-content-wrap {
  display: flex;
  flex-direction: column;
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

/* ─── Chat skeleton ─────────────────────────────────── */
.sk-chat-panel {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
:global(.dark) .sk-chat-panel {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
}
.sk-messages {
  flex: 1 1 auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: flex-end;
}
.sk-msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.sk-msg-row.sk-compact { padding-left: 48px; }
.sk-avatar-col { width: 38px; flex-shrink: 0; }
.sk-avatar { width: 34px; height: 34px; border-radius: 50%; }
.sk-bubble-col { flex: 1; display: flex; flex-direction: column; gap: 5px; }
.sk-meta { height: 10px; width: 120px; border-radius: 6px; }
.sk-text { height: 14px; border-radius: 8px; }
.sk-chat-input {
  padding: 12px 16px;
  border-top: 1px solid rgba(119, 181, 254, 0.10);
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.sk-input-box { flex: 1; height: 36px; border-radius: 22px; }
.sk-send-btn { width: 76px; height: 36px; border-radius: 22px; flex-shrink: 0; }

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
