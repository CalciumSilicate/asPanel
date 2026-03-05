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
        aria-label="传输"
        title="传输"
        circle
        text
      >
        <el-icon :size="18">
          <Download />
        </el-icon>
      </el-button>
    </el-badge>
    <template #dropdown>
      <el-dropdown-menu class="transfers-menu">
        <el-dropdown-item class="transfers-menu-actions-item">
          <div class="transfers-menu-actions">
            <span class="transfers-menu-header">传输</span>
            <el-button
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
          <div class="transfer-row">
            <div class="transfer-row-header">
              <span class="transfer-name">
                <el-icon v-if="t.type === 'upload'" class="transfer-type-icon"><Upload /></el-icon>
                <el-icon v-else class="transfer-type-icon"><Download /></el-icon>
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
              <el-button size="small" text @click.stop="cancelTransfer(t.id)">取消</el-button>
            </div>
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-if="transfers.length === 0" disabled>暂无传输</el-dropdown-item>
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
.transfers-dropdown { margin-right: 8px; }
.transfers-menu { width: 420px; max-width: min(520px, 92vw); padding: 6px 0; overflow-x: hidden; box-sizing: border-box; }
.transfers-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
}
.transfers-menu-actions { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
.transfers-menu-actions-item { cursor: default; }
.transfers-menu-actions-item:hover { background-color: transparent !important; }
.transfers-menu .transfers-menu-header { font-weight: 600; color: var(--color-text); }
.transfer-row { padding: 10px 14px; display: block; width: 100%; box-sizing: border-box; }
.transfer-row-header { display: grid; grid-template-columns: 1fr auto auto; column-gap: 12px; align-items: baseline; margin-bottom: 4px; }
.transfer-name { font-size: 13px; color: var(--color-text); font-weight: 600; text-align: left; display: flex; align-items: center; gap: 4px; }
.transfer-type-icon { font-size: 14px; color: var(--el-text-color-secondary); flex-shrink: 0; }
.transfer-state, .transfer-percent { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.transfer-row-desc { font-size: 11px; color: var(--el-text-color-secondary); margin: 2px 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.transfer-progress { display: block; width: 96%; margin: 0 auto; }
.transfer-row-actions { display: flex; justify-content: flex-end; padding: 6px 14px 0; }
.transfers-badge :deep(.el-badge__content) { transform: translate(4px, -6px); }
</style>
