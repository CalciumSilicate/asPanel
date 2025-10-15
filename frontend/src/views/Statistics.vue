<template>
  <div class="statistics-view">

    <el-row :gutter="16">
      <!-- 左：排行榜 -->
      <el-col :xs="24" :lg="7">
        <el-card shadow="never" class="rank-card">
          <template #header>
            <div class="card-header">排行榜</div>
          </template>

          <!-- 横向柱状图（dataZoom 移至底部） -->
          <div ref="rankChartRef" class="rank-chart"></div>
        </el-card>
      </el-col>

      <!-- 右：筛选 + 统计视图 -->
      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" label-width="80px" class="filter-form">
            <!-- 第一行：数据来源、指标选择、换算单位开关 -->
            <div class="mini-form">
              <el-form-item label="数据来源">
                <el-popover placement="bottom-start" trigger="click" width="280">
                  <template #reference>
                    <el-button class="btn-scope-like" type="primary">数据来源 ({{ selectedServerNames.length }})</el-button>
                  </template>
                  <el-checkbox-group v-model="selectedServerNames" @change="onServersSelectionChange" class="server-checkboxes">
                    <el-checkbox v-for="s in serverNames" :key="s" :label="s">{{ s }}</el-checkbox>
                  </el-checkbox-group>
                </el-popover>
              </el-form-item>
              <el-form-item label="指标">
                <el-select v-model="selectedMetrics" multiple filterable remote :remote-method="searchMetrics" :loading="metricsLoading" collapse-tags placeholder="输入以搜索指标" style="min-width: 320px">
                  <el-option v-for="m in metricOptions" :key="m" :label="m" :value="m"/>
                </el-select>
              </el-form-item>
              <el-form-item label="换算单位">
                <el-switch v-model="convertEnabled" active-text="开启" inactive-text="关闭" />
              </el-form-item>
            </div>

            <!-- 第二行：玩家、粒度、换算单位选择 -->
            <div class="mini-form">
              <el-form-item label="玩家">
                <el-select v-model="selectedPlayers" multiple filterable remote :remote-method="searchPlayers" :loading="playersLoading" collapse-tags placeholder="输入以搜索玩家" style="min-width: 320px">
                  <el-option v-for="opt in playerOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="粒度">
                <el-select v-model="granularity" style="width: 130px">
                  <el-option v-for="g in granularities" :key="g" :label="g" :value="g"/>
                </el-select>
              </el-form-item>
              <el-form-item label="单位选择">
                <div class="mini-form">
                  <el-select v-model="convertFrom" :disabled="!convertEnabled" style="width: 120px">
                    <el-option label="gt" value="gt" />
                    <el-option label="cm" value="cm" />
                  </el-select>
                  →
                  <el-select v-model="convertTo" :disabled="!convertEnabled" style="width: 160px">
                    <template v-if="convertFrom==='gt'">
                      <el-option label="sec" value="sec" />
                      <el-option label="min" value="min" />
                      <el-option label="hour" value="hour" />
                      <el-option label="day" value="day" />
                    </template>
                    <template v-else>
                      <el-option label="km" value="km" />
                    </template>
                  </el-select>
                </div>
              </el-form-item>
            </div>
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
              <template #header><div class="card-header">Delta 增量趋势</div></template>
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

// 换算单位配置
const convertEnabled = ref<boolean>(false)
const convertFrom = ref<'gt'|'cm'>('gt')
const convertTo = ref<'sec'|'min'|'hour'|'day'|'km'>('hour')

function getConvertFactor(): number {
  if (!convertEnabled.value) return 1
  if (convertFrom.value === 'gt') {
    // 1 gt = 1/20 sec
    if (convertTo.value === 'sec') return 1/20
    if (convertTo.value === 'min') return 1/(20*60)
    if (convertTo.value === 'hour') return 1/(20*3600)
    if (convertTo.value === 'day') return 1/(20*86400)
    return 1
  } else {
    // cm -> km
    return convertTo.value === 'km' ? 1/100000 : 1
  }
}

function applyConvert(v: number): number {
  const f = getConvertFactor()
  return Number(((Number(v || 0) * f)).toFixed(2))
}

function convertDict(dict: Record<string, [number, number][]>): Record<string, [number, number][]> {
  const out: Record<string, [number, number][]> = {}
  for (const [k, arr] of Object.entries(dict)) {
    out[k] = arr.map(([t, v]) => [t, applyConvert(Number(v||0))]) as [number, number][]
  }
  return out
}


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
    const rankMap = new Map<string, number>()
    rankItems.value.forEach((it:any, idx:number) => { if (it?.player_uuid) rankMap.set(String(it.player_uuid), idx) })
    list.sort((a:any,b:any) => {
      const ra = rankMap.has(String(a.uuid)) ? rankMap.get(String(a.uuid))! : Number.MAX_SAFE_INTEGER
      const rb = rankMap.has(String(b.uuid)) ? rankMap.get(String(b.uuid))! : Number.MAX_SAFE_INTEGER
      if (ra !== rb) return ra - rb
      return String(a.player_name||'').localeCompare(String(b.player_name||''))
    })
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
  const [deltaDictRaw, totalDictRaw] = await Promise.all([ fetchDeltaSeries(base), fetchTotalSeries(base) ])
  // 先按原始值计算，再统一进行单位换算
  const deltaDict = convertDict(deltaDictRaw)
  const totalDict = convertDict(totalDictRaw)
  totalDeltaSum.value = Number(Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0).toFixed(2))
  totalLastTotal.value = Number(Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0).toFixed(2))

  const deltaOpt: any = buildSeriesOption(deltaDict, 'bar', granularity.value, 'delta')
  const totalOpt: any = buildSeriesOption(totalDict, 'line', granularity.value, 'total')

  deltaChart && deltaChart.setOption(deltaOpt, true)
  totalChart && totalChart.setOption(totalOpt, true)
  currentDeltaXTimestamps = deltaOpt._xTs
  currentTotalXTimestamps = totalOpt._xTs
  // 初始根据当前 dataZoom 计算 KPI
  deltaChart && onZoom(deltaChart,'delta')()
  totalChart && onZoom(totalChart,'total')()

  totalChart && totalChart.off('click')
  totalChart && totalChart.on('click', (params:any) => {
    const idx = params?.dataIndex
    if (typeof idx === 'number' && currentTotalXTimestamps[idx]) {
      rankAtTs.value = currentTotalXTimestamps[idx]
      refreshRanks(true)
    }
  })
  const onZoom = (chart:any, which:'delta'|'total') => () => {
    // 根据当前 dataZoom 选区，计算 KPI：
    const opt = chart.getOption() || {}
    const dz = (opt.dataZoom||[])[0] || {}
    const xArr = which==='delta' ? currentDeltaXTimestamps : currentTotalXTimestamps
    const startIdx = (dz.startValue != null) ? dz.startValue : Math.round((dz.start||0)/100*(xArr.length-1))
    const endIdx = (dz.endValue != null) ? dz.endValue : Math.round((dz.end||100)/100*(xArr.length-1))
    const series = (opt.series || [])
    if (which === 'delta') {
      let sum = 0
      for (const s of series) {
        const arr = (s.data || [])
        for (let i = Math.max(0,startIdx); i <= Math.min(arr.length-1,endIdx); i++) sum += Number(arr[i] || 0)
      }
      totalDeltaSum.value = Number(sum.toFixed(2))
    } else {
      let total = 0
      for (const s of series) {
        const arr = (s.data || [])
        const a = Number(arr[Math.max(0,startIdx)] || 0)
        const b = Number(arr[Math.min(arr.length-1,endIdx)] || 0)
        total += (b - a)
      }
      totalLastTotal.value = Number(total.toFixed(2))
    }
  }
  deltaChart && (deltaChart.off('dataZoom'), deltaChart.on('dataZoom', onZoom(deltaChart,'delta')))
  totalChart && (totalChart.off('dataZoom'), totalChart.on('dataZoom', onZoom(totalChart,'total')))
}



async function fetchPlayers() {
  try {
    const res = await apiClient.get('/api/players')
    players.value = Array.isArray(res.data) ? res.data : []
    // 初始填充一次可选项（按当前排行榜顺序）
    await searchPlayers('')
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


async function drawRankChart(items: any[]) {
  const echarts = await loadECharts()
  if (!rankChartRef.value) return
  if (!rankChart) rankChart = echarts.init(rankChartRef.value)
  rankItems.value = items || []
  const names = items.map(it => it.player_name || shortUuid(it.player_uuid))
  const vals = items.map(it => applyConvert(Number(it.value||0)))
  const option = {
    grid: { left: 110, right: 16, top: 8, bottom: 26, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLabel: {
        interval: 0,
        formatter: (val: string) => {
          const s = String(val || '')
          return s.length > 10 ? (s.slice(0, 10) + '…') : s
        },
      },
    },
    dataZoom: [
      { type: 'inside', yAxisIndex: 0 },
    ],
    series: [{ type: 'bar', data: vals, label: { show: true, position: 'right', formatter: (p:any) => Number(p.value||0).toFixed(2) } }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  }
  rankChart.setOption(option, true)
  // 榜单变化后自动刷新右侧曲线（前五位）
  await searchPlayers('')
  await queryStatsForTopPlayers()
}

async function refreshRanks(_showTip=false) {
  if (!canQuery.value) return
  // 若未选择时刻，默认使用后端“当前时刻”逻辑（不传 at）
  const list = await fetchLeaderboardTotal({ metric: selectedMetrics.value, server_id: selectedServerIds.value, limit: 10, ...(rankAtTs.value ? { at: toIso(new Date(rankAtTs.value*1000)) } : {}) })
  await drawRankChart(list)
}

watch(selectedMetrics, async () => {
  if (canQuery.value) {
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

// 换算单位相关：切换源/目标或启用状态后，刷新榜单与曲线
watch(convertFrom, async (v) => {
  if (v === 'gt' && !['sec','min','hour','day'].includes(convertTo.value)) convertTo.value = 'hour'
  if (v === 'cm') convertTo.value = 'km'
  if (canQuery.value) { await queryStatsForTopPlayers(); await refreshRanks(false) }
})
watch(convertTo, async () => { if (canQuery.value) { await queryStatsForTopPlayers(); await refreshRanks(false) } })
watch(convertEnabled, async () => { if (canQuery.value) { await queryStatsForTopPlayers(); await refreshRanks(false) } })

watch(rankAtTs, async () => {
  if (canQuery.value) await refreshRanks(false)
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
.filter-form { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.mini-form { display: flex; align-items: center; gap: 6px 10px; }
.kpi-row { margin-top: 6px; }
.kpi-card { text-align: center; border-radius: 8px; }
.kpi-title { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 600; }
.chart-card { border-radius: 8px; }
.chart { width: 100%; height: 300px; }
.rank-card { height: auto; padding-bottom: 8px; }
.rank-chart { width: 100%; height: 420px; }
.server-checkboxes { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow: auto; }

</style>
