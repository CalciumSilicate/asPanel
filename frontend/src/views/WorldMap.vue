<template>
  <div class="world-map-page">
    <!-- Toolbar -->
    <div class="wm-toolbar">
      <div class="wm-toolbar-left">
        <el-select
          v-model="selectedServerId"
          placeholder="选择服务器"
          style="width: 160px"
          @change="onServerChange"
          :loading="serversLoading"
        >
          <el-option
            v-for="s in servers"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>

        <el-radio-group v-model="activeDim" size="small" @change="onDimChange" :disabled="!selectedServerId">
          <el-radio-button value="nether">下界/主世界</el-radio-button>
          <el-radio-button value="end" :disabled="!currentServer?.available_dims?.includes('end')">末地</el-radio-button>
        </el-radio-group>

        <el-divider direction="vertical" />

        <el-button-group size="small">
          <el-button :type="layout === 'left' ? 'primary' : ''" @click="layout = 'left'" title="仅显示地图">
            <el-icon><Grid /></el-icon>
          </el-button>
          <el-button :type="layout === 'split' ? 'primary' : ''" @click="layout = 'split'" title="双栏">
            <el-icon><Grid /></el-icon> 双栏
          </el-button>
          <el-button :type="layout === 'right' ? 'primary' : ''" @click="layout = 'right'" title="仅显示 BlueMap">
            BlueMap
          </el-button>
        </el-button-group>
      </div>

      <div class="wm-toolbar-right">
        <el-checkbox v-model="showOfflinePlayers" label="离线玩家" size="small" />

        <el-divider direction="vertical" />

        <el-date-picker
          v-model="trajectoryFromTime"
          type="datetime"
          placeholder="轨迹起始时间"
          size="small"
          style="width: 168px"
          clearable
          format="MM-DD HH:mm"
          value-format="YYYY-MM-DDTHH:mm:ss"
          :disabled="!selectedServerId"
          @change="onTrajectoryFromTimeChange"
        />

        <el-divider direction="vertical" />

        <el-switch
          v-model="editMode"
          active-text="编辑"
          inactive-text="查看"
          size="small"
          :disabled="!selectedServerId"
          @change="onEditModeChange"
        />

        <template v-if="editMode">
          <el-button
            size="small"
            :type="connectMode ? 'warning' : ''"
            @click="toggleConnectMode"
            title="连线模式：起点→终点节点，或终点→已有线段（垂直插入）"
          >
            {{ connectMode ? (connectSourceKey ? '点击终点/线段…' : '点击起点…') : '连线' }}
          </el-button>
          <el-button
            size="small"
            :type="addVirtualMode ? 'info' : ''"
            @click="toggleAddVirtualMode"
            title="切换后双击放置虚拟节点（也可 Shift+双击）"
          >
            虚拟节点
          </el-button>
          <el-button size="small" type="danger" :disabled="!selectedNodeKey && !selectedEdgeKey" @click="deleteSelected">
            删除
          </el-button>
          <el-button size="small" type="primary" :disabled="!dirty" :loading="saving" @click="saveMap">
            保存
          </el-button>
        </template>

        <el-divider direction="vertical" />

        <el-button size="small" :disabled="!mapJsonRaw" @click="downloadJson">下载 JSON</el-button>
        <el-button size="small" :disabled="!mapJsonRaw" @click="openInRmp">RMP 编辑</el-button>

        <el-divider direction="vertical" />

        <el-input
          v-model="bluemapUrlInput"
          placeholder="BlueMap 地址（如 http://localhost:8100）"
          size="small"
          style="width: 260px"
          clearable
          @change="saveBluemapUrl"
        >
          <template #prefix><el-icon><MapLocation /></el-icon></template>
        </el-input>
      </div>
    </div>

    <!-- Main content area -->
    <div class="wm-content" :class="layout">
      <!-- Left: Canvas map -->
      <div class="wm-canvas-wrap" v-show="layout !== 'right'" ref="canvasWrap">
        <canvas
          ref="mapCanvas"
          class="wm-canvas"
          @wheel.prevent="onWheel"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseLeave"
          @dblclick="onDblClick"
          @contextmenu.prevent="onContextMenu"
          @click="onCanvasClick"
          :style="{ cursor: canvasCursor }"
        />

        <!-- Node editor overlay (name + coords) -->
        <div
          v-if="editingNodeKey"
          class="wm-node-editor"
          :style="nodeEditorStyle"
          @mousedown.stop
          @click.stop
        >
          <div class="wm-node-editor-inner">
            <el-input
              v-if="editingNodeIsStation"
              ref="nodeNameInputRef"
              v-model="editingNodeName"
              size="small"
              placeholder="节点名称"
              @keyup.enter="focusCoordX"
              @keyup.esc="cancelNodeEdit"
            >
              <template #prefix><span class="wm-editor-prefix">名</span></template>
            </el-input>
            <div class="wm-node-editor-row">
              <el-input
                ref="nodeCoordXRef"
                v-model.number="editingNodeX"
                type="number"
                size="small"
                placeholder="X"
                @keyup.enter="focusCoordZ"
                @keyup.esc="cancelNodeEdit"
              >
                <template #prefix><span class="wm-editor-prefix">X</span></template>
              </el-input>
              <el-input
                ref="nodeCoordZRef"
                v-model.number="editingNodeZ"
                type="number"
                size="small"
                placeholder="Z"
                @keyup.enter="confirmNodeEdit"
                @keyup.esc="cancelNodeEdit"
              >
                <template #prefix><span class="wm-editor-prefix">Z</span></template>
              </el-input>
            </div>
            <div class="wm-node-editor-actions">
              <el-button size="small" @click.stop="cancelNodeEdit">取消</el-button>
              <el-button size="small" type="primary" @click.stop="confirmNodeEdit">确认</el-button>
            </div>
          </div>
        </div>

        <!-- HUD overlays -->
        <div class="wm-hud wm-coords">
          <template v-if="activeDim === 'nether'">
            下界 {{ hoverCoord.x }}, {{ hoverCoord.z }} &nbsp;|&nbsp; 主世界 {{ hoverCoord.x * 8 }}, {{ hoverCoord.z * 8 }}
          </template>
          <template v-else>
            末地 {{ hoverCoord.x }}, {{ hoverCoord.z }}
          </template>
        </div>

        <div class="wm-hud wm-edit-hint" v-if="editMode && !connectMode">
          双击添加站点 · Shift+双击添加虚拟节点 · 拖拽移动 · 单击选中 · 再次单击改名/坐标 · Del 删除
        </div>
        <div class="wm-hud wm-edit-hint wm-connect-hint" v-if="editMode && connectMode">
          {{ connectSourceKey ? '点击目标节点 或 点击线段（垂直插入）' : '点击起点节点' }} — ESC 取消
        </div>

        <!-- Trajectory playback panel -->
        <div class="wm-playback-bar" v-if="selectedPlayerName">
          <div class="wm-playback-title">
            <el-icon><User /></el-icon>
            <span>{{ selectedPlayerName }} 的轨迹</span>
            <span class="wm-playback-time" v-if="trajectory.length > 1">{{ playbackTimeDisplay }}</span>
            <el-button text size="small" class="wm-playback-close" @click="clearTrajectory">×</el-button>
          </div>
          <template v-if="trajectory.length > 1">
            <el-slider
              v-model="playbackProgressModel"
              :min="0" :max="100" :step="0.05"
              :show-tooltip="false"
              size="small"
              style="margin: 0 4px 2px"
            />
            <div class="wm-playback-controls">
              <el-button text size="small" @click="playbackRewind" title="跳到起点">⏮</el-button>
              <el-button
                text
                size="small"
                class="wm-playback-play-btn"
                :class="{ 'is-pausing': playbackPlaying }"
                @click="playbackToggle"
              >{{ playbackPlaying ? '⏸' : '▶' }}</el-button>
              <el-button text size="small" @click="playbackForward" title="跳到终点">⏭</el-button>
              <el-select v-model="playbackSpeed" size="small" style="width:68px" title="速度">
                <el-option :value="1"   label="1×" />
                <el-option :value="5"   label="5×" />
                <el-option :value="10"  label="10×" />
                <el-option :value="60"  label="60×" />
                <el-option :value="300" label="300×" />
              </el-select>
              <el-checkbox v-model="playbackLockCamera" size="small">锁定视角</el-checkbox>
            </div>
          </template>
          <div v-else class="wm-playback-nodata">
            {{ trajectory.length === 0 ? '轨迹加载中…' : '无轨迹数据' }}
          </div>
        </div>

        <!-- Map loading indicator -->
        <div class="wm-canvas-loading" v-if="mapLoading">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>

        <!-- Empty state: no server selected -->
        <div class="wm-canvas-empty" v-if="!selectedServerId && !mapLoading">
          <el-empty description="请选择一个服务器" />
        </div>

        <!-- Empty state: server selected but no map data -->
        <div class="wm-canvas-empty" v-if="selectedServerId && !mapLoading && !mapJsonRaw">
          <el-empty description="此服务器暂无地图">
            <template #extra>
              <el-button type="primary" size="small" @click="createBlankMap">新建空白地图</el-button>
            </template>
          </el-empty>
        </div>
      </div>

      <!-- Right: BlueMap iframe -->
      <div class="wm-bluemap-wrap" v-show="layout !== 'left'">
        <iframe
          v-if="bluemapUrl"
          :src="bluemapIframeSrc"
          class="wm-bluemap-iframe"
          allowfullscreen
          ref="bluemapFrame"
        />
        <div v-else class="wm-bluemap-empty">
          <el-empty description="未配置 BlueMap 地址">
            <template #description>
              <p>在顶栏输入 BlueMap 服务地址以启用实时地形视图</p>
            </template>
          </el-empty>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Grid, MapLocation, User, Loading } from '@element-plus/icons-vue'
import apiClient from '@/api'

// ─── State ────────────────────────────────────────────────────────────────────

const servers = ref([])
const serversLoading = ref(false)
const selectedServerId = ref(null)
const activeDim = ref('nether')
const layout = ref('left')       // 'left' | 'split' | 'right'
const editMode = ref(false)
const connectMode = ref(false)
const connectSourceKey = ref(null)
const showOfflinePlayers = ref(true)
const saving = ref(false)
const mapLoading = ref(false)
const dirty = ref(false)

// Map data
const mapJsonRaw = ref(null)   // raw RMP JSON object (mutated in place)

// View state (all coords are in "map units" = nether blocks for nether dim, end blocks for end dim)
const view = reactive({ cx: 0, cz: 0, scale: 0.8, cssW: 800, cssH: 600 })

// Selection & editing
const selectedNodeKey = ref(null)
const selectedEdgeKey = ref(null)
const editingNodeKey = ref(null)
const editingNodeName = ref('')
const editingNodeX = ref(0)
const editingNodeZ = ref(0)
const editingNodeIsStation = ref(true)
const addVirtualMode = ref(false)
const nodeNameInputRef = ref(null)
const nodeCoordXRef = ref(null)
const nodeCoordZRef = ref(null)

// Hover coord display
const hoverCoord = reactive({ x: 0, z: 0 })

// Players
const players = ref([])
const selectedPlayerName = ref(null)
const trajectory = ref([])
const trajectoryFromTime = ref(null)   // ISO string for 'since' query param
const playerRefreshTimer = ref(null)

// Avatars (uuid -> HTMLImageElement)
const avatarCache = reactive({})

// Playback
const playbackPlaying = ref(false)
const playbackSpeed = ref(60)          // speed multiplier (× real time)
const playbackLockCamera = ref(true)
const playbackCurrentTs = ref(0)       // virtual playback timestamp (ms)
let playbackRafHandle = null
let playbackLastRealTs = null

// BlueMap
const bluemapUrlInput = ref('')
const bluemapUrl = ref('')
const bluemapIframeSrc = ref('')

// Canvas refs
const canvasWrap = ref(null)
const mapCanvas = ref(null)

// Mouse interaction state
const mouse = reactive({
  isDown: false, lastX: 0, lastY: 0,
  startX: 0, startY: 0, hasMoved: false,
  dragNodeKey: null,
})

// RAF scheduling
let rafId = null

// ─── Computed ─────────────────────────────────────────────────────────────────

const currentServer = computed(() => servers.value.find(s => s.id === selectedServerId.value))

const parsedNodes = computed(() => {
  if (!mapJsonRaw.value) return []
  return (mapJsonRaw.value.graph?.nodes || []).map(n => ({
    key: n.key,
    x: n.attributes?.x ?? 0,
    z: n.attributes?.y ?? 0,   // RMP uses y for world-z
    name: extractNodeName(n),
    visible: n.attributes?.visible !== false,
    isStation: n.attributes?.type !== 'virtual',
    isVirtual: n.attributes?.type === 'virtual',
    rawNode: n,
  }))
})

const nodeMap = computed(() => new Map(parsedNodes.value.map(n => [n.key, n])))

const parsedEdges = computed(() => {
  if (!mapJsonRaw.value) return []
  return (mapJsonRaw.value.graph?.edges || []).map(e => {
    const src = nodeMap.value.get(e.source)
    const tgt = nodeMap.value.get(e.target)
    if (!src || !tgt) return null
    return {
      key: e.key,
      source: e.source,
      target: e.target,
      x1: src.x, z1: src.z,
      x2: tgt.x, z2: tgt.z,
      color: extractEdgeColor(e),
    }
  }).filter(Boolean)
})

const canvasCursor = computed(() => {
  if (connectMode.value) return 'crosshair'
  if (editMode.value) return 'default'
  return 'grab'
})

const nodeEditorStyle = computed(() => {
  if (!editingNodeKey.value) return { display: 'none' }
  const node = nodeMap.value.get(editingNodeKey.value)
  if (!node) return { display: 'none' }
  const [sx, sy] = w2c(node.x, node.z)
  const pw = 210
  const ph = node.isStation ? 132 : 96
  // Keep panel on-screen
  const left = Math.max(4, Math.min(view.cssW - pw - 4, sx - pw / 2))
  const top  = Math.max(4, Math.min(view.cssH - ph - 4, sy - ph - 12))
  return { position: 'absolute', left: `${left}px`, top: `${top}px`, width: `${pw}px`, zIndex: 20 }
})

// ─── Playback Computed ────────────────────────────────────────────────────────

const playbackStartTs = computed(() => {
  const pt = trajectory.value.find(p => p.ts)
  return pt ? new Date(pt.ts).getTime() : 0
})

const playbackEndTs = computed(() => {
  const pts = trajectory.value
  for (let i = pts.length - 1; i >= 0; i--) {
    if (pts[i].ts) return new Date(pts[i].ts).getTime()
  }
  return 0
})

/** Index of the last point whose ts ≤ playbackCurrentTs (binary search) */
const playbackIdx = computed(() => {
  const pts = trajectory.value
  if (!pts.length) return 0
  const ts = playbackCurrentTs.value
  let lo = 0, hi = pts.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    const midTs = pts[mid].ts ? new Date(pts[mid].ts).getTime() : 0
    if (midTs <= ts) lo = mid; else hi = mid - 1
  }
  return lo
})

/** Linearly interpolated world position between playbackIdx and playbackIdx+1 */
const playbackPosition = computed(() => {
  const pts = trajectory.value
  if (!pts.length) return null
  const idx = playbackIdx.value
  if (idx >= pts.length - 1) {
    const last = pts[pts.length - 1]
    return { x: last.x, z: last.z, dim: last.dim }
  }
  const p1 = pts[idx], p2 = pts[idx + 1]
  const t1 = p1.ts ? new Date(p1.ts).getTime() : playbackCurrentTs.value
  const t2 = p2.ts ? new Date(p2.ts).getTime() : playbackCurrentTs.value
  const frac = t2 > t1 ? Math.max(0, Math.min(1, (playbackCurrentTs.value - t1) / (t2 - t1))) : 0
  return { x: p1.x + (p2.x - p1.x) * frac, z: p1.z + (p2.z - p1.z) * frac, dim: p1.dim }
})

/** Two-way writable: progress in [0, 100] ↔ playbackCurrentTs */
const playbackProgressModel = computed({
  get: () => {
    const dur = playbackEndTs.value - playbackStartTs.value
    if (!dur) return 0
    return Math.max(0, Math.min(100,
      (playbackCurrentTs.value - playbackStartTs.value) / dur * 100))
  },
  set: (pct) => {
    const dur = playbackEndTs.value - playbackStartTs.value
    playbackCurrentTs.value = playbackStartTs.value + dur * Math.max(0, Math.min(100, pct)) / 100
    if (playbackLockCamera.value && playbackPosition.value) {
      const { mx, mz } = playerToMap(playbackPosition.value.x, playbackPosition.value.z, playbackPosition.value.dim)
      view.cx = mx; view.cz = mz
    }
    scheduleRender()
  },
})

function fmtTs(ts) {
  if (!ts) return '--:--:--'
  const d = new Date(ts)
  const H = String(d.getHours()).padStart(2, '0')
  const M = String(d.getMinutes()).padStart(2, '0')
  const S = String(d.getSeconds()).padStart(2, '0')
  const startDay = playbackStartTs.value ? new Date(playbackStartTs.value).toDateString() : null
  const endDay   = playbackEndTs.value   ? new Date(playbackEndTs.value).toDateString()   : null
  if (startDay && endDay && startDay !== endDay) {
    // span multiple days: prefix with MM-DD
    const mon = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${mon}-${day} ${H}:${M}:${S}`
  }
  return `${H}:${M}:${S}`
}

const playbackTimeDisplay = computed(() => {
  if (!playbackStartTs.value || !playbackEndTs.value) return ''
  return `${fmtTs(playbackCurrentTs.value)} / ${fmtTs(playbackEndTs.value)}`
})

// ─── Helpers ──────────────────────────────────────────────────────────────────

function extractNodeName(rawNode) {
  const type = rawNode.attributes?.type
  if (!type || type === 'virtual') return null
  const names = rawNode.attributes?.[type]?.names || []
  return names[0]?.split('\n')[0] || null
}

function extractEdgeColor(rawEdge) {
  try {
    const style = rawEdge.attributes?.style || {}
    const sc = style['single-color']
    if (sc) {
      const c = sc.color
      if (Array.isArray(c) && c.length >= 3) return c[2]
    }
  } catch {}
  return '#cbd5e1'
}

/** world → canvas CSS pixel coords */
function w2c(wx, wz) {
  return [
    (wx - view.cx) * view.scale + view.cssW / 2,
    (wz - view.cz) * view.scale + view.cssH / 2,
  ]
}

/** canvas CSS pixel → world coords */
function c2w(cx, cy) {
  return [
    (cx - view.cssW / 2) / view.scale + view.cx,
    (cy - view.cssH / 2) / view.scale + view.cz,
  ]
}

/** Convert player position to map coordinate space */
function playerToMap(x, z, dim) {
  const d = String(dim ?? '')
  const isOverworld = d === 'minecraft:overworld' || d === '0'
  const isNether = d === 'minecraft:the_nether' || d === '-1'
  const isEnd = d === 'minecraft:the_end' || d === '1'
  if (isOverworld) return { mx: x / 8, mz: z / 8, mapDim: 'nether' }
  if (isNether) return { mx: x, mz: z, mapDim: 'nether' }
  if (isEnd) return { mx: x, mz: z, mapDim: 'end' }
  return { mx: x / 8, mz: z / 8, mapDim: 'nether' }  // default assume overworld
}

function scheduleRender() {
  if (rafId) return
  rafId = requestAnimationFrame(() => { rafId = null; render() })
}

// ─── Canvas Setup & Resize ────────────────────────────────────────────────────

let resizeObserver = null

function setupCanvas() {
  const wrap = canvasWrap.value
  const canvas = mapCanvas.value
  if (!wrap || !canvas) return
  const dpr = window.devicePixelRatio || 1
  const w = wrap.clientWidth
  const h = wrap.clientHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = `${w}px`
  canvas.style.height = `${h}px`
  view.cssW = w
  view.cssH = h
  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)
  scheduleRender()
}

// ─── Canvas Rendering ─────────────────────────────────────────────────────────

function render() {
  const canvas = mapCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, view.cssW, view.cssH)

  drawGrid(ctx)
  drawEdges(ctx)
  drawNodes(ctx)
  drawTrajectory(ctx)
  drawPlayers(ctx)
}

function drawGrid(ctx) {
  const target = 100
  const world = target / view.scale
  const exp = Math.floor(Math.log10(world))
  const frac = world / 10 ** exp
  const nice = frac < 1.5 ? 1 : frac < 3.5 ? 2 : frac < 7.5 ? 5 : 10
  const step = nice * 10 ** exp

  const [sx0, sz0] = c2w(0, 0)
  const [sx1, sz1] = c2w(view.cssW, view.cssH)

  ctx.strokeStyle = '#e8eaf0'
  ctx.lineWidth = 1

  for (let x = Math.floor(sx0 / step) * step; x <= sx1 + step; x += step) {
    const [px] = w2c(x, 0)
    ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, view.cssH); ctx.stroke()
  }
  for (let z = Math.floor(sz0 / step) * step; z <= sz1 + step; z += step) {
    const [, py] = w2c(0, z)
    ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(view.cssW, py); ctx.stroke()
  }

  // axes
  const [ox] = w2c(0, 0); const [, oy] = w2c(0, 0)
  ctx.strokeStyle = '#c0c4cc'; ctx.lineWidth = 1.5
  if (ox >= 0 && ox <= view.cssW) {
    ctx.beginPath(); ctx.moveTo(ox, 0); ctx.lineTo(ox, view.cssH); ctx.stroke()
  }
  if (oy >= 0 && oy <= view.cssH) {
    ctx.beginPath(); ctx.moveTo(0, oy); ctx.lineTo(view.cssW, oy); ctx.stroke()
  }

  // scale bar
  const barWorld = nice * 10 ** exp
  const barPx = barWorld * view.scale
  const bx = view.cssW - 20
  const by = 24
  ctx.strokeStyle = '#60707a'; ctx.lineWidth = 2
  ctx.beginPath(); ctx.moveTo(bx - barPx, by); ctx.lineTo(bx, by); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(bx - barPx, by - 5); ctx.lineTo(bx - barPx, by + 5); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(bx, by - 5); ctx.lineTo(bx, by + 5); ctx.stroke()
  ctx.font = '11px sans-serif'; ctx.fillStyle = '#60707a'
  ctx.textAlign = 'center'
  ctx.fillText(`${barWorld >= 1000 ? barWorld / 1000 + 'k' : barWorld} blk`, bx - barPx / 2, by - 7)
}

function drawEdges(ctx) {
  for (const edge of parsedEdges.value) {
    const [x1, y1] = w2c(edge.x1, edge.z1)
    const [x2, y2] = w2c(edge.x2, edge.z2)
    const isSelected = edge.key === selectedEdgeKey.value
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2)
    ctx.strokeStyle = isSelected ? '#f59e0b' : edge.color
    ctx.lineWidth = isSelected ? 4 : 2
    ctx.stroke()
  }
}

function drawNodes(ctx) {
  const showLabels = view.scale > 0.12
  for (const node of parsedNodes.value) {
    if (!node.visible) continue
    // Virtual nodes only drawn in edit mode; always draw stations
    if (node.isVirtual && !editMode.value) continue

    const [sx, sy] = w2c(node.x, node.z)
    if (sx < -20 || sx > view.cssW + 20 || sy < -20 || sy > view.cssH + 20) continue

    const isSelected = node.key === selectedNodeKey.value
    const isConnectSrc = node.key === connectSourceKey.value

    if (node.isVirtual) {
      // Draw as small diamond
      const r = isSelected ? 6 : 4
      if (isConnectSrc || isSelected) {
        ctx.beginPath(); ctx.arc(sx, sy, r + 4, 0, Math.PI * 2)
        ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1.5; ctx.stroke()
      }
      ctx.beginPath()
      ctx.moveTo(sx, sy - r); ctx.lineTo(sx + r, sy)
      ctx.lineTo(sx, sy + r); ctx.lineTo(sx - r, sy)
      ctx.closePath()
      ctx.fillStyle = isSelected ? '#f59e0b' : '#94a3b8'
      ctx.strokeStyle = isSelected ? '#d97706' : '#64748b'
      ctx.lineWidth = 1
      ctx.fill(); ctx.stroke()
    } else {
      // Station node
      const r = isSelected ? 7 : 5
      if (isConnectSrc) {
        ctx.beginPath(); ctx.arc(sx, sy, r + 4, 0, Math.PI * 2)
        ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 2; ctx.stroke()
      }
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2)
      ctx.fillStyle = isSelected ? '#f59e0b' : '#fff'
      ctx.strokeStyle = isSelected ? '#d97706' : '#94a3b8'
      ctx.lineWidth = isSelected ? 2 : 1.5
      ctx.fill(); ctx.stroke()

      if (showLabels && node.name) {
        ctx.font = `${Math.min(14, Math.max(10, view.scale * 18))}px sans-serif`
        ctx.fillStyle = '#1e2332'
        ctx.textAlign = 'center'
        ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 3
        ctx.strokeText(node.name, sx, sy - r - 4)
        ctx.fillText(node.name, sx, sy - r - 4)
      }
    }
  }
}

function drawTrajectory(ctx) {
  if (!trajectory.value.length) return
  const currentMapDim = activeDim.value === 'end' ? 'end' : 'nether'
  const hasPlayback = playbackEndTs.value > playbackStartTs.value

  // Full path (faint background when playback is available)
  ctx.lineWidth = 1.5
  ctx.setLineDash([5, 4])
  let lastDim = null, started = false
  ctx.beginPath()
  for (let i = 0; i < trajectory.value.length; i++) {
    const pt = trajectory.value[i]
    const { mx, mz, mapDim } = playerToMap(pt.x, pt.z, pt.dim)
    if (mapDim !== currentMapDim) { started = false; continue }
    const [sx, sy] = w2c(mx, mz)
    if (!started || mapDim !== lastDim) { ctx.moveTo(sx, sy); started = true }
    else ctx.lineTo(sx, sy)
    lastDim = mapDim
  }
  ctx.strokeStyle = hasPlayback ? 'rgba(99,102,241,0.25)' : '#6366f1'
  ctx.stroke()
  ctx.setLineDash([])

  if (!hasPlayback) {
    // Static: dot at last point
    const last = trajectory.value[trajectory.value.length - 1]
    const { mx, mz, mapDim } = playerToMap(last.x, last.z, last.dim)
    if (mapDim === currentMapDim) {
      const [sx, sy] = w2c(mx, mz)
      ctx.beginPath(); ctx.arc(sx, sy, 5, 0, Math.PI * 2)
      ctx.fillStyle = '#6366f1'; ctx.fill()
    }
    return
  }

  // Played portion (solid, up to current playback index)
  const upTo = playbackIdx.value
  ctx.lineWidth = 2
  started = false; lastDim = null
  ctx.beginPath()
  for (let i = 0; i <= upTo; i++) {
    const pt = trajectory.value[i]
    const { mx, mz, mapDim } = playerToMap(pt.x, pt.z, pt.dim)
    if (mapDim !== currentMapDim) { started = false; continue }
    const [sx, sy] = w2c(mx, mz)
    if (!started || mapDim !== lastDim) { ctx.moveTo(sx, sy); started = true }
    else ctx.lineTo(sx, sy)
    lastDim = mapDim
  }
  ctx.strokeStyle = '#6366f1'; ctx.stroke()

  // Playback head marker at interpolated position
  const pos = playbackPosition.value
  if (pos) {
    const { mx, mz, mapDim } = playerToMap(pos.x, pos.z, pos.dim)
    if (mapDim === currentMapDim) {
      const [sx, sy] = w2c(mx, mz)
      ctx.beginPath(); ctx.arc(sx, sy, 7, 0, Math.PI * 2)
      ctx.fillStyle = '#6366f1'; ctx.fill()
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke()
    }
  }
}

function drawPlayers(ctx) {
  const currentMapDim = activeDim.value === 'end' ? 'end' : 'nether'
  for (const player of players.value) {
    if (!player.is_online && !showOfflinePlayers.value) continue
    if (player.x === null || player.x === undefined) continue
    const { mx, mz, mapDim } = playerToMap(player.x, player.z, player.dim)
    if (mapDim !== currentMapDim) continue
    const [sx, sy] = w2c(mx, mz)
    if (sx < -30 || sx > view.cssW + 30 || sy < -30 || sy > view.cssH + 30) continue
    drawPlayerMarker(ctx, player, sx, sy)
  }
}

function drawPlayerMarker(ctx, player, sx, sy) {
  const R = 10
  const isOnline = player.is_online
  const isSelected = player.player_name === selectedPlayerName.value

  // selection ring
  if (isSelected) {
    ctx.beginPath(); ctx.arc(sx, sy, R + 4, 0, Math.PI * 2)
    ctx.strokeStyle = '#6366f1'; ctx.lineWidth = 2; ctx.stroke()
  }

  const avatar = avatarCache[player.uuid]
  if (avatar) {
    ctx.save()
    ctx.beginPath(); ctx.arc(sx, sy, R, 0, Math.PI * 2); ctx.clip()
    ctx.drawImage(avatar, sx - R, sy - R, R * 2, R * 2)
    ctx.restore()
    ctx.beginPath(); ctx.arc(sx, sy, R, 0, Math.PI * 2)
    ctx.strokeStyle = isOnline ? '#22c55e' : '#6b7280'; ctx.lineWidth = 2; ctx.stroke()
  } else {
    ctx.beginPath(); ctx.arc(sx, sy, R, 0, Math.PI * 2)
    ctx.fillStyle = isOnline ? '#22c55e' : '#6b7280'
    ctx.fill()
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke()
    // initials
    ctx.font = 'bold 9px sans-serif'; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'
    ctx.fillText(player.player_name.slice(0, 2).toUpperCase(), sx, sy + 3)
  }

  // status dot
  if (isOnline) {
    ctx.beginPath(); ctx.arc(sx + R - 3, sy + R - 3, 3, 0, Math.PI * 2)
    ctx.fillStyle = '#22c55e'; ctx.fill()
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke()
  }

  // name label
  ctx.font = '11px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillStyle = isOnline ? '#16a34a' : '#6b7280'
  ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 3
  ctx.strokeText(player.player_name, sx, sy - R - 4)
  ctx.fillText(player.player_name, sx, sy - R - 4)
}

// ─── Hit Testing ──────────────────────────────────────────────────────────────

function hitTestNode(cx, cy, radius = 10) {
  // In edit mode: hit all visible nodes (including virtual); in view mode: stations only
  for (const node of parsedNodes.value) {
    if (!node.visible) continue
    if (node.isVirtual && !editMode.value) continue
    const [sx, sy] = w2c(node.x, node.z)
    const r = node.isVirtual ? Math.max(6, radius * 0.7) : radius
    if (Math.hypot(cx - sx, cy - sy) <= r) return node
  }
  return null
}

function hitTestEdge(cx, cy, dist = 6) {
  for (const edge of parsedEdges.value) {
    const [x1, y1] = w2c(edge.x1, edge.z1)
    const [x2, y2] = w2c(edge.x2, edge.z2)
    const dx = x2 - x1, dy = y2 - y1, len2 = dx * dx + dy * dy
    if (len2 === 0) continue
    const t = Math.max(0, Math.min(1, ((cx - x1) * dx + (cy - y1) * dy) / len2))
    if (Math.hypot(cx - x1 - t * dx, cy - y1 - t * dy) <= dist) return edge
  }
  return null
}

function hitTestPlayer(cx, cy, radius = 14) {
  const currentMapDim = activeDim.value === 'end' ? 'end' : 'nether'
  for (const player of players.value) {
    if (!player.is_online && !showOfflinePlayers.value) continue
    if (player.x === null || player.x === undefined) continue
    const { mx, mz, mapDim } = playerToMap(player.x, player.z, player.dim)
    if (mapDim !== currentMapDim) continue
    const [sx, sy] = w2c(mx, mz)
    if (Math.hypot(cx - sx, cy - sy) <= radius) return player
  }
  return null
}

// ─── Mouse Events ─────────────────────────────────────────────────────────────

function onMouseDown(e) {
  if (e.button !== 0) return
  const { cx, cy } = evCoords(e)
  mouse.isDown = true; mouse.lastX = cx; mouse.lastY = cy
  mouse.startX = cx; mouse.startY = cy; mouse.hasMoved = false
  mouse.dragNodeKey = null

  if (editMode.value && !connectMode.value) {
    const node = hitTestNode(cx, cy)
    if (node) { mouse.dragNodeKey = node.key }
  }
}

function onMouseMove(e) {
  const { cx, cy } = evCoords(e)
  const [wx, wz] = c2w(cx, cy)
  hoverCoord.x = Math.round(wx); hoverCoord.z = Math.round(wz)

  if (!mouse.isDown) return
  const dx = cx - mouse.lastX, dy = cy - mouse.lastY
  if (Math.abs(cx - mouse.startX) > 3 || Math.abs(cy - mouse.startY) > 3) mouse.hasMoved = true

  if (editMode.value && mouse.dragNodeKey) {
    // Drag node
    const rawNode = mapJsonRaw.value?.graph?.nodes?.find(n => n.key === mouse.dragNodeKey)
    if (rawNode) {
      rawNode.attributes.x += dx / view.scale
      rawNode.attributes.y += dy / view.scale
      dirty.value = true
    }
  } else {
    // Pan
    view.cx -= dx / view.scale
    view.cz -= dy / view.scale
  }
  mouse.lastX = cx; mouse.lastY = cy
  scheduleRender()
}

function onMouseUp(e) {
  const { cx, cy } = evCoords(e)

  if (!mouse.hasMoved && editMode.value) {
    if (mouse.dragNodeKey) {
      if (selectedNodeKey.value === mouse.dragNodeKey) {
        // second click on already-selected node → start name editing
        startNodeEdit(mouse.dragNodeKey)
      } else {
        selectedNodeKey.value = mouse.dragNodeKey
        selectedEdgeKey.value = null
      }
    } else {
      // click on empty area
      const edge = hitTestEdge(cx, cy)
      if (edge) {
        selectedEdgeKey.value = edge.key
        selectedNodeKey.value = null
      } else {
        selectedNodeKey.value = null
        selectedEdgeKey.value = null
      }
    }
  }

  mouse.isDown = false; mouse.dragNodeKey = null
  scheduleRender()
}

function onMouseLeave() {
  mouse.isDown = false; mouse.dragNodeKey = null
}

function onCanvasClick(e) {
  const { cx, cy } = evCoords(e)

  if (connectMode.value) {
    const node = hitTestNode(cx, cy)
    if (!connectSourceKey.value) {
      // Set source: only accept any visible node
      if (node) {
        connectSourceKey.value = node.key
        selectedNodeKey.value = node.key
      }
    } else {
      // Set target: can be a node or an edge
      if (node && node.key !== connectSourceKey.value) {
        addEdge(connectSourceKey.value, node.key)
        connectSourceKey.value = null; connectMode.value = false; selectedNodeKey.value = null
      } else if (!node) {
        // Try to hit an edge for perpendicular insertion
        const edge = hitTestEdge(cx, cy, 12)
        if (edge) {
          connectToEdge(connectSourceKey.value, edge)
        }
      }
    }
    scheduleRender()
    return
  }

  if (!mouse.hasMoved) {
    // Check player clicks (regardless of edit mode)
    const player = hitTestPlayer(cx, cy)
    if (player) {
      onPlayerClick(player)
      return
    }
  }
}

/**
 * Perpendicular connection: from sourceKey node to an existing edge.
 * Finds the foot of the perpendicular from source to the edge line,
 * inserts a virtual node there, splits the edge, and connects source→virtual.
 */
function connectToEdge(sourceKey, edge) {
  if (!mapJsonRaw.value) return
  const srcNode = nodeMap.value.get(sourceKey)
  if (!srcNode) return

  // Compute perpendicular foot (world coords)
  const ax = edge.x1, az = edge.z1, bx = edge.x2, bz = edge.z2
  const dx = bx - ax, dz = bz - az
  const len2 = dx * dx + dz * dz
  if (len2 === 0) return
  const t = Math.max(0, Math.min(1, ((srcNode.x - ax) * dx + (srcNode.z - az) * dz) / len2))
  const px = ax + t * dx
  const pz = az + t * dz

  // Create virtual node at foot
  const virtKey = `misc_node_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
  mapJsonRaw.value.graph.nodes.push({
    key: virtKey,
    attributes: { visible: true, zIndex: 0, x: px, y: pz, type: 'virtual', virtual: {} },
  })

  // Split original edge A→B into A→virt and virt→B (preserving original style)
  const origEdge = mapJsonRaw.value.graph.edges.find(e => e.key === edge.key)
  if (origEdge) {
    const origSrc = origEdge.source
    const origTgt = origEdge.target
    const origAttrs = JSON.parse(JSON.stringify(origEdge.attributes || {}))
    const idx = mapJsonRaw.value.graph.edges.indexOf(origEdge)
    mapJsonRaw.value.graph.edges.splice(idx, 1)
    const ts = Date.now()
    mapJsonRaw.value.graph.edges.push(
      { key: `line_${ts}_a`, source: origSrc, target: virtKey, attributes: origAttrs },
      { key: `line_${ts}_b`, source: virtKey,  target: origTgt, attributes: JSON.parse(JSON.stringify(origAttrs)) },
    )
  }

  // Connect source node → virtual foot
  addEdge(sourceKey, virtKey)

  connectSourceKey.value = null; connectMode.value = false; selectedNodeKey.value = null
  dirty.value = true
  scheduleRender()
}

function onDblClick(e) {
  if (!editMode.value) return
  const { cx, cy } = evCoords(e)
  if (hitTestNode(cx, cy)) return   // don't add if clicking existing node
  const [wx, wz] = c2w(cx, cy)
  const useVirtual = e.shiftKey || addVirtualMode.value
  addNode(wx, wz, useVirtual ? 'virtual' : 'station')
  if (addVirtualMode.value) addVirtualMode.value = false  // one-shot
}

function onWheel(e) {
  const { cx, cy } = evCoords(e)
  const factor = e.deltaY > 0 ? 0.85 : 1 / 0.85
  const [wx, wz] = c2w(cx, cy)
  view.scale = Math.max(0.015, Math.min(80, view.scale * factor))
  view.cx = wx - (cx - view.cssW / 2) / view.scale
  view.cz = wz - (cy - view.cssH / 2) / view.scale
  scheduleRender()
}

function onContextMenu(e) {
  if (!editMode.value) return
  // Right-click: deselect or cancel connect
  if (connectMode.value) { connectMode.value = false; connectSourceKey.value = null }
  selectedNodeKey.value = null; selectedEdgeKey.value = null
  scheduleRender()
}

function evCoords(e) {
  const rect = mapCanvas.value.getBoundingClientRect()
  return { cx: e.clientX - rect.left, cy: e.clientY - rect.top }
}

// ─── Keyboard ─────────────────────────────────────────────────────────────────

function onKeyDown(e) {
  if (e.key === 'Escape') {
    if (connectMode.value) { connectMode.value = false; connectSourceKey.value = null; scheduleRender() }
    if (editingNodeKey.value) cancelNodeEdit()
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && editMode.value && !editingNodeKey.value) {
    if (document.activeElement === document.body || document.activeElement === mapCanvas.value) {
      deleteSelected()
    }
  }
}

// ─── Edit Operations ──────────────────────────────────────────────────────────

function addNode(wx, wz, type = 'station') {
  if (!mapJsonRaw.value) return
  if (type === 'virtual') {
    const key = `misc_node_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    mapJsonRaw.value.graph.nodes.push({
      key,
      attributes: { visible: true, zIndex: 0, x: wx, y: wz, type: 'virtual', virtual: {} },
    })
    dirty.value = true
    selectedNodeKey.value = key
    nextTick(() => startNodeEdit(key))
  } else {
    const key = `stn_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    mapJsonRaw.value.graph.nodes.push({
      key,
      attributes: {
        visible: true, zIndex: 0, x: wx, y: wz,
        type: 'shmetro-basic',
        'shmetro-basic': { names: ['新节点'], nameOffsetX: 'middle', nameOffsetY: 'top' },
      },
    })
    dirty.value = true
    selectedNodeKey.value = key
    nextTick(() => startNodeEdit(key))
  }
  scheduleRender()
}

function addEdge(srcKey, tgtKey) {
  if (!mapJsonRaw.value) return
  const key = `line_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
  mapJsonRaw.value.graph.edges.push({
    key, source: srcKey, target: tgtKey,
    attributes: { style: {} },
  })
  dirty.value = true
  scheduleRender()
}

function deleteSelected() {
  if (!mapJsonRaw.value) return
  if (selectedNodeKey.value) {
    const nodes = mapJsonRaw.value.graph.nodes
    const idx = nodes.findIndex(n => n.key === selectedNodeKey.value)
    if (idx >= 0) {
      nodes.splice(idx, 1)
      mapJsonRaw.value.graph.edges = mapJsonRaw.value.graph.edges.filter(
        e => e.source !== selectedNodeKey.value && e.target !== selectedNodeKey.value
      )
    }
    selectedNodeKey.value = null
  } else if (selectedEdgeKey.value) {
    const edges = mapJsonRaw.value.graph.edges
    const idx = edges.findIndex(e => e.key === selectedEdgeKey.value)
    if (idx >= 0) edges.splice(idx, 1)
    selectedEdgeKey.value = null
  }
  dirty.value = true
  scheduleRender()
}

function startNodeEdit(key) {
  const node = nodeMap.value.get(key)
  if (!node) return
  editingNodeKey.value = key
  editingNodeName.value = node.name || ''
  editingNodeX.value = Math.round(node.x)
  editingNodeZ.value = Math.round(node.z)
  editingNodeIsStation.value = node.isStation
  nextTick(() => {
    if (node.isStation) nodeNameInputRef.value?.focus()
    else nodeCoordXRef.value?.focus()
  })
}

function confirmNodeEdit() {
  if (!editingNodeKey.value || !mapJsonRaw.value) return
  const rawNode = mapJsonRaw.value.graph.nodes.find(n => n.key === editingNodeKey.value)
  if (rawNode) {
    // Apply name (station only)
    const type = rawNode.attributes?.type
    if (type && type !== 'virtual' && rawNode.attributes[type]) {
      const names = rawNode.attributes[type].names || ['']
      const rest = names[0]?.includes('\n') ? names[0].substring(names[0].indexOf('\n')) : ''
      names[0] = editingNodeName.value + rest
      rawNode.attributes[type].names = names
    }
    // Apply coordinates
    rawNode.attributes.x = Number(editingNodeX.value)
    rawNode.attributes.y = Number(editingNodeZ.value)  // RMP uses y for z
    dirty.value = true
  }
  editingNodeKey.value = null
  scheduleRender()
}

function focusCoordX() { nextTick(() => nodeCoordXRef.value?.focus()) }
function focusCoordZ() { nextTick(() => nodeCoordZRef.value?.focus()) }

function cancelNodeEdit() {
  editingNodeKey.value = null
}

function toggleConnectMode() {
  connectMode.value = !connectMode.value
  if (!connectMode.value) connectSourceKey.value = null
  addVirtualMode.value = false
}

function toggleAddVirtualMode() {
  addVirtualMode.value = !addVirtualMode.value
  if (addVirtualMode.value) connectMode.value = false
}

function onEditModeChange(val) {
  if (!val) {
    connectMode.value = false; connectSourceKey.value = null
    selectedNodeKey.value = null; selectedEdgeKey.value = null
    editingNodeKey.value = null; addVirtualMode.value = false
  }
  scheduleRender()
}

// ─── Data Loading ─────────────────────────────────────────────────────────────

async function loadServers() {
  serversLoading.value = true
  try {
    const { data } = await apiClient.get('/api/servers')
    servers.value = data
  } catch (e) {
    ElMessage.error('加载服务器列表失败')
  } finally {
    serversLoading.value = false
  }
}

async function loadMapData() {
  if (!selectedServerId.value) { mapJsonRaw.value = null; return }
  mapLoading.value = true
  try {
    const { data } = await apiClient.get(
      `/api/tools/world-map/${selectedServerId.value}/map-data`,
      { params: { dim: activeDim.value } }
    )
    mapJsonRaw.value = data
    dirty.value = false
    fitView()
  } catch (e) {
    if (e.response?.status !== 404) ElMessage.error('加载地图数据失败')
    mapJsonRaw.value = null
  } finally {
    mapLoading.value = false
    scheduleRender()
  }
}

function createBlankMap() {
  mapJsonRaw.value = { graph: { nodes: [], edges: [] } }
  dirty.value = true
  editMode.value = true
  scheduleRender()
}

async function loadPlayers() {
  if (!selectedServerId.value) return
  try {
    const { data } = await apiClient.get(`/api/tools/world-map/${selectedServerId.value}/players`)
    players.value = data
    // preload avatars
    for (const p of data) {
      if (p.uuid && !avatarCache[p.uuid]) loadAvatar(p.uuid)
    }
    scheduleRender()
  } catch {}
}

async function loadConfig() {
  if (!selectedServerId.value) return
  try {
    const { data } = await apiClient.get(`/api/tools/world-map/${selectedServerId.value}/config`)
    bluemapUrl.value = data.bluemap_url || ''
    bluemapUrlInput.value = bluemapUrl.value
    if (bluemapUrl.value) bluemapIframeSrc.value = bluemapUrl.value
  } catch {}
}

async function loadTrajectory(playerName) {
  try {
    const params = {}
    if (trajectoryFromTime.value) params.since = trajectoryFromTime.value
    const { data } = await apiClient.get(
      `/api/tools/world-map/${selectedServerId.value}/trajectory/${encodeURIComponent(playerName)}`,
      { params }
    )
    trajectory.value = data
    if (data.length > 0 && data[0].ts) {
      playbackCurrentTs.value = new Date(data[0].ts).getTime()
    }
    scheduleRender()
  } catch {
    trajectory.value = []
  }
}

function onTrajectoryFromTimeChange() {
  if (selectedPlayerName.value) {
    trajectory.value = []
    loadTrajectory(selectedPlayerName.value)
  }
}

function loadAvatar(uuid) {
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.src = `https://mc-heads.net/avatar/${uuid}/32`
  img.onload = () => { avatarCache[uuid] = img; scheduleRender() }
  img.onerror = () => {
    const img2 = new Image()
    img2.crossOrigin = 'anonymous'
    img2.src = `https://crafatar.com/avatars/${uuid}?size=32&overlay`
    img2.onload = () => { avatarCache[uuid] = img2; scheduleRender() }
  }
}

// ─── Save & Export ────────────────────────────────────────────────────────────

async function saveMap() {
  if (!selectedServerId.value || !mapJsonRaw.value) return
  saving.value = true
  try {
    await apiClient.put(
      `/api/tools/world-map/${selectedServerId.value}/map-data`,
      mapJsonRaw.value,
      { params: { dim: activeDim.value } }
    )
    dirty.value = false
    ElMessage.success('地图已保存')
  } catch (e) {
    ElMessage.error(`保存失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    saving.value = false
  }
}

function downloadJson() {
  if (!mapJsonRaw.value) return
  const blob = new Blob([JSON.stringify(mapJsonRaw.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${activeDim.value === 'end' ? 'the_end' : 'the_nether'}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function openInRmp() {
  if (!mapJsonRaw.value) return
  const jsonStr = JSON.stringify(mapJsonRaw.value)
  try {
    await navigator.clipboard.writeText(jsonStr)
    ElMessage.success('JSON 已复制到剪贴板，请在 RMP 中使用 Import → Paste JSON 导入', { duration: 5000 })
  } catch {
    ElMessage.warning('无法自动复制，请手动下载 JSON 后导入 RMP')
  }
  window.open('https://railmapgen.gitlab.io/?app=rmp', '_blank')
}

async function saveBluemapUrl() {
  if (!selectedServerId.value) return
  try {
    await apiClient.put(`/api/tools/world-map/${selectedServerId.value}/config`, {
      bluemap_url: bluemapUrlInput.value,
    })
    bluemapUrl.value = bluemapUrlInput.value
    if (bluemapUrl.value) bluemapIframeSrc.value = bluemapUrl.value
    else bluemapIframeSrc.value = ''
    ElMessage.success('BlueMap 地址已保存')
  } catch {}
}

// ─── Player interaction ───────────────────────────────────────────────────────

function onPlayerClick(player) {
  if (selectedPlayerName.value === player.player_name) {
    clearTrajectory(); return
  }
  playbackStop()
  playbackCurrentTs.value = 0
  selectedPlayerName.value = player.player_name
  trajectory.value = []
  loadTrajectory(player.player_name)
  scheduleRender()
}

function clearTrajectory() {
  playbackStop()
  selectedPlayerName.value = null
  trajectory.value = []
  scheduleRender()
}

// ─── Playback Controls ────────────────────────────────────────────────────────

function playbackToggle() {
  if (!trajectory.value.length || playbackEndTs.value <= playbackStartTs.value) return
  if (playbackPlaying.value) {
    playbackStop()
  } else {
    if (playbackCurrentTs.value >= playbackEndTs.value) {
      playbackCurrentTs.value = playbackStartTs.value
    }
    playbackStart()
  }
}

function playbackStart() {
  playbackPlaying.value = true
  playbackLastRealTs = performance.now()
  playbackRafHandle = requestAnimationFrame(playbackTick)
}

function playbackStop() {
  playbackPlaying.value = false
  if (playbackRafHandle) { cancelAnimationFrame(playbackRafHandle); playbackRafHandle = null }
}

function playbackTick(now) {
  if (!playbackPlaying.value) return
  const dt = now - playbackLastRealTs
  playbackLastRealTs = now
  playbackCurrentTs.value += dt * playbackSpeed.value
  if (playbackCurrentTs.value >= playbackEndTs.value) {
    playbackCurrentTs.value = playbackEndTs.value
    playbackStop()
    scheduleRender()
    return
  }
  if (playbackLockCamera.value && playbackPosition.value) {
    const { mx, mz } = playerToMap(playbackPosition.value.x, playbackPosition.value.z, playbackPosition.value.dim)
    view.cx = mx; view.cz = mz
  }
  scheduleRender()
  playbackRafHandle = requestAnimationFrame(playbackTick)
}

function playbackRewind() {
  playbackStop()
  playbackCurrentTs.value = playbackStartTs.value
  scheduleRender()
}

function playbackForward() {
  playbackStop()
  playbackCurrentTs.value = playbackEndTs.value
  scheduleRender()
}

// ─── View Helpers ─────────────────────────────────────────────────────────────

function fitView() {
  const nodes = parsedNodes.value.filter(n => n.visible && n.isStation)
  if (!nodes.length) { view.cx = 0; view.cz = 0; view.scale = 0.5; return }
  const xs = nodes.map(n => n.x), zs = nodes.map(n => n.z)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minZ = Math.min(...zs), maxZ = Math.max(...zs)
  view.cx = (minX + maxX) / 2
  view.cz = (minZ + maxZ) / 2
  const pad = 0.85
  const sx = view.cssW * pad / Math.max(maxX - minX, 1)
  const sz = view.cssH * pad / Math.max(maxZ - minZ, 1)
  view.scale = Math.max(0.015, Math.min(20, Math.min(sx, sz)))
}

// ─── Event Handlers ───────────────────────────────────────────────────────────

function onServerChange() {
  mapJsonRaw.value = null; players.value = []; trajectory.value = []
  selectedPlayerName.value = null; selectedNodeKey.value = null
  selectedEdgeKey.value = null; editMode.value = false; dirty.value = false
  if (!currentServer.value?.available_dims?.includes(activeDim.value)) activeDim.value = 'nether'
  loadMapData(); loadPlayers(); loadConfig()
  startPlayerRefresh()
}

function onDimChange() {
  selectedNodeKey.value = null; selectedEdgeKey.value = null
  dirty.value = false
  loadMapData()
}

function startPlayerRefresh() {
  if (playerRefreshTimer.value) clearInterval(playerRefreshTimer.value)
  playerRefreshTimer.value = setInterval(loadPlayers, 10000)
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(() => {
  loadServers()
  nextTick(() => {
    setupCanvas()
    resizeObserver = new ResizeObserver(() => { setupCanvas() })
    if (canvasWrap.value) resizeObserver.observe(canvasWrap.value)
  })
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (playerRefreshTimer.value) clearInterval(playerRefreshTimer.value)
  if (rafId) cancelAnimationFrame(rafId)
  if (playbackRafHandle) cancelAnimationFrame(playbackRafHandle)
  window.removeEventListener('keydown', onKeyDown)
})

// re-render on data changes
watch([parsedNodes, parsedEdges, players, trajectory, selectedNodeKey, selectedEdgeKey,
  connectSourceKey, showOfflinePlayers, selectedPlayerName], scheduleRender, { deep: false })
</script>

<style scoped>
.world-map-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--el-header-height) - 24px);
  min-height: 400px;
}

/* Toolbar */
.wm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.wm-toolbar-left,
.wm-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* Content */
.wm-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.wm-content.left  .wm-canvas-wrap  { flex: 1; }
.wm-content.right .wm-bluemap-wrap { flex: 1; }
.wm-content.split .wm-canvas-wrap  { flex: 1; }
.wm-content.split .wm-bluemap-wrap { flex: 1; border-left: 1px solid var(--el-border-color-lighter); }

/* Canvas panel */
.wm-canvas-wrap {
  position: relative;
  background: #f8f9fc;
  overflow: hidden;
  min-width: 0;
}
.wm-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

/* Node editor overlay */
.wm-node-editor {
  pointer-events: auto;
}
.wm-node-editor-inner {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.wm-node-editor-row {
  display: flex;
  gap: 6px;
}
.wm-node-editor-row .el-input {
  flex: 1;
  min-width: 0;
}
.wm-node-editor-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.wm-editor-prefix {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

/* HUD overlays */
.wm-hud {
  position: absolute;
  pointer-events: none;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(4px);
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}
.wm-coords { bottom: 8px; left: 8px; }
.wm-edit-hint { bottom: 8px; right: 8px; pointer-events: none; }
.wm-connect-hint { background: rgba(245,158,11,0.15); border-color: #f59e0b; color: #92400e; }
.wm-traj-info { top: 8px; left: 50%; transform: translateX(-50%); pointer-events: auto;
  display: flex; align-items: center; gap: 4px; }

/* Playback bar */
.wm-playback-bar {
  position: absolute;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(480px, calc(100% - 24px));
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  padding: 8px 10px 6px;
  pointer-events: auto;
  z-index: 10;
}
.wm-playback-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
}
.wm-playback-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.wm-playback-close {
  margin-left: 4px;
  font-size: 15px;
  line-height: 1;
}
.wm-playback-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.wm-playback-nodata {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: 4px 0;
}
.wm-playback-play-btn {
  font-size: 15px !important;
  min-width: 30px !important;
  line-height: 1 !important;
  padding: 4px 6px !important;
  color: var(--el-color-primary) !important;
}
.wm-playback-play-btn.is-pausing {
  color: var(--el-color-warning) !important;
}

/* Loading & empty */
.wm-canvas-loading,
.wm-canvas-empty {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(248,249,252,0.7);
  pointer-events: none;
}
.wm-canvas-loading { font-size: 28px; color: var(--el-color-primary); }

/* BlueMap panel */
.wm-bluemap-wrap {
  position: relative;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}
.wm-bluemap-iframe {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
}
.wm-bluemap-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
