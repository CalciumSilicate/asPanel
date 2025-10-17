<template>
  <div class="statistics-view">

    <!-- 顶部数据统计顶栏：标题 + 玩家范围筛选 -->
    <el-card shadow="never" class="topbar-card" :body-style="{ display: 'none', padding: '0' }">
      <template #header>
        <div class="topbar">
          <div class="topbar-title">数据统计</div>
          <div class="topbar-actions">
            <el-radio-group v-model="scope" @change="onScopeChange">
              <el-radio-button label="all">所有玩家</el-radio-button>
              <el-radio-button label="official_only">仅正版玩家</el-radio-button>
              <el-radio-button label="include_cracked">包括盗版玩家</el-radio-button>
            </el-radio-group>
            <el-checkbox class="wl-only" v-model="whitelistOnly" @change="onWhitelistToggle">仅白名单玩家</el-checkbox>
          </div>
        </div>
      </template>
    </el-card>

    <el-row :gutter="16" class="main-row">
      <!-- 左：排行榜 -->
      <el-col :xs="24" :lg="7">
        <div class="left-stack">
          <el-card shadow="never" class="rank-card">
            <template #header>
              <div class="card-header">排行榜</div>
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
              <el-form-item label="粒度">
                <el-select v-model="granularity" style="width: 180px">
                  <el-option v-for="opt in granularityOptions" :key="opt.value" :label="opt.label" :value="opt.value" :title="opt.label"/>
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

/** =========================
 *  基础状态
 *  ========================= */
const players = ref<any[]>([])
const servers = ref<any[]>([])

const scope = ref<'official_only'|'include_cracked'|'all'>('official_only')
const whitelistUUIDs = ref<string[]>([])
const whitelistOnly = ref<boolean>(true)
const whitelistSet = computed(() => new Set(whitelistUUIDs.value))

const serverNames = computed(() => servers.value.map((s:any) => (s.path?.split('/').pop()) || s.name))
const selectedServerNames = ref<string[]>([])
const selectedServerIds = ref<number[]>([])

const selectedPlayers = ref<string[]>([]) // 右侧图表玩家

// 远程搜索
const playersLoading = ref(false)
const playerOptions = ref<{label:string,value:string}[]>([])

const metricOptions = ref<string[]>([])
const metricsLoading = ref(false)
const selectedMetrics = ref<string[]>(['custom.play_time','custom.play_one_minute'])

// 粒度
const granularities = ['10min','20min','30min','1h','6h','12h','24h','1week','1month','3month','6month','1year']
const granularity = ref<string>('12h')
const granularityOptions = computed(() => granularities.map(g => ({
  value: g,
  label: (g==='10min' || g==='20min' || g==='30min' || g==='1h') ? `${g}（数据量大时易卡，慎选）` : g,
})))
const range = ref<[Date, Date] | null>(null)

// 指标预设
const metricPresets = [
  { key: 'online_time', name: '在线时长', metrics: ['custom.play_one_minute','custom.play_time'], conv: { on: true, from: 'gt', to: 'hour' } },
  { key: 'deaths', name: '死亡次数', metrics: ['custom.deaths'], conv: { on: false } },
  { key: 'm i n e d_total', name: '挖掘总数', metrics: (()=>{ const mats=['wooden','stone','iron','golden','diamond','netherite','copper']; const tools=['axe','sword','pickaxe','shovel','hoe']; const combos = mats.flatMap(m=>tools.map(t=>`used.${m}_${t}`)); return ['used.shears', ...combos] })(), conv: { on: false } },
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
  convertEnabled.value = !!p.conv?.on
  if (p.conv?.from) convertFrom.value = p.conv.from as any
  if (p.conv?.to) convertTo.value = p.conv.to as any
  await refreshRanks(false)
  await queryStatsForTopPlayers()
}

/** =========================
 *  ECharts 实例
 *  ========================= */
const rankAtTs = ref<number | null>(null) // 由 Total 图点击选择
const rankChartRef = ref<HTMLElement | null>(null)
let rankChart: any = null
const deltaChartRef = ref<HTMLElement | null>(null)
const totalChartRef = ref<HTMLElement | null>(null)
let deltaChart: any = null
let totalChart: any = null

const canQuery = computed(() => selectedMetrics.value.length > 0)

const totalDeltaSum = ref<number>(0)   // KPI：区间合计(Δ)
const totalLastTotal = ref<number>(0)  // KPI：选中玩家总计（窗口末端）
const globalTotalSum = ref<number>(0)  // KPI：全服总计
let currentTotalEndTs: number | null = null

// 缓存最后一次查询的原始数据（稀疏）
let lastDeltaDictRaw: Record<string, [number, number][]> = {}
let lastTotalDictRaw: Record<string, [number, number][]> = {}

/** =========================
 *  单位换算 & 百分比
 *  ========================= */
const convertEnabled = ref<'boolean'>(true)
const convertFrom = ref<'gt'|'cm'>('gt')
const convertTo = ref<'sec'|'min'|'hour'|'day'|'km'>('hour')

function getConvertFactor(): number {
  if (!convertEnabled.value) return 1
  if (convertFrom.value === 'gt') {
    if (convertTo.value === 'sec') return 1/20
    if (convertTo.value === 'min') return 1/(20*60)
    if (convertTo.value === 'hour') return 1/(20*3600)
    if (convertTo.value === 'day') return 1/(20*86400)
    return 1
  } else {
    return convertTo.value === 'km' ? 1/100000 : 1
  }
}
function applyConvert(v: number): number {
  const f = getConvertFactor()
  return Number(((Number(v || 0) * f)).toFixed(2))
}

// 百分比：仅用于 Total 累计趋势
const percentEnabled = ref<boolean>(false)
const percentBase = ref<string>('global') // 'global' 或 'player:<uuid>'
const percentBaseCandidates = computed(() => {
  const arr = [] as {label:string,value:string}[]
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
function formatAxisValueTick(v: number): string {
  const val = Number(v || 0)
  if (percentEnabled.value) return Number(val).toPrecision(5) + '%'
  if (convertEnabled.value) return Number(val).toFixed(2)
  const abs = Math.abs(val)
  if (abs >= 1e9) return (val/1e9).toFixed(1) + 'B'
  if (abs >= 1e6) return (val/1e6).toFixed(1) + 'M'
  if (abs >= 1e3) return (val/1e3).toFixed(1) + 'k'
  return String(Math.round(val))
}

/** =========================
 *  稀疏渲染相关（关键优化）
 *  ========================= */
// 稀疏：直接换算但保留原始 ts
function convertDictSparse(dict: Record<string, [number, number][]>): Record<string, [number, number][]> {
  const out: Record<string, [number, number][]> = {}
  for (const [k, arr] of Object.entries(dict)) {
    out[k] = arr.map(([t, v]) => [t, applyConvert(Number(v||0))])
  }
  return out
}

// granularity -> 秒
function granToSec(g: string): number {
  if (g==='10min') return 600
  if (g==='20min') return 1200
  if (g==='30min') return 1800
  if (g==='1h') return 3600
  if (g==='6h') return 21600
  if (g==='12h') return 43200
  if (g==='24h') return 86400
  if (g==='1week') return 604800
  if (g==='1month') return 86400*30
  if (g==='3month') return 86400*90
  if (g==='6month') return 86400*180
  if (g==='1year') return 86400*365
  return 600
}

// 对可见窗口聚合 delta 为有限桶
function bucketizeDelta(
  arr: [number,number][],
  gran: string,
  winStart: number,
  winEnd: number,
  maxBuckets = 1000
): [number,number][] {
  if (!arr.length) return []
  const clipped = arr.filter(([t]) => t >= winStart && t <= winEnd)
  if (clipped.length === 0) return []
  const span = Math.max(1, winEnd - winStart)
  const bucketCount = Math.min(maxBuckets, Math.ceil(span / granToSec(gran)))
  const bucketWidth = Math.max(1, Math.ceil(span / bucketCount))
  const firstBucketStart = Math.floor(winStart / bucketWidth) * bucketWidth
  const buckets = new Map<number, number>()
  for (const [t, v] of clipped) {
    const b = firstBucketStart + Math.floor((t - firstBucketStart)/bucketWidth)*bucketWidth
    buckets.set(b, (buckets.get(b) || 0) + (v||0))
  }
  const out: [number,number][] = Array.from(buckets.entries())
    .sort((a,b)=>a[0]-b[0])
    .map(([b, sum]) => [b + Math.floor(bucketWidth/2), Number(sum.toFixed(2))])
  return out
}

// 获取 total 图当前可见窗口（ms -> s）
function currentWindowSecFromChart(chart:any): [number,number] {
  const opt = chart?.getOption?.()
  if (!opt) return [0,0]
  // 尝试从第一条 series 取 x 范围
  const s0 = opt.series?.[0]?.data || []
  if (!s0.length) return [0,0]
  const xs = s0.map((d:any)=>Array.isArray(d)?d[0]:d) as number[]
  const min = xs[0], max = xs[xs.length-1]
  const dz = (opt.dataZoom||[])[0] || {}
  const start = dz.startValue!=null ? xs[Math.max(0, Math.min(xs.length-1, dz.startValue))] : min + (dz.start||0)/100*(max-min)
  const end   = dz.endValue!=null   ? xs[Math.max(0, Math.min(xs.length-1, dz.endValue))]   : min + (dz.end??100)/100*(max-min)
  return [Math.floor(start/1000), Math.floor(end/1000)]
}

/** 用稀疏 total（阶梯）+ 窗口桶化 delta 渲染 */
function renderSparseChartsFromCache(initial=false) {
  if (!deltaChart || !totalChart) return
  const totalDictSparse = convertDictSparse(lastTotalDictRaw)
  const baseForPercent = percentBaseValueRank.value || 1
  const pct = (v:number) => Number(((v / (baseForPercent || 1)) * 100).toPrecision(5))
  const totalSeries = Object.entries(totalDictSparse).map(([uuid, arr]) => {
    const seriesData = (percentEnabled.value ? arr.map(([t,v]) => [t*1000, pct(v)]) : arr.map(([t,v]) => [t*1000, v]))
    return {
      name: showName(uuid),
      type: 'line',
      step: 'end',
      showSymbol: false,
      sampling: 'lttb',
      data: seriesData,
    }
  })
  totalChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: (val:any)=>formatAxisValueTick(Number(val)) } },
    dataZoom: [{ type:'inside' }, { type:'slider', height:18, bottom:4 }],
    series: totalSeries,
    progressive: 4000,
    progressiveThreshold: 3000,
    progressiveChunkMode: 'mod',
    hoverLayerThreshold: 2000,
  }, true)

  // 点击 total 图上的点 -> 更新 rankAtTs
  totalChart.off('click')
  totalChart.on('click', (params:any) => {
    const v = params?.value
    const tsMs = Array.isArray(v) ? v[0] : v
    if (typeof tsMs === 'number') {
      rankAtTs.value = Math.floor(tsMs/1000)
    }
  })

  // 根据窗口渲染 delta
  const [ws, we] = currentWindowSecFromChart(totalChart)
  renderDeltaForWindow(ws, we)

  // 绑定缩放事件：窗口变化时重算 delta + KPI
  totalChart.off('dataZoom')
  totalChart.on('dataZoom', () => {
    const [s, e] = currentWindowSecFromChart(totalChart)
    renderDeltaForWindow(s, e)
    recomputeKpisFromCharts()
  })

  // 初次也算一次 KPI
  if (initial) recomputeKpisFromCharts()
}

function renderDeltaForWindow(winStart:number, winEnd:number) {
  const deltaDictSparse = convertDictSparse(lastDeltaDictRaw)
  const deltaSeries = Object.entries(deltaDictSparse).map(([uuid, arr]) => {
    const bucketed = bucketizeDelta(arr, granularity.value, winStart, winEnd, 1000)
    return {
      name: showName(uuid),
      type: 'bar',
      large: true,
      largeThreshold: 500,
      data: bucketed.map(([t,v]) => [t*1000, v]),
    }
  })
  deltaChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { type:'scroll' },
    xAxis: { type:'time' },
    yAxis: { type:'value', scale: true, axisLabel: { formatter: (val:any)=>formatAxisValueTick(Number(val)) } },
    dataZoom: [{ type:'inside' }, { type:'slider', height:18, bottom:4 }],
    series: deltaSeries,
    progressive: 4000,
    progressiveThreshold: 3000,
    progressiveChunkMode: 'mod',
    hoverLayerThreshold: 2000,
  }, true)
}

/** 从当前图表（窗口）重算 KPI */
function recomputeKpisFromCharts() {
  // totalLastTotal：窗口末端（每条线的最后一个可见点）之和
  let endSum = 0
  const totOpt = totalChart.getOption?.() || {}
  const dz = (totOpt.dataZoom||[])[0] || {}
  const series = (totOpt.series || [])
  for (const s of series) {
    const data = s.data || []
    if (!data.length) continue
    const endIdx = (dz.endValue!=null) ? Math.min(data.length-1, dz.endValue) : Math.round(((dz.end??100)/100) * (data.length-1))
    const val = Array.isArray(data[endIdx]) ? Number(data[endIdx][1]||0) : Number(data[endIdx]||0)
    endSum += val
  }
  totalLastTotal.value = Number(endSum.toFixed(2))

  // totalDeltaSum：delta 可见窗口内的和
  const delOpt = deltaChart.getOption?.() || {}
  const delDz = (delOpt.dataZoom||[])[0] || {}
  let sum = 0
  for (const s of (delOpt.series || [])) {
    const data = s.data || []
    if (!data.length) continue
    const sIdx = (delDz.startValue!=null) ? Math.max(0, delDz.startValue) : Math.round(((delDz.start||0)/100) * (data.length-1))
    const eIdx = (delDz.endValue!=null) ? Math.min(data.length-1, delDz.endValue) : Math.round(((delDz.end??100)/100) * (data.length-1))
    for (let i = Math.max(0,sIdx); i <= Math.min(eIdx, data.length-1); i++) {
      const v = Array.isArray(data[i]) ? Number(data[i][1]||0) : Number(data[i]||0)
      sum += v
    }
  }
  totalDeltaSum.value = Number(sum.toFixed(2))

  // 记录末端时间并刷新全服总计
  const [ws, we] = currentWindowSecFromChart(totalChart)
  currentTotalEndTs = we || null
  if (currentTotalEndTs) scheduleGlobalTotalRefresh(currentTotalEndTs)
}

/** 单位或百分比变化时：从缓存重绘（不重新请求） */
function rerenderFromCache() {
  try {
    if (lastDeltaDictRaw && lastTotalDictRaw) {
      renderSparseChartsFromCache()
      // 排行榜也要重绘（单位/百分比会影响显示）
      drawRankChart(rankItems.value, true)
      // 全服总计（命中缓存后再做单位换算）
      const ts = currentRankContextTs()
      if (ts) refreshGlobalTotalAtTs(ts)
      // KPI
      recomputeKpisFromCharts()
    }
  } catch {}
}

/** =========================
 *  其它工具函数
 *  ========================= */
async function ensureCharts() {
  const echarts = await loadECharts()
  if (deltaChartRef.value && !deltaChart) deltaChart = echarts.init(deltaChartRef.value)
  if (totalChartRef.value && !totalChart) totalChart = echarts.init(totalChartRef.value)
  if (rankChartRef.value && !rankChart) rankChart = echarts.init(rankChartRef.value)
}
function shortUuid(u: string): string { return (u||'').slice(0,8) }
function showName(u: string): string {
  const p = players.value.find((x:any) => x.uuid === u)
  return p?.player_name || shortUuid(u)
}
function visiblePlayers(): any[] {
  if (!whitelistOnly.value) return players.value
  const set = whitelistSet.value
  return players.value.filter((p:any) => set.has(String(p.uuid)))
}
async function searchPlayers(query: string) {
  playersLoading.value = true
  try {
    const q = (query || '').toLowerCase()
    const baseList = visiblePlayers()
    const list = baseList.filter((p:any) => (p.player_name||'').toLowerCase().includes(q) || (p.uuid||'').toLowerCase().includes(q))
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
function toIso(d?: Date) {
  if (!d) return undefined
  const dt = new Date(d)
  const pad = (n:number) => String(n).padStart(2,'0')
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`
}

/** =========================
 *  查询 & 渲染（稀疏）
 *  ========================= */
async function queryStatsForTopPlayers() {
  if (!canQuery.value) return
  await ensureCharts()
  let topUuids = selectedPlayers.value.slice(0,10)
  if (topUuids.length === 0) {
    topUuids = rankItems.value.map((x:any)=>x.player_uuid).filter(Boolean).slice(0,10)
  }
  if (topUuids.length === 0) {
    topUuids = visiblePlayers().slice(0,10).map((p:any)=>p.uuid)
  }
  if (topUuids.length === 0) return

  const base = { player_uuid: topUuids, metric: selectedMetrics.value, granularity: granularity.value, namespace: 'minecraft', server_id: selectedServerIds.value }
  const [deltaDictRaw, totalDictRaw] = await Promise.all([ fetchDeltaSeries(base), fetchTotalSeries(base) ])
  lastDeltaDictRaw = deltaDictRaw || {}
  lastTotalDictRaw = totalDictRaw || {}

  // KPI 初算（以全量—随后在 dataZoom 时重算）
  const convDelta = convertDictSparse(lastDeltaDictRaw)
  const convTotal = convertDictSparse(lastTotalDictRaw)
  totalDeltaSum.value = Number(Object.values(convDelta).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0).toFixed(2))
  totalLastTotal.value = Number(Object.values(convTotal).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0).toFixed(2))

  // 渲染（不补点）
  renderSparseChartsFromCache(true)
}

/** =========================
 *  排行榜
 *  ========================= */
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

  let base = 1
  if (percentEnabled.value) base = percentBaseValueRank.value || 1
  const scaled = percentEnabled.value ? convVals.map(v => (v / (base || 1)) * 100) : convVals
  const vals = (!percentEnabled.value && !convertEnabled.value) ? scaled.map(v => Math.round(v)) : scaled
  const initialEndIdx = Math.min(names.length - 1, 14)
  const option = {
    grid: { left: 20, right: 30, top: 8, bottom: 36, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { hideOverlap: true, formatter: (val:any) => formatAxisValueTick(Number(val)) },
      splitNumber: 4,
    },
    yAxis: {
      type: 'category',
      data: names,
      inverse: true,
      axisLabel: { interval: 0, width: 80, overflow: 'truncate', ellipsis: '…', margin: 4 },
    },
    dataZoom: [
      { type: 'inside', yAxisIndex: 0, startValue: 0, endValue: initialEndIdx },
      { type: 'slider', yAxisIndex: 0, orient: 'vertical', right: 6, top: 24, bottom: 24, width: 12, startValue: 0, endValue: initialEndIdx },
    ],
    series: [{ type: 'bar', data: vals, label: { show: true, position: 'right', formatter: (p:any) => {
      const v = Number(p.value||0)
      if (percentEnabled.value) return Number(v).toPrecision(5) + '%'
      return convertEnabled.value ? Number(v).toFixed(2) : String(Math.round(v))
    } } }],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  }
  rankChart.setOption(option, true)

  // 榜单变化后自动刷新右侧曲线（前十位）
  await searchPlayers('')
  if (!skipRight) await queryStatsForTopPlayers()
}

/** =========================
 *  服务器 & 全服总计缓存
 *  ========================= */
function computeSelectedServerIds() {
  const nameToId = new Map<string, number>()
  servers.value.forEach((s:any) => nameToId.set((s.path?.split('/').pop()) || s.name, Number(s.id)))
  selectedServerIds.value = selectedServerNames.value.map(n => nameToId.get(n)!).filter(Boolean)
}

const globalTotalCache = new Map<string, number>()
let globalTotalTimer: any = null
async function refreshGlobalTotalAtTs(ts: number) {
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

function currentRankContextTs(): number {
  return rankAtTs.value || currentTotalEndTs || Math.floor(Date.now()/1000)
}

/** =========================
 *  后端数据
 *  ========================= */
async function fetchPlayers() {
  try {
    const res = await apiClient.get('/api/players', { params: { scope: scope.value } })
    players.value = Array.isArray(res.data) ? res.data : []
    await searchPlayers('')
  } catch { players.value = [] }
}
async function fetchServers() {
  try {
    const res = await apiClient.get('/api/servers')
    servers.value = Array.isArray(res.data) ? res.data : []
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
async function searchMetrics(query: string) {
  metricsLoading.value = true
  try {
    metricOptions.value = query ? await fetchMetrics(query, 50, 'minecraft') : []
  } finally { metricsLoading.value = false }
}

/** =========================
 *  排行榜刷新（支持 rankAtTs）
 *  ========================= */
async function refreshRanks(_showTip=false) {
  if (!canQuery.value) return
  const list = await fetchLeaderboardTotal({ metric: selectedMetrics.value, server_id: selectedServerIds.value, limit: 10000, ...(rankAtTs.value ? { at: toIso(new Date(rankAtTs.value*1000)) } : {}) })
  const allowed = new Set(visiblePlayers().map((p:any)=>String(p.uuid)))
  const filtered = (list || []).filter((it:any) => allowed.has(String(it.player_uuid)))
  await drawRankChart(filtered)
  const ts = rankAtTs.value || currentTotalEndTs || Math.floor(Date.now()/1000)
  scheduleGlobalTotalRefresh(ts)
}

/** =========================
 *  事件与副作用
 *  ========================= */
const onScopeChange = async () => {
  await fetchPlayers()
  const allowed = new Set((players.value || []).map((p:any)=>String(p.uuid)))
  selectedPlayers.value = selectedPlayers.value.filter(u => allowed.has(String(u)))
  await refreshRanks(false)
  if (canQuery.value) await queryStatsForTopPlayers()
  scheduleGlobalTotalRefresh(currentRankContextTs())
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
  if (canQuery.value) await queryStatsForTopPlayers()
})

// 换算单位：本地重绘
watch(convertFrom, async (v) => {
  if (v === 'gt' && !['sec','min','hour','day'].includes(convertTo.value)) convertTo.value = 'hour'
  if (v === 'cm') convertTo.value = 'km'
  rerenderFromCache()
})
watch(convertTo, async () => { rerenderFromCache() })
watch(convertEnabled, async () => { rerenderFromCache() })

// 百分比：只影响 total
watch(percentEnabled, async () => { rerenderFromCache() })
watch(percentBase, async () => { rerenderFromCache() })

// 当 rankItems 变化时，若基准是某玩家且其不在榜单则回退到全服
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

// 白名单切换
const onWhitelistToggle = async () => {
  const allowed = new Set(visiblePlayers().map((p:any)=>String(p.uuid)))
  selectedPlayers.value = selectedPlayers.value.filter(u => allowed.has(String(u)))
  await refreshRanks(false)
  if (canQuery.value) await queryStatsForTopPlayers()
  scheduleGlobalTotalRefresh(currentRankContextTs())
}

async function fetchWhitelist() {
  try {
    const res = await apiClient.get('/api/players/whitelist-uuids')
    whitelistUUIDs.value = Array.isArray(res.data) ? res.data : []
  } catch { whitelistUUIDs.value = [] }
}

/** =========================
 *  挂载
 *  ========================= */
onMounted(async () => {
  await Promise.all([fetchPlayers(), fetchServers(), fetchWhitelist()])
  if (canQuery.value) {
    await refreshRanks(false)
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
.wl-only { margin-left: 8px; }
</style>
