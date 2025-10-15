<template>
  <div class="statistics-view">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" label-width="80px" class="filter-form">
        <el-form-item label="玩家">
          <el-select v-model="selectedPlayers" multiple filterable collapse-tags placeholder="选择玩家" style="min-width: 300px">
            <el-option v-for="p in players" :key="p.uuid" :label="p.player_name ? `${p.player_name} (${p.uuid.slice(0,8)})` : p.uuid" :value="p.uuid"/>
          </el-select>
        </el-form-item>
        <el-form-item label="指标">
          <el-select v-model="selectedMetrics" multiple filterable collapse-tags placeholder="输入或选择指标" style="min-width: 360px">
            <el-option v-for="m in commonMetrics" :key="m" :label="m" :value="m"/>
          </el-select>
        </el-form-item>
        <el-form-item label="粒度">
          <el-select v-model="granularity" style="width: 160px">
            <el-option v-for="g in granularities" :key="g" :label="g" :value="g"/>
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="range" type="datetimerange" range-separator="到" start-placeholder="开始时间" end-placeholder="结束时间" style="min-width: 380px"/>
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

    <el-card shadow="never" class="chart-card">
      <template #header><div class="card-header">Δ Delta 趋势</div></template>
      <div ref="deltaChartRef" class="chart"></div>
    </el-card>

    <el-card shadow="never" class="chart-card">
      <template #header><div class="card-header">Total 累计趋势</div></template>
      <div ref="totalChartRef" class="chart"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '@/api'
import { fetchDeltaSeries, fetchTotalSeries } from '@/api/stats'
import { loadECharts } from '@/utils/echartsLoader'

const players = ref<any[]>([])
const selectedPlayers = ref<string[]>([])
const commonMetrics = ref<string[]>([
  'custom.play_one_minute',
  'custom.play_time',
  'custom.deaths',
  'used.minecraft:totem_of_undying',
])
const selectedMetrics = ref<string[]>(['custom.play_one_minute'])
const granularities = ['10min', '30min', '1h', '12h', '24h', '1week', '1month', '6month', '1year']
const granularity = ref<string>('10min')
const range = ref<[Date, Date] | null>(null)

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

function buildSeriesOption(dict: Record<string, [number, number][]>) {
  const uuids = Object.keys(dict)
  const allTs = new Set<number>()
  uuids.forEach(u => dict[u].forEach(([t]) => allTs.add(t)))
  const xTs = Array.from(allTs).sort((a,b)=>a-b)
  const xLabels = xTs.map(tsToLabel)
  const series = uuids.map(u => {
    const map = new Map<number, number>()
    dict[u].forEach(([t, v]) => map.set(t, Number(v||0)))
    return { name: u.slice(0,8), type: 'line', smooth: true, symbol: 'none', data: xTs.map(ts => map.get(ts) ?? 0) }
  })
  return { tooltip: { trigger: 'axis' }, legend: { type: 'scroll' }, grid: { left: 40, right: 20, top: 40, bottom: 40 }, xAxis: { type: 'category', data: xLabels }, yAxis: { type: 'value', scale: true }, series }
}

async function queryStats() {
  if (!canQuery.value) return
  await ensureCharts()
  const [start, end] = (range.value || []) as any
  const toIso = (d?: Date) => d ? new Date(d).toISOString().slice(0,19) : undefined
  const base = { player_uuid: selectedPlayers.value, metric: selectedMetrics.value, granularity: granularity.value, start: toIso(start), end: toIso(end), namespace: 'minecraft' }
  const [deltaDict, totalDict] = await Promise.all([ fetchDeltaSeries(base), fetchTotalSeries(base) ])
  totalDeltaSum.value = Object.values(deltaDict).reduce((acc, arr) => acc + arr.reduce((s, [,v]) => s + Number(v||0), 0), 0)
  totalLastTotal.value = Object.values(totalDict).reduce((acc, arr) => acc + (arr.length ? Number(arr[arr.length-1][1]||0) : 0), 0)
  deltaChart && deltaChart.setOption(buildSeriesOption(deltaDict), true)
  totalChart && totalChart.setOption(buildSeriesOption(totalDict), true)
}

function resetFilters() {
  selectedPlayers.value = []
  selectedMetrics.value = ['custom.play_one_minute']
  granularity.value = '10min'
  range.value = null
  totalDeltaSum.value = 0
  totalLastTotal.value = 0
}

async function fetchPlayers() {
  try {
    const res = await apiClient.get('/api/players')
    players.value = Array.isArray(res.data) ? res.data : []
  } catch (e) {
    players.value = []
  }
}

onMounted(() => { fetchPlayers() })
</script>

<style scoped>
.statistics-view { display: flex; flex-direction: column; gap: 16px; }
.filter-card { border-radius: 8px; }
.filter-form { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.kpi-row { margin-top: 6px; }
.kpi-card { text-align: center; border-radius: 8px; }
.kpi-title { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 600; }
.chart-card { border-radius: 8px; }
.chart { width: 100%; height: 360px; }
</style>

