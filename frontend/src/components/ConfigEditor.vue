<template>
  <Teleport to="body">
    <Transition name="ced">
      <div v-if="visible" class="ced-overlay">
        <div class="ced-panel">

          <!-- Shimmer accent -->
          <div class="shimmer-line" aria-hidden="true" />

          <!-- Header -->
          <div class="ced-header">
            <div class="ced-header-left">
              <div class="ced-icon">
                <el-icon :size="14"><Document /></el-icon>
              </div>
              <div class="ced-title-group">
                <span class="ced-title">{{ title }}</span>
                <span class="ced-lang-badge">{{ language.toUpperCase() }}</span>
              </div>
            </div>
            <button class="ced-close" @click="$emit('update:visible', false)" aria-label="关闭">
              <el-icon :size="15"><Close /></el-icon>
            </button>
          </div>

          <!-- Editor body -->
          <div
            class="ced-body"
            v-loading="loading"
            element-loading-text="正在加载配置文件…"
            element-loading-background="rgba(10,17,32,0.75)"
          >
            <codemirror
              v-model="internalContent"
              placeholder="正在加载文件内容..."
              :style="{ height: '100%' }"
              :autofocus="true"
              :indent-with-tab="true"
              :tab-size="2"
              :extensions="extensions"
            />
          </div>

          <!-- Footer -->
          <div class="ced-footer">
            <div class="ced-footer-info">
              <el-icon :size="12" style="color: var(--brand-primary)"><InfoFilled /></el-icon>
              <span>修改将立即保存到服务器</span>
            </div>
            <div class="ced-footer-actions">
              <button class="ced-btn ced-btn-cancel" @click="$emit('update:visible', false)">
                取消
              </button>
              <button class="ced-btn ced-btn-save" :disabled="isSaving" @click="handleSave">
                <el-icon v-if="!isSaving" :size="13"><Check /></el-icon>
                <el-icon v-else :size="13" class="spin"><Loading /></el-icon>
                保存文件
              </button>
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'
import { Document, Close, Check, Loading, InfoFilled } from '@element-plus/icons-vue'

const props = defineProps({
  visible: Boolean,
  loading: Boolean,
  isSaving: Boolean,
  title: { type: String, default: '编辑文件' },
  initialContent: { type: String, default: '' },
  language: { type: String, default: 'text' },
})

const emit = defineEmits(['update:visible', 'save'])

const internalContent = ref('')

const extensions = computed(() => {
  const exts = [oneDark]
  if (props.language === 'yaml') exts.push(yaml())
  return exts
})

watch(
  () => props.initialContent,
  (val) => { if (props.visible) internalContent.value = val }
)

watch(
  () => props.visible,
  (val) => { if (!val) internalContent.value = '' }
)

const handleSave = () => emit('save', internalContent.value)
</script>

<style scoped>
/* ── Overlay ─────────────────────────────────────────────── */
.ced-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}

/* ── Panel ───────────────────────────────────────────────── */
.ced-panel {
  width: 78vw;
  max-width: 1280px;
  height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(10, 17, 32, 0.88);
  -webkit-backdrop-filter: saturate(180%) blur(28px);
  backdrop-filter: saturate(180%) blur(28px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow:
    0 32px 80px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(255, 255, 255, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

/* Shimmer accent line */
.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, var(--brand-primary) 0%, #a78bfa 50%, var(--brand-primary) 100%);
  background-size: 200% 100%;
  animation: shimmer-slide 3s linear infinite;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Header ──────────────────────────────────────────────── */
.ced-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.10);
  background: rgba(255, 255, 255, 0.03);
  flex-shrink: 0;
}
.ced-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ced-icon {
  width: 32px; height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.ced-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ced-title {
  font-size: 14px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.90);
}
.ced-lang-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(119, 181, 254, 0.12);
  border: 1px solid rgba(119, 181, 254, 0.25);
  color: var(--brand-primary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  font-family: 'Maple Mono', monospace;
}

.ced-close {
  width: 30px; height: 30px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.45);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}
.ced-close:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
  color: #ef4444;
}

/* ── Editor body ─────────────────────────────────────────── */
.ced-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.ced-body :deep(.vue-codemirror) {
  height: 100%;
}
.ced-body :deep(.cm-editor) {
  height: 100%;
  font-family: 'Maple Mono', 'Fira Code', monospace;
  font-size: 13px;
}
.ced-body :deep(.cm-scroller) {
  scrollbar-width: thin;
  scrollbar-color: rgba(119, 181, 254, 0.25) transparent;
}
.ced-body :deep(.cm-editor.cm-focused) {
  outline: none;
}

/* ── Footer ──────────────────────────────────────────────── */
.ced-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid rgba(119, 181, 254, 0.10);
  background: rgba(255, 255, 255, 0.02);
  flex-shrink: 0;
  gap: 12px;
}
.ced-footer-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.30);
}
.ced-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Buttons */
.ced-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 18px;
  border-radius: 22px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
  white-space: nowrap;
}
.ced-btn-cancel {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.60);
}
.ced-btn-cancel:hover {
  background: rgba(255, 255, 255, 0.10);
  border-color: rgba(255, 255, 255, 0.22);
  color: rgba(255, 255, 255, 0.85);
}
.ced-btn-save {
  border: none;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  color: #fff;
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.40);
}
.ced-btn-save:not(:disabled):hover {
  box-shadow: 0 6px 22px rgba(119, 181, 254, 0.65);
  transform: translateY(-1px) scale(1.03);
}
.ced-btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── Loading spin ────────────────────────────────────────── */
.spin {
  animation: icon-spin 0.8s linear infinite;
}
@keyframes icon-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* ── Enter / Leave transitions ───────────────────────────── */
.ced-enter-active {
  animation: ced-in 0.28s cubic-bezier(.34, 1.56, .64, 1);
}
.ced-leave-active {
  animation: ced-out 0.18s ease forwards;
}
@keyframes ced-in {
  from { opacity: 0; transform: scale(0.95) translateY(12px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
@keyframes ced-out {
  from { opacity: 1; transform: scale(1); }
  to   { opacity: 0; transform: scale(0.97); }
}
</style>
