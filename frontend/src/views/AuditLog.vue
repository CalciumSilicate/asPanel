<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="header-bar">
          <div class="flex items-center header-title">
            <el-icon style="margin-right:6px;font-size:18px;"><Tickets/></el-icon>
            <span class="text-base font-medium">审计日志</span>
            <el-tag type="info" class="title-count">共 {{ total }} 条</el-tag>
          </div>
          <div class="header-actions">
            <el-button :icon="Refresh" @click="load" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-select
          v-model="filters.category"
          clearable
          placeholder="分类"
          style="width:120px"
          @change="onFilterChange"
        >
          <el-option
            v-for="c in categories"
            :key="c.value"
            :label="c.label"
            :value="c.value"
          />
        </el-select>

        <el-input
          v-model="filters.action"
          clearable
          placeholder="动作关键字"
          style="width:150px"
          @change="onFilterChange"
        />

        <el-input
          v-model="filters.actor_name"
          clearable
          placeholder="操作人"
          style="width:130px"
          @change="onFilterChange"
        />

        <el-input
          v-model="filters.target_name"
          clearable
          placeholder="对象名称"
          style="width:130px"
          @change="onFilterChange"
        />

        <el-select
          v-model="filters.result"
          clearable
          placeholder="结果"
          style="width:100px"
          @change="onFilterChange"
        >
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failure" />
        </el-select>

        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          range-separator="~"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width:360px"
          @change="onFilterChange"
        />

        <el-button @click="resetFilters" :icon="Delete" plain>重置</el-button>
      </div>

      <!-- 数据表格 -->
      <div class="table-wrap">
      <el-table
        :data="rows"
        v-loading="loading"
        stripe
        size="small"
        height="100%"
        style="width:100%"
        row-key="id"
        :expand-row-keys="expandedIds"
        @expand-change="handleExpandChange"
      >
        <!-- 展开行：显示 detail JSON -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail-expand">
              <div v-if="row.error_msg" class="error-msg">
                <el-icon><WarningFilled/></el-icon>
                <span>{{ row.error_msg }}</span>
              </div>
              <template v-if="row.detail && typeof row.detail === 'object' && Object.keys(row.detail).length">
                <div class="detail-title">详细信息</div>
                <pre class="detail-json">{{ JSON.stringify(row.detail, null, 2) }}</pre>
              </template>
              <template v-else-if="row.detail && typeof row.detail === 'string'">
                <div class="detail-title">详细信息</div>
                <pre class="detail-json">{{ row.detail }}</pre>
              </template>
              <span v-else class="no-detail">无附加信息</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="170" prop="ts">
          <template #default="{ row }">
            <span class="mono">{{ row.ts ? row.ts.replace('T', ' ').substring(0, 19) : '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="分类" width="90" prop="category">
          <template #default="{ row }">
            <el-tag :type="categoryTagType(row.category)" size="small" disable-transitions>
              {{ categoryLabel(row.category) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="动作" width="150" prop="action">
          <template #default="{ row }">
            <span class="action-text">{{ row.action }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作人" width="130" prop="actor_name">
          <template #default="{ row }">
            <span v-if="row.actor_name" class="actor">{{ row.actor_name }}</span>
            <el-tag v-else type="info" size="small" plain>系统</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="IP" width="130" prop="ip_address">
          <template #default="{ row }">
            <span class="mono">{{ row.ip_address || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="对象" min-width="160">
          <template #default="{ row }">
            <template v-if="row.target_type || row.target_name">
              <el-tag type="info" size="small" plain style="margin-right:4px" v-if="row.target_type">
                {{ row.target_type }}
              </el-tag>
              <span v-if="row.target_name">{{ row.target_name }}</span>
              <span v-if="row.target_id" class="target-id"> #{{ row.target_id }}</span>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="结果" width="80" align="center" prop="result">
          <template #default="{ row }">
            <el-tag
              :type="row.result === 'success' ? 'success' : 'danger'"
              size="small"
              disable-transitions
            >
              {{ row.result === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="load"
          @size-change="() => { page = 1; load() }"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Delete, Tickets, WarningFilled } from '@element-plus/icons-vue'
import { fetchAuditLogs, fetchAuditCategories, type AuditLogItem, type CategoryOption } from '@/api/audit'

// ——— 数据 ———
const loading = ref(false)
const rows = ref<AuditLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const categories = ref<CategoryOption[]>([])
const expandedIds = ref<string[]>([])

const timeRange = ref<[string, string] | null>(null)

const filters = reactive({
  category: '',
  action: '',
  actor_name: '',
  target_name: '',
  result: '',
})

// ——— 分类映射 ———
const CATEGORY_MAP: Record<string, string> = {
  SYSTEM:   '系统',
  AUTH:     '认证',
  USER:     '用户',
  SERVER:   '服务器',
  PLAYER:   '玩家',
  PLUGIN:   '插件',
  ARCHIVE:  '存档',
  SETTINGS: '设置',
}

const CATEGORY_TAG_TYPE: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
  SYSTEM:   'info',
  AUTH:     '',
  USER:     'warning',
  SERVER:   'success',
  PLAYER:   '',
  PLUGIN:   'warning',
  ARCHIVE:  'info',
  SETTINGS: 'danger',
}

function categoryLabel(cat: string): string {
  return CATEGORY_MAP[cat] ?? cat
}

function categoryTagType(cat: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  return CATEGORY_TAG_TYPE[cat] ?? 'info'
}

// ——— 加载 ———
async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filters.category) params.category = filters.category
    if (filters.action) params.action = filters.action
    if (filters.actor_name) params.actor_name = filters.actor_name
    if (filters.target_name) params.target_name = filters.target_name
    if (filters.result) params.result = filters.result
    if (timeRange.value?.[0]) params.start_ts = timeRange.value[0]
    if (timeRange.value?.[1]) params.end_ts = timeRange.value[1]

    const res = await fetchAuditLogs(params as any)
    rows.value = res.items
    total.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '加载失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  load()
}

function resetFilters() {
  filters.category = ''
  filters.action = ''
  filters.actor_name = ''
  filters.target_name = ''
  filters.result = ''
  timeRange.value = null
  page.value = 1
  load()
}

function handleExpandChange(_row: AuditLogItem, expanded: AuditLogItem[]) {
  expandedIds.value = expanded.map(r => String(r.id))
}

onMounted(async () => {
  try {
    categories.value = await fetchAuditCategories()
  } catch {
    // 静默，不影响主功能
  }
  load()
})
</script>

<style scoped>
.page {
  padding: 16px;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.page > .el-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  margin-top: 12px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-count {
  margin-left: 8px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0 4px;
}

.mono {
  font-family: monospace;
  font-size: 12px;
}

.action-text {
  font-family: monospace;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.actor {
  font-weight: 500;
}

.target-id {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  font-family: monospace;
}

/* 展开行样式 */
.detail-expand {
  padding: 12px 24px;
}

.detail-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.detail-json {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 10px 14px;
  font-size: 12px;
  font-family: 'Fira Code', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
  color: var(--el-text-color-regular);
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-color-danger);
  font-size: 13px;
  margin-bottom: 8px;
}

.no-detail {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
</style>
