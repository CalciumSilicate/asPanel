<template>
  <el-dropdown
    trigger="click"
    class="transfers-dropdown"
    placement="bottom-end"
    :popper-options="dropdownPopperOptions"
    :hide-on-click="false"
  >
    <el-badge
      :value="activeTransfersCount"
      :max="99"
      type="primary"
      :hidden="activeTransfersCount === 0"
      class="transfers-badge"
    >
      <el-button
        class="transfers-toggle"
        aria-label="下载传输"
        title="下载传输"
      >
        <span class="transfers-toggle-glow"></span>
        <span class="transfers-toggle-icon-wrap">
          <el-icon :size="18" class="transfers-toggle-icon">
            <Download />
          </el-icon>
        </span>
        <span class="transfers-toggle-copy">
          <span class="transfers-toggle-label">下载传输</span>
          <span class="transfers-toggle-meta">{{ transfersToggleMeta }}</span>
        </span>
      </el-button>
    </el-badge>
    <template #dropdown>
      <el-dropdown-menu class="transfers-menu">
        <el-dropdown-item class="transfers-menu-actions-item">
          <div class="transfers-menu-actions">
            <div class="transfers-menu-title-group">
              <span class="transfers-menu-icon">
                <el-icon><Download /></el-icon>
              </span>
              <div>
                <span class="transfers-menu-header">下载传输</span>
                <p class="transfers-menu-subtitle">查看文件流转、准备状态与中断操作</p>
              </div>
            </div>
            <el-button
              class="transfers-clear-btn"
              size="small"
              text
              :disabled="clearTransfersDisabled"
              @click.stop="handleClearTransfers"
            >
              清除已完成
            </el-button>
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-for="t in transfers" :key="t.id" class="transfer-menu-item">
          <div class="transfer-row" :class="`is-${t.status.toLowerCase()}`">
            <div class="transfer-row-header">
              <span class="transfer-name">
                <span class="transfer-type-chip">
                  <el-icon v-if="t.type === 'upload'" class="transfer-type-icon"><Upload /></el-icon>
                  <el-icon v-else class="transfer-type-icon"><Download /></el-icon>
                </span>
                {{ t.title }}
              </span>
              <span class="transfer-state">{{ transferStatusLabel(t.status) }}</span>
              <span class="transfer-percent">{{ transferDisplayPercent(t) }}%</span>
            </div>
            <div v-if="transferDesc(t)" class="transfer-row-desc" :title="transferDesc(t)">{{ transferDesc(t) }}</div>
            <el-progress
              v-if="t.status === 'TRANSFERRING' || t.status === 'PREPARING'"
              class="transfer-progress"
              :class="t.status.toLowerCase()"
              :percentage="transferProgressPercent(t)"
              :stroke-width="4"
              :show-text="false"
            />
            <div class="transfer-row-actions" v-if="t.status === 'PREPARING' || t.status === 'TRANSFERRING'">
              <el-button class="transfer-cancel-btn" size="small" text @click.stop="cancelTransfer(t.id)">取消</el-button>
            </div>
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-if="transfers.length === 0" disabled>
          <div class="transfers-empty">暂无传输</div>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Upload } from '@element-plus/icons-vue'
import { useTransfersStore } from '@/store/transfers'
import { storeToRefs } from 'pinia'
import type { TransferItem, TransferStatus } from '@/store/transfers'

const transfersStore = useTransfersStore()
const { transfers, activeTransfersCount, finishedTransfersCount } = storeToRefs(transfersStore)
const { cancelTransfer, clearFinishedTransfers } = transfersStore

const dropdownPopperOptions = {
  modifiers: [
    { name: 'offset', options: { offset: [0, 8] } },
    { name: 'preventOverflow', options: { padding: 8, boundary: 'viewport' } },
    { name: 'flip', options: { fallbackPlacements: ['bottom-end', 'bottom-start', 'top-end', 'top-start'] } },
  ],
}

const clearTransfersDisabled = computed(() => finishedTransfersCount.value === 0)
const transfersToggleMeta = computed(() => {
  if (activeTransfersCount.value > 0) return `${activeTransfersCount.value} 个传输中`
  if (finishedTransfersCount.value > 0) return `${finishedTransfersCount.value} 个已完成`
  return '文件流转'
})

const handleClearTransfers = () => {
  if (clearTransfersDisabled.value) return
  clearFinishedTransfers()
  ElMessage.success('已清理已完成传输')
}

const STATUS_LABELS: Record<TransferStatus, string> = {
  PREPARING: '准备中',
  TRANSFERRING: '传输中',
  SUCCESS: '完成',
  FAILED: '失败',
  CANCELED: '已取消',
}
const transferStatusLabel = (status: TransferStatus): string => STATUS_LABELS[status] || status
const transferDesc = (t: TransferItem): string => t?.error || t?.message || ''
const transferDisplayPercent = (t: TransferItem): number =>
  (t.status === 'SUCCESS' || t.status === 'FAILED' || t.status === 'CANCELED') ? 100 : (t.progress || 0)
const transferProgressPercent = (t: TransferItem): number =>
  (t.status === 'SUCCESS' || t.status === 'FAILED' || t.status === 'CANCELED') ? 100 : (t.progress || 0)
</script>

<style scoped>
.transfers-dropdown {
  margin-right: 10px;
  position: relative;
}

.transfers-toggle {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 5px 14px 5px 6px !important;
  border-radius: 16px !important;
  border: 1px solid rgba(119,181,254,0.18) !important;
  background: rgba(255,255,255,0.5) !important;
  -webkit-backdrop-filter: saturate(160%) blur(16px);
  backdrop-filter: saturate(160%) blur(16px);
  box-shadow:
    0 10px 24px rgba(119,181,254,0.12),
    inset 0 1px 0 rgba(255,255,255,0.85) !important;
  transition:
    transform 0.25s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.25s ease,
    border-color 0.25s ease,
    background 0.25s ease !important;
}

.transfers-toggle:hover {
  transform: translateY(-1px) scale(1.01) !important;
  border-color: rgba(119,181,254,0.28) !important;
  box-shadow:
    0 14px 30px rgba(119,181,254,0.18),
    0 0 0 1px rgba(119,181,254,0.16),
    inset 0 1px 0 rgba(255,255,255,0.92) !important;
}

:global(.dark) .transfers-toggle {
  background: rgba(15,23,42,0.58) !important;
  border-color: rgba(119,181,254,0.14) !important;
  box-shadow:
    0 14px 28px rgba(0,0,0,0.34),
    inset 0 1px 0 rgba(255,255,255,0.04) !important;
}

:global(.dark) .transfers-toggle:hover {
  border-color: rgba(119,181,254,0.24) !important;
  box-shadow:
    0 18px 34px rgba(0,0,0,0.42),
    0 0 0 1px rgba(119,181,254,0.14),
    0 0 22px rgba(119,181,254,0.18) !important;
}

.transfers-toggle-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top left, rgba(119,181,254,0.18), transparent 52%),
    radial-gradient(circle at right center, rgba(239,183,186,0.16), transparent 46%);
  opacity: 0.95;
  pointer-events: none;
}

.transfers-toggle-icon-wrap {
  position: relative;
  z-index: 1;
  width: 30px;
  height: 30px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #40c9c6;
  background: rgba(64,201,198,0.12);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.transfers-toggle-icon {
  filter: drop-shadow(0 0 8px rgba(64,201,198,0.35));
}

.transfers-toggle-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
}

.transfers-toggle-label {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--color-text);
}

.transfers-toggle-meta {
  font-size: 11px;
  line-height: 1.1;
  color: var(--color-text-secondary);
}

.transfers-menu {
  width: 440px;
  max-width: min(540px, 92vw);
  padding: 0;
  overflow-x: hidden;
  box-sizing: border-box;
  border: 1px solid rgba(119,181,254,0.18);
  border-radius: 20px;
  background: rgba(255,255,255,0.78);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  box-shadow:
    0 20px 60px rgba(119,181,254,0.18),
    0 4px 16px rgba(0,0,0,0.06);
}

:global(.dark) .transfers-menu {
  background: rgba(8,14,26,0.92);
  border-color: rgba(119,181,254,0.14);
  box-shadow:
    0 28px 80px rgba(0,0,0,0.72),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

.transfers-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
  border-radius: 16px !important;
  margin: 6px 10px !important;
}

.transfers-menu :deep(.el-dropdown-menu__item:hover) {
  background: rgba(119,181,254,0.08) !important;
}

.transfers-menu-actions {
  position: relative;
  padding: 16px 18px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(119,181,254,0.12);
  margin-bottom: 2px;
}

.transfers-menu-actions::before {
  content: '';
  position: absolute;
  top: 0;
  left: 18px;
  right: 18px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(119,181,254,0.5) 32%, rgba(239,183,186,0.45) 68%, transparent 100%);
}

.transfers-menu-actions-item {
  cursor: default;
}

.transfers-menu-actions-item:hover {
  background-color: transparent !important;
}

.transfers-menu-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.transfers-menu-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(64,201,198,0.12);
  color: #40c9c6;
}

.transfers-menu .transfers-menu-header {
  display: block;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.03em;
  background: linear-gradient(135deg, #77b5fe, #efb7ba);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.transfers-menu-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.transfers-clear-btn,
.transfer-cancel-btn {
  border-radius: 10px;
  border: 1px solid rgba(119,181,254,0.2);
  background: rgba(128,128,128,0.06);
  color: var(--color-text-secondary);
  padding: 0 12px;
}

.transfers-clear-btn:hover,
.transfer-cancel-btn:hover {
  color: var(--brand-primary);
  border-color: rgba(119,181,254,0.28);
  background: rgba(119,181,254,0.08);
}

.transfer-row {
  position: relative;
  overflow: hidden;
  padding: 14px 14px 12px;
  display: block;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(119,181,254,0.1);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.36), rgba(64,201,198,0.06));
}

:global(.dark) .transfer-row {
  background: linear-gradient(180deg, rgba(18,28,46,0.74), rgba(10,16,32,0.92));
  border-color: rgba(119,181,254,0.1);
}

.transfer-row::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  border-radius: 16px 0 0 16px;
  background: linear-gradient(180deg, rgba(64,201,198,0.95), rgba(119,181,254,0.78));
  opacity: 0;
  transition: opacity 0.22s ease;
}

.transfer-row.is-preparing::before,
.transfer-row.is-transferring::before,
.transfer-row.is-failed::before,
.transfer-row.is-success::before {
  opacity: 1;
}

.transfer-row-header {
  display: grid;
  grid-template-columns: 1fr auto auto;
  column-gap: 12px;
  align-items: baseline;
  margin-bottom: 4px;
}

.transfer-name {
  font-size: 13px;
  color: var(--color-text);
  font-weight: 600;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
}

.transfer-type-chip {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(64,201,198,0.12);
  flex-shrink: 0;
}

.transfer-type-icon {
  font-size: 13px;
  color: #40c9c6;
  flex-shrink: 0;
}

.transfer-state {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-align: right;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(119,181,254,0.08);
}

.transfer-percent {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.transfer-row-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 6px 0 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.transfer-progress {
  display: block;
  width: 100%;
  margin: 0;
}

.transfer-progress :deep(.el-progress-bar__outer) {
  background: rgba(119,181,254,0.1) !important;
  border-radius: 99px !important;
}

.transfer-progress :deep(.el-progress-bar__inner) {
  border-radius: 99px !important;
  box-shadow: 0 0 8px currentColor;
}

.transfer-row-actions {
  display: flex;
  justify-content: flex-end;
  padding: 10px 0 0;
}

.transfers-empty {
  padding: 18px 16px;
  text-align: center;
  color: var(--color-text-secondary);
}

.transfers-badge :deep(.el-badge__content) {
  transform: translate(6px, -6px);
  border: none;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #40c9c6, #77b5fe);
  box-shadow: 0 6px 14px rgba(64,201,198,0.3);
}

@media (max-width: 900px) {
  .transfers-toggle {
    padding-right: 10px !important;
  }

  .transfers-toggle-copy {
    display: none;
  }

  .transfers-menu {
    width: min(92vw, 440px);
  }
}
</style>
