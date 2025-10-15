<template>
  <div class="statistics-view">
    <el-row :gutter="16">
      <!-- 左：排行榜 -->
      <el-col :xs="24" :lg="7">
        <el-card shadow="never" class="rank-card">
          <template #header>
            <div class="card-header">排行榜（数据源与指标同步右侧选择）</div>
          </template>
          <el-form :inline="true" label-width="66px" class="mini-form">
            <el-form-item label="时刻">
              <el-date-picker v-model="rankAt" type="datetime" placeholder="默认当前" style="width: 200px" />
            </el-form-item>
            <el-form-item>
              <el-button size="small" @click="refreshRanks">刷新</el-button>
            </el-form-item>
          </el-form>

          <el-tabs v-model="rankTab" class="rank-tabs">
            <el-tab-pane label="总量榜(时刻)" name="total">
              <el-table :data="rankTotal" size="small" height="280" style="width:100%" empty-text="暂无数据">
                <el-table-column type="index" width="48" />
                <el-table-column prop="player_name" label="玩家" min-width="120">
                  <template #default="scope">{{ scope.row.player_name || shortUuid(scope.row.player_uuid) }}</template>
                </el-table-column>
                <el-table-column prop="value" label="值" width="100" align="right" />
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="增量榜(区间)" name="delta">
              <el-table :data="rankDelta" size="small" height="280" style="width:100%" empty-text="暂无数据">
                <el-table-column type="index" width="48" />
                <el-table-column prop="player_name" label="玩家" min-width="120">
                  <template #default="scope">{{ scope.row.player_name || shortUuid(scope.row.player_uuid) }}</template>
                </el-table-column>
                <el-table-column prop="value" label="值" width="100" align="right" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>

      <!-- 右：筛选 + 统计视图 -->
      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" label-width="66px" class="filter-form">
            <el-form-item label="玩家">
              <el-select v-model="selectedPlayers" multiple filterable collapse-tags placeholder="选择玩家" style="min-width: 280px">
                <el-option v-for="p in players" :key="p.uuid" :label="p.player_name ? `${p.player_name} (${p.uuid.slice(0,8)})` : p.uuid" :value="p.uuid"/>
              </el-select>
            </el-form-item>
            <el-form-item label="指标">
              <el-select v-model="selectedMetrics" multiple filterable remote reserve-keyword :remote-method="searchMetrics" :loading="metricsLoading" collapse-tags placeholder="输入以搜索指标" style="min-width: 320px">
                <el-option v-for="m in metricOptions" :key="m" :label="m" :value="m"/>
              </el-select>
            </el-form-item>
            <el-form-item label="数据源">
              <el-select v-model="selectedServerIds" multiple filterable collapse-tags placeholder="选择服务器" style="min-width: 240px">
                <el-option v-for="s in servers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="粒度">
              <el-select v-model="granularity" style="width: 130px">
                <el-option v-for="g in granularities" :key="g" :label="g" :value="g"/>
              </el-select>
            </el-form-item>
            <el-form-item label="时间">
              <el-date-picker v-model="range" type="datetimerange" range-separator="到" start-placeholder="开始时间" end-placeholder="结束时间" style="min-width: 340px"/>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="queryStats" :disabled="!canQuery">查询</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-row :gutter="16" class="kpi-row">
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">玩家数量</div><div class="kpi-value">{{ selectedPlayers.length }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">指标数</div><div class="kpi-value">{{ selectedMetrics.length }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">区间合计(Δ)</div><div class="kpi-value">{{ totalDeltaSum }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">末值合计(Total)</div><div class="kpi-value">{{ totalLastTotal }}</div></el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><div class="card-header">Δ Delta 趋势</div></template>
              <div ref="deltaChartRef" class="chart"></div>
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><div class="card-header">Total 累计趋势</div></template>
              <div ref="totalChartRef" class="chart"></div>
            </el-card>
          </el-col>
        </el-row>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '@/api'
import { fetchDeltaSeries, fetchTotalSeries, fetchMetrics, fetchLeaderboardTotal, fetchLeaderboardDelta } from '@/api/stats'
import { loadECharts } from '@/utils/echartsLoader'

const players = ref<any[]>([])
const servers = ref<any[]>([])
const selectedPlayers = ref<string[]>([])
const selectedServerIds = ref<number[]>([])

const metricOptions = ref<string[]>([])
const metricsLoading = ref(false)
const selectedMetrics = ref<string[]>([])
const granularities = ['10min', '30min', '1h', '12h', '24h', '1week', '1month', '6month', '1year']
const granularity = ref<string>('10min')
const range = ref<[Date, Date] | null>(null)

const rankTab = ref<'total'|'delta'>('total')
const rankAt = ref<Date | null>(null)
const rankTotal = ref<any[]>([])
const rankDelta = ref<any[]>([])

const deltaChartRef = ref<HTMLElement | null>(null)
const totalChartRef = ref<HTMLElement | null>(null)
let deltaChart: any = null
let totalChart: any = null

const canQuery = computed(() => selectedPlayers.value.length > 0 && selectedMetrics.value.length > 0)

const totalDeltaSum = ref<number>(0)
const totalLastTotal = ref<number>(0)

async function ensureCharts() {
  const echarts = await loadECharts()
  if (deltaChartRef.value && !deltaChart) deltaChart = echarts.init(deltaChartRef.value)
  if (totalChartRef.value && !totalChart) totalChart = echarts.init(totalChartRef.value)
}

function tsToLabel(ts: number): string {
  const d = new Date(ts * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function shortUuid(u: string): string { return (u||'').slice(0,8) }
function showName(u: string): string {
  const p = players.value.find((x:any) => x.uuid === u)
  return p?.player_name || shortUuid(u)
}

function buildSeriesOption(dict: Record<string, [number, number][]>, type: 'line'|'bar') {
  const uuids = Object.keys(dict)
  const allTs = new Set<number>()
  uuids.forEach(u => dict[u].forEach(([t]) => allTs.add(t)))
  const xTs = Array.from(allTs).sort((a,b)=>a-b)
  const xLabels = xTs.map(tsToLabel)
  const series = uuids.map(u => {
    const map = new Map<number, number>()
    dict[u].forEach(([t, v]) => map.set(t, Number(v||0)))
    return { name: showName(u), type, smooth: type==='line', symbol: 'none', data: xTs.map(ts => map.get(ts) ?? 0) }
  })
  return { tooltip: { trigger: 'axis' }, legend: { type: 'scroll' }, grid: { left: 40, right: 20, top: 40, bottom: 40 }, xAxis: { type: 'category', data: xLabels }, yAxis: { type: 'value', scale: true }, series }
}

function toIso(d?: Date) { return d ? new Date(d).toISOString().slice(0,19) : undefined }

async function queryStats() {
  if (!canQuery.value) return
  await ensureCharts()
  const [start, end] = (range.value || []) as any
  const base = { player_uuid: selectedPlayers.value, metric: selectedMetrics.value, granularity: granularity.value, start: toIso(start), end: toIso(end), namespace: 'minecraft', server_id: selectedServerIds.value }
  const [deltaDict, totalDict] = await Promise.all([ fetchDeltaSeries(base), fetchTotalSeries(base) ])
  totalDeltaSum.value = Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0)
  totalLastTotal.value = Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0)
  deltaChart && deltaChart.setOption(buildSeriesOption(deltaDict, 'bar'), true)
  totalChart && totalChart.setOption(buildSeriesOption(totalDict, 'line'), true)
  refreshRanks()
}

function resetFilters() {
  selectedPlayers.value = []
  selectedMetrics.value = []
  selectedServerIds.value = []
  granularity.value = '10min'
  range.value = null
  totalDeltaSum.value = 0
  totalLastTotal.value = 0
  metricOptions.value = []
}

async function fetchPlayers() {
  try {
    const res = await apiClient.get('/api/players')
    players.value = Array.isArray(res.data) ? res.data : []
  } catch { players.value = [] }
}

async function fetchServers() {
  try {
    const res = await apiClient.get('/api/servers')
    servers.value = Array.isArray(res.data) ? res.data : []
  } catch { servers.value = [] }
}

async function searchMetrics(query: string) {
  metricsLoading.value = true
  try {
    metricOptions.value = query ? await fetchMetrics(query, 50, 'minecraft') : []
  } finally { metricsLoading.value = false }
}

async function refreshRanks() {
  const [start, end] = (range.value || []) as any
  const atIso = rankAt.value ? toIso(rankAt.value) : toIso(end)
  const base = { metric: selectedMetrics.value, server_id: selectedServerIds.value, namespace: 'minecraft' }
  const [r1, r2] = await Promise.all([
    fetchLeaderboardTotal({ ...base, at: atIso, limit: 10 }),
    fetchLeaderboardDelta({ ...base, start: toIso(start), end: toIso(end), limit: 10 }),
  ])
  rankTotal.value = r1
  rankDelta.value = r2
}

onMounted(() => { fetchPlayers(); fetchServers() })
</script>

<style scoped>
.statistics-view { display: flex; flex-direction: column; gap: 16px; }
.filter-card { border-radius: 8px; }
.filter-form { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.mini-form { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.kpi-row { margin-top: 6px; }
.kpi-card { text-align: center; border-radius: 8px; }
.kpi-title { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 600; }
.chart-card { border-radius: 8px; }
.chart { width: 100%; height: 320px; }
.rank-card :deep(.el-table__inner-wrapper) { border-radius: 6px; }
</style>

