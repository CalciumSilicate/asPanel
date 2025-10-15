<template>
  <div class="statistics-view">
    <!-- 顶栏：标题 + 数据来源 + 指标（默认 custom.play_time / custom.play_one_minute） -->
    <div class="topbar">
      <div class="topbar-title">数据统计</div>
      <div class="topbar-actions">
        <el-popover placement="bottom-start" trigger="click" width="280">
          <template #reference>
            <el-button class="btn-scope-like" type="primary">数据来源 ({{ selectedServerNames.length }})</el-button>
          </template>
          <el-checkbox-group v-model="selectedServerNames" @change="onServersSelectionChange" class="server-checkboxes">
            <el-checkbox v-for="s in serverNames" :key="s" :label="s">{{ s }}</el-checkbox>
          </el-checkbox-group>
        </el-popover>
        <el-select v-model="selectedMetrics" multiple filterable remote :remote-method="searchMetrics" :loading="metricsLoading" collapse-tags placeholder="输入以搜索指标" style="min-width: 320px">
          <el-option v-for="m in metricOptions" :key="m" :label="m" :value="m"/>
        </el-select>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 左：排行榜 -->
      <el-col :xs="24" :lg="7">
        <el-card shadow="never" class="rank-card">
          <template #header>
            <div class="card-header">排行榜</div>
          </template>

          <div class="mini-form">
            <div class="mode-switch">
              <el-radio-group v-model="rankMode">
                <el-radio-button label="total">总量</el-radio-button>
                <el-radio-button label="delta" :disabled="!zoomRangeReady">增量</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <!-- 横向柱状图 + 纵向滑动选择范围 -->
          <div ref="rankChartRef" class="rank-chart"></div>
          <div class="rank-hint">
            <template v-if="rankMode==='total'">提示：点击右侧“Total”图表选择时刻以生成总量榜。</template>
            <template v-else>提示：在右侧图表底部滑块选择时间段以生成增量榜。</template>
          </div>
        </el-card>
      </el-col>

      <!-- 右：筛选 + 统计视图 -->
      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" label-width="66px" class="filter-form">
            <el-form-item label="粒度">
              <el-select v-model="granularity" style="width: 130px">
                <el-option v-for="g in granularities" :key="g" :label="g" :value="g"/>
              </el-select>
            </el-form-item>
            <el-form-item label="玩家">
              <el-select v-model="selectedPlayers" multiple filterable remote :remote-method="searchPlayers" :loading="playersLoading" collapse-tags placeholder="输入以搜索玩家" style="min-width: 320px">
                <el-option v-for="opt in playerOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>

        <el-row :gutter="16" class="kpi-row">
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">玩家数量</div><div class="kpi-value">{{ Math.min(5, rankItems.length || 0) }}</div></el-card>
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
import { ref, computed, onMounted, watch } from 'vue'
import apiClient from '@/api'
import { fetchDeltaSeries, fetchTotalSeries, fetchMetrics, fetchLeaderboardTotal, fetchLeaderboardDelta } from '@/api/stats'
import { loadECharts } from '@/utils/echartsLoader'

const players = ref<any[]>([])
const servers = ref<any[]>([])
const serverNames = computed(() => servers.value.map((s:any) => (s.path?.split('/').pop()) || s.name))
const selectedServerNames = ref<string[]>([])
const selectedServerIds = ref<number[]>([])
// 选中的玩家 UUID 列表（用于右侧图表与筛选）
const selectedPlayers = ref<string[]>([])

// 玩家远程搜索
const playersLoading = ref(false)
const playerOptions = ref<{label:string,value:string}[]>([])

const metricOptions = ref<string[]>([])
const metricsLoading = ref(false)
const selectedMetrics = ref<string[]>(['custom.play_time','custom.play_one_minute'])
const granularities = ['10min', '30min', '1h', '12h', '24h', '1week', '1month', '6month', '1year']
const granularity = ref<string>('10min')
const range = ref<[Date, Date] | null>(null)

const rankMode = ref<'total'|'delta'>('total')
const rankAtTs = ref<number | null>(null) // 由右侧 Total 图点击选择
const rankChartRef = ref<HTMLElement | null>(null)
let rankChart: any = null

const deltaChartRef = ref<HTMLElement | null>(null)
const totalChartRef = ref<HTMLElement | null>(null)
let deltaChart: any = null
let totalChart: any = null

const canQuery = computed(() => selectedMetrics.value.length > 0)

const totalDeltaSum = ref<number>(0)
const totalLastTotal = ref<number>(0)

let currentDeltaXTimestamps: number[] = []
let currentTotalXTimestamps: number[] = []
let currentZoomRange: {startTs?: number, endTs?: number} = {}


async function ensureCharts() {
  const echarts = await loadECharts()
  if (deltaChartRef.value && !deltaChart) deltaChart = echarts.init(deltaChartRef.value)
  if (totalChartRef.value && !totalChart) totalChart = echarts.init(totalChartRef.value)
  if (rankChartRef.value && !rankChart) rankChart = echarts.init(rankChartRef.value)
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

async function searchPlayers(query: string) {
  playersLoading.value = true
  try {
    const q = (query || '').toLowerCase()
    const list = players.value.filter((p:any) => (p.player_name||'').toLowerCase().includes(q) || (p.uuid||'').toLowerCase().includes(q))
    playerOptions.value = list.slice(0,50).map((p:any) => ({ label: p.player_name ? `${p.player_name} (${p.uuid.slice(0,8)})` : p.uuid, value: p.uuid }))
  } finally { playersLoading.value = false }
}

const STEP_SECONDS: Record<string, number> = { '10min':600, '30min':1800, '1h':3600, '12h':43200, '24h':86400, '1week':604800, '1month':2629800, '6month':15778800, '1year':31557600 }

function fillGaps(dict: Record<string, [number, number][]>, gran: string, mode: 'delta'|'total') {
  const step = STEP_SECONDS[gran] || 600
  // 找到全局最小/最大 ts
  let minTs = Number.MAX_SAFE_INTEGER, maxTs = 0
  for (const arr of Object.values(dict)) {
    if (!arr.length) continue
    minTs = Math.min(minTs, arr[0][0])
    maxTs = Math.max(maxTs, arr[arr.length-1][0])
  }
  if (!isFinite(minTs) || maxTs <= 0) return { dict, xTs: [] }
  const xTs: number[] = []
  for (let t = minTs; t <= maxTs; t += step) xTs.push(t)

  const out: Record<string, [number, number][]> = {}
  for (const [uuid, arr] of Object.entries(dict)) {
    const map = new Map<number, number>(arr.map(([t,v]) => [t, Number(v||0)]))
    const series: [number, number][] = []
    let prevNonZero = 0
    for (const t of xTs) {
      let v = map.get(t)
      if (v == null) {
        if (mode === 'delta') v = 0
        else v = prevNonZero
      }
      if (mode === 'total' && (v||0) !== 0) prevNonZero = v as number
      series.push([t, v as number])
    }
    out[uuid] = series
  }
  return { dict: out, xTs }
}

function buildSeriesOption(dict: Record<string, [number, number][]>, type: 'line'|'bar', gran: string, which: 'delta'|'total') {
  const { dict: filled, xTs } = fillGaps(dict, gran, which)
  const xLabels = xTs.map(tsToLabel)
  const series = Object.keys(filled).map(u => ({
    name: showName(u),
    type,
    smooth: type==='line',
    symbol: 'none',
    data: filled[u].map(([,v]) => v),
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll' },
    grid: [{ left: 56, right: 20, top: 28, height: 220, containLabel: true }],
    xAxis: [{ type: 'category', data: xLabels }],
    yAxis: [{ type: 'value', scale: true }],
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 4 },
    ],
    series,
    _xTs: xTs,
  }
}

function toIso(d?: Date) { return d ? new Date(d).toISOString().slice(0,19) : undefined }

async function queryStatsForTopPlayers() {
  // 依据当前排行榜前五名作为右图玩家，自动查询与渲染
  if (!canQuery.value) return
  await ensureCharts()
  let topUuids = selectedPlayers.value.slice(0,5)
  if (topUuids.length === 0) {
    topUuids = rankItems.value.map((x:any)=>x.player_uuid).filter(Boolean).slice(0,5)
  }
  if (topUuids.length === 0) {
    // 回退：玩家列表前 5 个
    topUuids = players.value.slice(0,5).map((p:any)=>p.uuid)
  }
  if (topUuids.length === 0) return
  const base = { player_uuid: topUuids, metric: selectedMetrics.value, granularity: granularity.value, namespace: 'minecraft', server_id: selectedServerIds.value }
  const [deltaDict, totalDict] = await Promise.all([ fetchDeltaSeries(base), fetchTotalSeries(base) ])
  totalDeltaSum.value = Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0)
  totalLastTotal.value = Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0)

  const deltaOpt: any = buildSeriesOption(deltaDict, 'bar', granularity.value, 'delta')
  const totalOpt: any = buildSeriesOption(totalDict, 'line', granularity.value, 'total')

  deltaChart && deltaChart.setOption(deltaOpt, true)
  totalChart && totalChart.setOption(totalOpt, true)
  currentDeltaXTimestamps = deltaOpt._xTs
  currentTotalXTimestamps = totalOpt._xTs

  totalChart && totalChart.off('click')
  totalChart && totalChart.on('click', (params:any) => {
    const idx = params?.dataIndex
    if (typeof idx === 'number' && currentTotalXTimestamps[idx]) {
      rankAtTs.value = currentTotalXTimestamps[idx]
      if (rankMode.value === 'total') refreshRanks(true)
    }
  })
  const onZoom = (chart:any, which:'delta'|'total') => () => {
    const xArr = which==='delta' ? currentDeltaXTimestamps : currentTotalXTimestamps
    const dz = (chart.getOption().dataZoom||[])[0]
    const startValue = dz.startValue ?? Math.round(dz.start/100*(xArr.length-1))
    const endValue = dz.endValue ?? Math.round(dz.end/100*(xArr.length-1))
    currentZoomRange = { startTs: xArr[startValue], endTs: xArr[endValue] }
    if (rankMode.value === 'delta' && currentZoomRange.startTs && currentZoomRange.endTs) {
      refreshRanks(false)
    }
  }
  deltaChart && (deltaChart.off('dataZoom'), deltaChart.on('dataZoom', onZoom(deltaChart,'delta')))
  totalChart && (totalChart.off('dataZoom'), totalChart.on('dataZoom', onZoom(totalChart,'total')))
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
    // 默认全选（先赋值，后尝试从服务器取上次保存的选择覆盖）
    selectedServerNames.value = serverNames.value.slice()
    try {
      const saved = await apiClient.get('/api/players/data-source-selection')
      const lst: string[] = Array.isArray(saved.data) ? saved.data : []
      const set = new Set(serverNames.value)
      const picked = lst.filter(x => set.has(String(x)))
      if (picked.length > 0) selectedServerNames.value = picked
    } catch {}
    computeSelectedServerIds()
  } catch { servers.value = [] }
}

function computeSelectedServerIds() {
  const nameToId = new Map<string, number>()
  servers.value.forEach((s:any) => nameToId.set((s.path?.split('/').pop()) || s.name, Number(s.id)))
  selectedServerIds.value = selectedServerNames.value.map(n => nameToId.get(n)!).filter(Boolean)
}

async function onServersSelectionChange() {
  computeSelectedServerIds()
  try { await apiClient.patch('/api/players/data-source-selection', { servers: selectedServerNames.value }) } catch {}
  // 自动刷新排行榜/曲线
  if (canQuery.value) await refreshRanks(false)
}

async function searchMetrics(query: string) {
  metricsLoading.value = true
  try {
    metricOptions.value = query ? await fetchMetrics(query, 50, 'minecraft') : []
  } finally { metricsLoading.value = false }
}

let rankRefreshTimer: any = null
const rankItems = ref<any[]>([])
const zoomRangeReady = computed(() => !!currentZoomRange.startTs && !!currentZoomRange.endTs)


async function drawRankChart(items: any[]) {
  const echarts = await loadECharts()
  if (!rankChartRef.value) return
  if (!rankChart) rankChart = echarts.init(rankChartRef.value)
  rankItems.value = items || []
  const names = items.map(it => it.player_name || shortUuid(it.player_uuid))
  const vals = items.map(it => Number(it.value||0))
  const option = {
    grid: { left: 56, right: 24, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names, inverse: true },
    dataZoom: [{ type: 'inside', yAxisIndex: 0 }, { type: 'slider', yAxisIndex: 0, orient: 'vertical', right: 2, width: 10 }],
    series: [{ type: 'bar', data: vals, label: { show: true, position: 'right' } }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  }
  rankChart.setOption(option, true)
  // 榜单变化后自动刷新右侧曲线（前五位）
  await queryStatsForTopPlayers()
}

async function refreshRanks(showTip=false) {
  if (!canQuery.value) return
  if (rankMode.value === 'total') {
    // 若未选择时刻，默认使用后端“当前时刻”逻辑（不传 at）
    const list = await fetchLeaderboardTotal({ metric: selectedMetrics.value, server_id: selectedServerIds.value, limit: 10, ...(rankAtTs.value ? { at: toIso(new Date(rankAtTs.value*1000)) } : {}) })
    await drawRankChart(list)
  } else {
    // 使用当前 dataZoom 选区
    const s = currentZoomRange.startTs
    const e = currentZoomRange.endTs
    if (!s || !e) {
      if (showTip) {
        const { ElMessage } = await import('element-plus')
        ElMessage.info('请先在右侧图表底部滑块选择时段，再查看增量榜')
      }
      return
    }
    const list = await fetchLeaderboardDelta({ metric: selectedMetrics.value, start: toIso(new Date(s*1000)), end: toIso(new Date(e*1000)), server_id: selectedServerIds.value, limit: 10 })
    await drawRankChart(list)
  }
}

watch(selectedMetrics, async () => {
  if (canQuery.value) {
    // 有指标→生成榜单（默认总量）
    if (rankMode.value === 'delta' && !zoomRangeReady.value) rankMode.value = 'total'
    await refreshRanks(false)
  }
})

watch(selectedServerNames, async () => {
  computeSelectedServerIds()
  if (canQuery.value) await refreshRanks(false)
})

watch(granularity, async () => {
  if (canQuery.value) await queryStatsForTopPlayers()
})

watch(selectedPlayers, async () => {
  // 手动选择玩家时，右图按所选玩家渲染
  if (canQuery.value) await queryStatsForTopPlayers()
})

watch(rankMode, async (m) => {
  if (m === 'delta' && !zoomRangeReady.value) {
    const { ElMessage } = await import('element-plus')
    ElMessage.info('请先在右侧图表底部滑块选择时段，再切换增量榜')
    rankMode.value = 'total'
    return
  }
  await refreshRanks(false)
})

watch(rankAtTs, async () => {
  if (rankMode.value === 'total' && canQuery.value) await refreshRanks(false)
})

onMounted(async () => {
  await Promise.all([fetchPlayers(), fetchServers()])
  if (canQuery.value) {
    await refreshRanks(false)
  }
})
</script>

<style scoped>
.statistics-view { display: flex; flex-direction: column; gap: 12px; height: calc(100vh - 112px); overflow: hidden; }
.topbar-card :deep(.el-card__header) { padding: 10px 12px; }
.topbar { display:flex; align-items:center; justify-content: space-between; gap: 12px; }
.topbar-title { font-size: 16px; font-weight: 600; }
.topbar-actions { display:flex; align-items:center; gap: 8px; }

.filter-card { border-radius: 8px; }
.filter-form { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.mini-form { display: flex; align-items: center; gap: 6px 10px; }
.kpi-row { margin-top: 6px; }
.kpi-card { text-align: center; border-radius: 8px; }
.kpi-title { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 600; }
.chart-card { border-radius: 8px; }
.chart { width: 100%; height: 300px; }
.rank-card { height: 100%; min-height: 520px; display:flex; flex-direction: column; }
.rank-chart { flex: 1; min-height: 360px; }
.rank-hint { margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.server-checkboxes { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow: auto; }

</style>
