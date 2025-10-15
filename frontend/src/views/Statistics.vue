<template>
  <div class="statistics-view">

    <el-row :gutter="16" class="main-row">
      <!-- 左：排行榜 -->
      <el-col :xs="24" :lg="7">
        <div class="left-stack">
          <el-card shadow="never" class="rank-card">
            <template #header>
              <div class="card-header">排行榜, 目前细微存在BUG</div>
            </template>

            <!-- 横向柱状图（含 dataZoom） -->
            <div ref="rankChartRef" class="rank-chart"></div>
          </el-card>
          <!-- 百分比显示控制区域：移动到排行榜容器下方 -->
          <div class="percent-panel">
            <div class="mini-form">
              <span class="percent-title">百分比显示</span>
              <el-switch v-model="percentEnabled" />
              <el-select v-model="percentBase" :disabled="!percentEnabled" placeholder="选择基准" style="width: 200px">
                <el-option label="全服总计" value="global" />
                <el-option v-for="opt in percentBaseCandidates" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 右：筛选 + 统计视图 -->
      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" label-width="80px" class="filter-form">
            <!-- 第一行：数据来源、指标选择、指标预设、换算单位开关 -->
            <div class="mini-form">
              <el-form-item label="数据来源">
                <el-popover placement="bottom-start" trigger="click" width="280">
                  <template #reference>
                    <el-button class="btn-scope-like" type="primary">数据来源 ({{ selectedServerNames.length }})</el-button>
                  </template>
                  <el-checkbox-group v-model="selectedServerNames" @change="onServersSelectionChange" class="server-checkboxes">
                    <el-checkbox v-for="s in serverNames" :key="s" :value="s">{{ s }}</el-checkbox>
                  </el-checkbox-group>
                </el-popover>
              </el-form-item>
              <el-form-item label="指标">
                <el-select v-model="selectedMetrics" multiple filterable remote :remote-method="searchMetrics" :loading="metricsLoading" collapse-tags collapse-tags-tooltip placeholder="输入以搜索指标" style="min-width: 320px">
                  <el-option v-for="m in metricOptions" :key="m" :label="m" :value="m"/>
                </el-select>
              </el-form-item>
              <el-form-item label="指标预设">
                <el-popover placement="bottom-start" trigger="click" width="380">
                  <template #reference>
                    <el-button class="btn-scope-like">指标预设</el-button>
                  </template>
                  <div class="preset-panel">
                    <el-button v-for="p in metricPresets" :key="p.key" size="small" @click="applyPreset(p.key)">{{ p.name }}</el-button>
                  </div>
                </el-popover>
              </el-form-item>
              <el-form-item label="换算单位">
                <el-switch v-model="convertEnabled"/>
              </el-form-item>
            </div>

            <!-- 第二行：玩家、粒度、换算单位选择 -->
            <div class="mini-form">
              <el-form-item label="玩家">
                <el-select v-model="selectedPlayers" multiple filterable remote :remote-method="searchPlayers" :loading="playersLoading" collapse-tags placeholder="输入以搜索玩家" style="min-width: 320px">
                  <el-option v-for="opt in playerOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="粒度 (慎选10min，数据量大易卡)">
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
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">选中玩家数量</div><div class="kpi-value">{{ selectedPlayerCount }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">区间合计(Δ)</div><div class="kpi-value">{{ fmtKpi(totalDeltaSum) }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">全服总计</div><div class="kpi-value">{{ fmtKpi(globalTotalSum) }}</div></el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="hover" class="kpi-card"><div class="kpi-title">选中玩家总计</div><div class="kpi-value">{{ fmtKpi(totalLastTotal) }}</div></el-card>
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
const granularity = ref<string>('12h')
const range = ref<[Date, Date] | null>(null)

// 指标预设
const metricPresets = [
  { key: 'online_time', name: '在线时长', metrics: ['custom.play_one_minute','custom.play_time'], conv: { on: true, from: 'gt', to: 'hour' } },
  { key: 'deaths', name: '死亡次数', metrics: ['custom.deaths'], conv: { on: false } },
  { key: 'mined_total', name: '挖掘总数', metrics: (()=>{ const mats=['wooden','stone','iron','golden','diamond','netherite','copper']; const tools=['axe','sword','pickaxe','shovel','hoe']; const combos = mats.flatMap(m=>tools.map(t=>`used.${m}_${t}`)); return ['used.shears', ...combos] })(), conv: { on: false } },
  { key: 'elytra_km', name: '鞘翅飞行距离', metrics: ['custom.aviate_one_cm'], conv: { on: true, from: 'cm', to: 'km' } },
  { key: 'pearl_km', name: '珍珠传送距离', metrics: ['custom.ender_pearl_one_cm'], conv: { on: true, from: 'cm', to: 'km' } },
  { key: 'vehicle_km', name: '载具行进距离', metrics: (()=>{ const vehicles=['boat','horse','minecart','pig','crouch']; return vehicles.map(v=>`custom.${v}_one_cm`) })(), conv: { on: true, from: 'cm', to: 'km' } },
  { key: 'walk_km', name: '步行行进距离', metrics: ['custom.sprint_one_cm','custom.walk_one_cm','custom.walk_under_water_one_cm','custom.walk_on_water_one_cm'], conv: { on: true, from: 'cm', to: 'km' } },
  { key: 'firework', name: '烟花火箭使用次数', metrics: ['custom.firework_boost'], conv: { on: false } },
  { key: 'break_bedrock', name: '破基岩次数', metrics: ['custom.break_bedrock'], conv: { on: false } },
  { key: 'totem_used', name: '不死图腾使用次数', metrics: ['used.totem_of_undying'], conv: { on: false } },
]

async function applyPreset(key: string) {
  const p = metricPresets.find(x=>x.key===key)
  if (!p) return
  selectedMetrics.value = p.metrics.slice()
  // 设置换算
  convertEnabled.value = !!p.conv?.on
  if (p.conv?.from) convertFrom.value = p.conv.from as any
  if (p.conv?.to) convertTo.value = p.conv.to as any
  // 刷新视图
  await refreshRanks(false)
  await queryStatsForTopPlayers()
}

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
const globalTotalSum = ref<number>(0)
let currentTotalEndTs: number | null = null

const selectedPlayerCount = computed(() => {
  if (selectedPlayers.value && selectedPlayers.value.length > 0) return selectedPlayers.value.length
  if (rankItems.value && rankItems.value.length > 0) return Math.min(5, rankItems.value.length)
  return Math.min(5, players.value.length || 0)
})

let currentDeltaXTimestamps: number[] = []
let currentTotalXTimestamps: number[] = []
// 序列原始缓存（用于本地重绘，避免重复请求）
let lastDeltaDictRaw: Record<string, [number, number][]> = {}
let lastTotalDictRaw: Record<string, [number, number][]> = {}

function rerenderFromCache() {
  try {
    if (lastDeltaDictRaw && lastTotalDictRaw) {
      // 重用现有 queryStatsForTopPlayers 的渲染逻辑：
      // 复制一份最小化流程以保持行为一致
      const deltaDict = convertDict(lastDeltaDictRaw)
      const totalDict = convertDict(lastTotalDictRaw)
      totalDeltaSum.value = Number(Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0).toFixed(2))
      totalLastTotal.value = Number(Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0).toFixed(2))

      const baseForPercent = percentBaseValueRank.value || 1
      const pct = (v:number) => Number(((v / (baseForPercent || 1)) * 100).toPrecision(5))
      const scaledTotalDict = percentEnabled.value
        ? Object.fromEntries(Object.entries(totalDict).map(([k, arr]) => [k, arr.map(([t, v]) => [t, pct(Number(v||0))]) as [number, number][]]))
        : totalDict
      const deltaOpt: any = buildSeriesOption(deltaDict, 'bar', granularity.value, 'delta')
      const totalOpt: any = buildSeriesOption(scaledTotalDict, 'line', granularity.value, 'total')
      deltaChart && deltaChart.setOption(deltaOpt, true)
      totalChart && totalChart.setOption(totalOpt, true)
      currentDeltaXTimestamps = deltaOpt._xTs
      currentTotalXTimestamps = totalOpt._xTs
    }
  } catch {}
}

// 换算单位配置
const convertEnabled = ref<'boolean'>(false)
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

function toIso(d?: Date) {
  if (!d) return undefined
  const dt = new Date(d)
  const pad = (n:number) => String(n).padStart(2,'0')
  // 生成本地时区 ISO，避免后端按本地解析产生时区偏移
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`
}

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
  lastDeltaDictRaw = deltaDictRaw
  lastTotalDictRaw = totalDictRaw
  // 先按原始值计算，再统一进行单位换算
  const deltaDict = convertDict(deltaDictRaw)
  const totalDict = convertDict(totalDictRaw)
  totalDeltaSum.value = Number(Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0).toFixed(2))
  totalLastTotal.value = Number(Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0).toFixed(2))

  // 百分比应用到 Total 累计趋势（按当前基准常量缩放）
  const baseForPercent = percentBaseValueRank.value || 1
  const pct = (v:number) => Number(((v / (baseForPercent || 1)) * 100).toPrecision(5))
  const scaledTotalDict = percentEnabled.value
    ? Object.fromEntries(Object.entries(totalDict).map(([k, arr]) => [k, arr.map(([t, v]) => [t, pct(Number(v||0))]) as [number, number][]]))
    : totalDict
  const deltaOpt: any = buildSeriesOption(deltaDict, 'bar', granularity.value, 'delta')
  const totalOpt: any = buildSeriesOption(scaledTotalDict, 'line', granularity.value, 'total')

  deltaChart && deltaChart.setOption(deltaOpt, true)
  totalChart && totalChart.setOption(totalOpt, true)
  currentDeltaXTimestamps = deltaOpt._xTs
  currentTotalXTimestamps = totalOpt._xTs

  totalChart && totalChart.off('click')
  totalChart && totalChart.on('click', (params:any) => {
    const idx = params?.dataIndex
    if (typeof idx === 'number' && currentTotalXTimestamps[idx]) {
      rankAtTs.value = currentTotalXTimestamps[idx]
      refreshRanks(true)
    }
  })
  const onZoom = (chart:any, which:'delta'|'total') => (evt?: any) => {
    // 根据当前 dataZoom 选区，计算 KPI：优先使用事件参数，回退到 getOption
    const xArr = which==='delta' ? currentDeltaXTimestamps : currentTotalXTimestamps
    let startIdx: number
    let endIdx: number
    const payload = (evt && (evt.batch?.[0] || evt)) || null
    if (payload) {
      const sVal = payload.startValue
      const eVal = payload.endValue
      if (sVal != null && eVal != null) {
        startIdx = Math.max(0, Math.min(xArr.length-1, Number(sVal)))
        endIdx = Math.max(0, Math.min(xArr.length-1, Number(eVal)))
      } else {
        const s = Number(payload.start ?? 0)
        const e = Number(payload.end ?? 100)
        startIdx = Math.round(s/100*(xArr.length-1))
        endIdx = Math.round(e/100*(xArr.length-1))
      }
    } else {
      const opt = chart.getOption() || {}
      const dz = (opt.dataZoom||[])[0] || {}
      startIdx = (dz.startValue != null) ? dz.startValue : Math.round((dz.start||0)/100*(xArr.length-1))
      endIdx = (dz.endValue != null) ? dz.endValue : Math.round((dz.end||100)/100*(xArr.length-1))
    }
    const series = (((chart.getOption && chart.getOption()) || {}).series || [])
    if (which === 'delta') {
      let sum = 0
      for (const s of series) {
        const arr = (s.data || [])
        for (let i = Math.max(0,startIdx); i <= Math.min(arr.length-1,endIdx); i++) sum += Number(arr[i] || 0)
      }
      totalDeltaSum.value = Number(sum.toFixed(2))
    } else {
      // Total：取每条曲线在区间末端（endIdx）数值之和
      let endSum = 0
      for (const s of series) {
        const arr = (s.data || [])
        const b = Number(arr[Math.min(arr.length-1,endIdx)] || 0)
        endSum += b
      }
      totalLastTotal.value = Number(endSum.toFixed(2))
      // 记录末端时间并（防抖）刷新全服总计
      currentTotalEndTs = xArr[Math.min(xArr.length-1, Math.max(0,endIdx))] || null
      currentTotalEndTs && scheduleGlobalTotalRefresh(currentTotalEndTs)
    }
  }
  deltaChart && (deltaChart.off('dataZoom'), deltaChart.on('dataZoom', (e:any)=>onZoom(deltaChart,'delta')(e)))
  totalChart && (totalChart.off('dataZoom'), totalChart.on('dataZoom', (e:any)=>onZoom(totalChart,'total')(e)))
  // 初始根据当前 dataZoom 计算 KPI
  deltaChart && onZoom(deltaChart,'delta')()
  totalChart && onZoom(totalChart,'total')()
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

const globalTotalCache = new Map<string, number>()
let globalTotalTimer: any = null
async function refreshGlobalTotalAtTs(ts: number) {
  // 缓存命中直接返回
  const cacheKey = `${ts}|${(selectedMetrics.value||[]).join(',')}|${(selectedServerIds.value||[]).join(',')}`
  if (globalTotalCache.has(cacheKey)) {
    const v = globalTotalCache.get(cacheKey) as number
    globalTotalSum.value = convertEnabled.value ? applyConvert(v) : Number(v)
    return
  }
  try {
    const list = await fetchLeaderboardTotal({ metric: selectedMetrics.value, server_id: selectedServerIds.value, limit: 10000, at: toIso(new Date(ts*1000)) })
    const raw = (list || []).reduce((acc:number, it:any) => acc + Number(it.value||0), 0)
    globalTotalCache.set(cacheKey, raw)
    globalTotalSum.value = convertEnabled.value ? applyConvert(raw) : Number(raw)
  } catch {
    globalTotalSum.value = 0
  }
}
function scheduleGlobalTotalRefresh(ts: number) {
  if (globalTotalTimer) clearTimeout(globalTotalTimer)
  globalTotalTimer = setTimeout(() => { refreshGlobalTotalAtTs(ts) }, 400)
}
// 百分比显示
const percentEnabled = ref<boolean>(false)
const percentBase = ref<string>('global') // 'global' 或 'player:<uuid>'
const percentBaseCandidates = computed(() => {
  const arr = [] as {label:string,value:string}[]
  // 仅加入数值不为 0 的玩家
  for (const it of (rankItems.value || [])) {
    const v = Number(it?.value || 0)
    if (v > 0 && it?.player_uuid) arr.push({ label: it.player_name || shortUuid(String(it.player_uuid)), value: `player:${String(it.player_uuid)}` })
  }
  return arr
})
const percentBaseValueRank = computed<number>(() => {
  if (!percentEnabled.value) return 1
  if (percentBase.value === 'global') return Number(globalTotalSum.value || 1)
  if (percentBase.value.startsWith('player:')) {
    const uid = percentBase.value.slice(7)
    const it = (rankItems.value || []).find((x:any)=> String(x.player_uuid) === uid)
    const raw = Number(it?.value || 0)
    return convertEnabled.value ? applyConvert(raw) : raw
  }
  return 1
})

function toPercent(val: number): number {
  const base = percentBaseValueRank.value || 1
  return (Number(val || 0) / base) * 100
}

function fmtKpi(val: number): string {
  if (percentEnabled.value) return Number(toPercent(val)).toPrecision(5) + '%'
  if (convertEnabled.value) return Number(val || 0).toFixed(2)
  return String(Math.round(Number(val || 0)))
}

function valueForChart(val: number): number {
  if (!percentEnabled.value) return Number(val || 0)
  return Number(toPercent(val))
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


async function drawRankChart(items: any[], skipRight=false) {
  const echarts = await loadECharts()
  if (!rankChartRef.value) return
  if (!rankChart) rankChart = echarts.init(rankChartRef.value)
  rankItems.value = items || []
  const names = items.map(it => it.player_name || shortUuid(it.player_uuid))
  const rawVals = items.map(it => Number(it.value||0))
  const convVals = convertEnabled.value ? rawVals.map(v => applyConvert(v)) : rawVals
  // 计算百分比基准（若开启百分比：默认用全服总计。若存在 rankAtTs 则以该时刻刷新全服总计）
  let base = 1
  if (percentEnabled.value) base = percentBaseValueRank.value || 1
  const scaled = percentEnabled.value ? convVals.map(v => (v / (base || 1)) * 100) : convVals
  const vals = (!percentEnabled.value && !convertEnabled.value)
    ? scaled.map(v => Math.round(v))
    : scaled
  const option = {
    grid: { left: 20, right: 30, top: 8, bottom: 36, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLabel: {
        interval: 0,
        width: 80,
        overflow: 'truncate',
        ellipsis: '…',
        margin: 4,
      },
    },
    dataZoom: [
      { type: 'inside', yAxisIndex: 0 },
      { type: 'slider', yAxisIndex: 0, orient: 'horizontal', bottom: 6, height: 16 },
    ],
    series: [{ type: 'bar', data: vals, label: { show: true, position: 'right', formatter: (p:any) => {
      const v = Number(p.value||0)
      if (percentEnabled.value) return Number(v).toPrecision(5) + '%'
      return convertEnabled.value ? Number(v).toFixed(2) : String(Math.round(v))
    } } }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  }
  rankChart.setOption(option, true)
  // 榜单变化后自动刷新右侧曲线（前五位）
  await searchPlayers('')
  if (!skipRight) await queryStatsForTopPlayers()
}

async function refreshRanks(_showTip=false) {
  if (!canQuery.value) return
  // 若未选择时刻，默认使用后端“当前时刻”逻辑（不传 at）
  const list = await fetchLeaderboardTotal({ metric: selectedMetrics.value, server_id: selectedServerIds.value, limit: 10, ...(rankAtTs.value ? { at: toIso(new Date(rankAtTs.value*1000)) } : {}) })
  await drawRankChart(list)
  // 同步刷新全服总计（防抖）用于“全服总计”为百分比基准
  const ts = rankAtTs.value || currentTotalEndTs || Math.floor(Date.now()/1000)
  scheduleGlobalTotalRefresh(ts)
}

watch(selectedMetrics, async () => {
  if (canQuery.value) {
    globalTotalCache.clear()
    await refreshRanks(false)
  }
})

watch(selectedServerNames, async () => {
  computeSelectedServerIds()
  globalTotalCache.clear()
  if (canQuery.value) await refreshRanks(false)
})

watch(granularity, async () => {
  if (canQuery.value) await queryStatsForTopPlayers()
})

watch(selectedPlayers, async () => {
  // 手动选择玩家时，右图按所选玩家渲染
  if (canQuery.value) await queryStatsForTopPlayers()
})

// 换算单位相关：切换源/目标或启用状态后，本地重绘（避免重复请求）
watch(convertFrom, async (v) => {
  if (v === 'gt' && !['sec','min','hour','day'].includes(convertTo.value)) convertTo.value = 'hour'
  if (v === 'cm') convertTo.value = 'km'
  rerenderFromCache()
  await drawRankChart(rankItems.value, true)
})
watch(convertTo, async () => { rerenderFromCache(); await drawRankChart(rankItems.value, true) })
watch(convertEnabled, async () => { rerenderFromCache(); await drawRankChart(rankItems.value, true) })

// 百分比：开关/基准变化时，本地重绘（避免请求）
watch(percentEnabled, async () => { rerenderFromCache(); await drawRankChart(rankItems.value, true) })
watch(percentBase, async () => { rerenderFromCache(); await drawRankChart(rankItems.value, true) })
// 全服总计变化不触发重新请求，避免循环；图表重绘在本地完成
// watch(globalTotalSum, async () => {})
watch(rankItems, async () => {
  if (!percentEnabled.value) return
  if (percentBase.value === 'global') return
  const uid = percentBase.value.startsWith('player:') ? percentBase.value.slice(7) : ''
  if (!uid) { percentBase.value = 'global'; return }
  const exists = (rankItems.value || []).some((x:any)=> String(x.player_uuid) === uid && Number(x.value||0) > 0)
  if (!exists) percentBase.value = 'global'
})

watch(rankAtTs, async () => {
  if (canQuery.value) await refreshRanks(false)
})

onMounted(async () => {
  await Promise.all([fetchPlayers(), fetchServers()])
  if (canQuery.value) {
    await refreshRanks(false)
    // 初始同步全服总计
    const ts = rankAtTs.value || currentTotalEndTs || Math.floor(Date.now()/1000)
    await refreshGlobalTotalAtTs(ts)
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
.main-row { align-items: stretch; }
.left-stack { display: flex; flex-direction: column; height: 100%; }
.rank-card { flex: 1; padding-bottom: 8px; display: flex; flex-direction: column; }
.rank-chart { width: 100%; flex: 1; min-height: 420px; }
.percent-panel { margin-top: 8px; padding: 6px 8px; }
.percent-title { color: var(--el-text-color-regular); margin-right: 6px; }
.server-checkboxes { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow: auto; }
.preset-panel { display: flex; flex-wrap: wrap; gap: 6px; }

</style>
