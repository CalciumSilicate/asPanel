<template>
  <div class="pm-page">

    <!-- Toolbar -->
    <PluginToolbar
      :selected-server="selectedServer"
      :total-count="filteredPlugins.length"
      :total-plugin-count="totalPluginCount"
      :query="query"
      :filter-status="filterStatus"
      :current-page="page"
      :page-size="pageSize"
      :total-filtered="filteredPlugins.length"
      @select-server="selectServer"
      @update:query="query = $event; page = 1"
      @update:filter-status="filterStatus = $event; page = 1"
      @add-online="openAddOnlinePluginDialog"
      @add-db="openAddDbPluginDialog"
      @prev-page="page > 1 && page--"
      @next-page="page < Math.ceil(filteredPlugins.length / pageSize) && page++"
    />

    <!-- No server selected: Picker -->
    <div v-if="!selectedServer" class="pm-placeholder">
      <PluginServerPicker
        :servers="servers"
        :loading="serversLoading"
        :total-plugin-count="totalPluginCount"
        @select="selectServer"
      />
    </div>

    <!-- Server selected: Glass card -->
    <div v-else class="pm-glass-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- Plugin table -->
      <div class="pm-table-wrap" v-loading="pluginsLoading" element-loading-background="transparent">
        <table class="native-table">
          <colgroup>
            <col style="min-width:280px" />
            <col style="min-width:160px" />
            <col style="width:180px" />
            <col style="width:100px" />
            <col style="width:100px" />
            <col style="width:200px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell">插件</th>
              <th class="th-cell">作者</th>
              <th class="th-cell">版本</th>
              <th class="th-cell th-center">文件大小</th>
              <th class="th-cell th-center">状态</th>
              <th class="th-cell th-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!pluginsLoading && pagedPlugins.length === 0">
              <td colspan="6" class="td-empty">
                <el-empty description="暂无插件" :image-size="80" />
              </td>
            </tr>
            <tr v-for="row in pagedPlugins" :key="row.file_name"
                :class="['tbl-row', { 'row-disabled': !row.enabled }]">
              <td class="td-cell">
                <PluginNameCell
                  :id="row.meta.id"
                  :name="row.meta.name"
                  :description="row.meta.description?.zh_cn || row.meta.description?.en_us"
                  :filename="row.file_name"
                />
              </td>
              <td class="td-cell">
                <AuthorTagsCell :authors="getAuthorsArray(row.meta)" />
              </td>
              <td class="td-cell">
                <div class="version-cell">
                  <el-tag size="small" :type="row.meta.version ? 'success' : 'info'">{{ row.meta.version || '未知' }}</el-tag>
                  <el-tooltip v-if="isUpdateAvailable(row)" :content="`有新版：${onlinePluginsMap.get(row.meta.id)?.release?.latest_version || ''}`" placement="top-start" effect="light">
                    <el-button size="small" type="warning" circle plain :icon="Refresh" :loading="row.loading" @click="handleUpdatePlugin(row)" />
                  </el-tooltip>
                </div>
              </td>
              <td class="td-cell td-center">
                <span class="size-cell">{{ (row.size / 1024).toFixed(1) }} KB</span>
              </td>
              <td class="td-cell td-center">
                <el-switch v-model="row.enabled" @change="handlePluginSwitch(row)" :loading="row.loading" />
              </td>
              <td class="td-cell td-right">
                <div class="row-actions">
                  <button class="act-btn act-dl" :disabled="row.loading" @click="handlePluginDownload(row)">
                    <el-icon :size="12"><Download /></el-icon>下载
                  </button>
                  <el-popconfirm title="确定删除这个插件吗？" width="220" @confirm="handlePluginDelete(row)">
                    <template #reference>
                      <button class="act-btn act-danger" :disabled="row.loading">
                        <el-icon :size="12"><Delete /></el-icon>删除
                      </button>
                    </template>
                  </el-popconfirm>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>

    <!-- ───────────────────────── Dialogs ───────────────────────── -->

    <!-- Online Plugin Explorer -->
    <el-dialog v-if="addOnlinePluginDialogVisible" v-model="addOnlinePluginDialogVisible" title="MCDR 插件市场"
               width="85%" top="5vh" destroy-on-close>
      <!-- Toolbar -->
      <el-card shadow="never" class="mb-3">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="text-base font-medium">浏览插件</span>
              <el-tag type="info" v-if="onlineStats.total">共 {{ onlineStats.total }} 个插件</el-tag>
              <el-tag type="success" v-if="onlineStats.updatedAt">更新于：{{ onlineStats.updatedAt }}</el-tag>
            </div>
            <div class="flex items-center gap-2">
              <el-button :loading="onlinePluginsLoading" type="primary" @click="fetchOnlinePlugins(true)">刷新</el-button>
            </div>
          </div>
        </template>

        <div class="grid grid-cols-1 md:grid-cols-12 gap-3" style="display: grid; grid-template-columns: repeat(12, 1fr); gap: 12px;">
          <el-input
              v-model="onlineQuery"
              placeholder="搜索：名称 / ID / 作者 / 标签"
              clearable
              class="md:col-span-4"
              style="grid-column: span 4;"
              @input="onlinePage = 1"
          >
            <template #prefix>
              <el-icon>
                <Search/>
              </el-icon>
            </template>
          </el-input>

          <el-select v-model="onlineSelectedLabels" class="md:col-span-3" style="grid-column: span 3;" multiple collapse-tags collapse-tags-tooltip
                     placeholder="标签筛选">
            <el-option v-for="l in onlineAllLabels" :key="l" :label="l" :value="l"/>
          </el-select>

          <el-select v-model="onlineSortBy" class="md:col-span-2" style="grid-column: span 2;" placeholder="排序">
            <el-option label="最新发布" value="latestDate"/>
            <el-option label="下载最多" value="downloads"/>
            <el-option label="Star 最多" value="stars"/>
            <el-option label="名称" value="name"/>
          </el-select>

          <div class="md:col-span-3 flex items-center gap-3" style="grid-column: span 3;">
            <el-checkbox v-model="onlineShowPrerelease">包含预发布</el-checkbox>
            <el-checkbox v-model="onlineHideArchived">隐藏已归档</el-checkbox>
          </div>
        </div>
      </el-card>

      <!-- Table -->
      <div class="table-card">
        <div v-loading="onlinePluginsLoading" element-loading-background="transparent">
          <table class="native-table">
            <colgroup>
              <col style="min-width:260px" />
              <col style="width:130px" />
              <col style="width:130px" />
              <col style="min-width:160px" />
              <col style="width:160px" />
              <col style="width:210px" />
            </colgroup>
            <thead>
              <tr class="thead-row">
                <th class="th-cell">插件</th>
                <th class="th-cell">最新版本</th>
                <th class="th-cell">当前版本</th>
                <th class="th-cell">作者</th>
                <th class="th-cell th-center">统计</th>
                <th class="th-cell th-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!onlinePluginsLoading && onlinePaged.length === 0">
                <td colspan="6" class="td-empty">
                  <el-empty description="暂无插件" :image-size="80" />
                </td>
              </tr>
              <tr v-for="row in onlinePaged" :key="row.meta.id" class="tbl-row" @dblclick="openOnlineDetail(row)">
                <td class="td-cell">
                  <PluginNameCell
                    :id="row.meta.id"
                    :name="row.meta.name"
                    :description="row.meta.description?.zh_cn || row.meta.description?.en_us"
                  />
                </td>
                <td class="td-cell">
                  <el-tag size="small" :type="row.latest?.prerelease ? 'warning' : 'success'">
                    {{ row.release?.latest_version || '-' }}
                  </el-tag>
                </td>
                <td class="td-cell">
                  <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
                    {{ getPluginInstallStatus(row.meta.id) }}
                  </el-tag>
                  <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
                </td>
                <td class="td-cell">
                  <AuthorTagsCell :authors="row.meta?.authors" />
                </td>
                <td class="td-cell td-center">
                  <div class="stats-cell">
                    <el-tooltip content="Repo Stars">
                      <span class="stat-chip stat-star">
                        <el-icon :size="11"><Star/></el-icon>
                        {{ row.repository?.stargazers_count ?? 0 }}
                      </span>
                    </el-tooltip>
                    <el-tooltip content="下载量">
                      <span class="stat-chip stat-dl-chip">
                        <el-icon :size="11"><Download/></el-icon>
                        {{ row.latest?.asset?.download_count ?? 0 }}
                      </span>
                    </el-tooltip>
                  </div>
                </td>
                <td class="td-cell td-right">
                  <div class="row-actions">
                    <button class="act-btn act-detail" @click="openOnlineDetail(row)">详情</button>
                    <button class="act-btn act-dl" :disabled="!row.latest?.asset?.browser_download_url" @click="go(row.latest?.asset?.browser_download_url)">下载</button>
                    <button class="act-btn act-install" @click="handleInstallOnlineRow(row)">
                      <el-icon :size="12"><Upload /></el-icon>安装
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pagination -->
      <div class="mt-3 flex items-center justify-end">
        <el-pagination
            background
            layout="prev, pager, next, sizes, total"
            :page-sizes="[10, 20, 50, 100]"
            :page-size="onlinePageSize"
            :current-page="onlinePage"
            :total="onlineFiltered.length"
            @current-change="(p: number)=>onlinePage=p"
            @size-change="(s: number)=>{onlinePageSize=s; onlinePage=1}"
        />
      </div>
    </el-dialog>

    <!-- Plugin Detail Drawer (Nested or global) -->
    <el-drawer v-model="detailVisible" size="40%" direction="rtl" :destroy-on-close="true" append-to-body>
      <template #header>
        <div class="flex items-center gap-2">
          <div class="text-base font-medium">{{ detail?.meta?.name }}<span class="text-gray-500">（{{ detail?.meta?.id }}）</span></div>
          <el-tag size="small" :type="detail?.latest?.prerelease ? 'warning' : 'success'">
            {{ detail?.release?.latest_version }}
          </el-tag>
          <el-tag v-if="detail?.repository?.archived" size="small" type="danger">Archived</el-tag>
        </div>
      </template>

      <div class="table-card">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="Repo">
            <el-link v-if="detail?.repository?.html_url" :href="detail?.repository?.html_url" target="_blank"
                     type="primary">{{ detail?.repository?.full_name }}
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="Labels">
            <el-space wrap>
              <el-tag v-for="t in detail?.plugin?.labels || []" :key="t" size="small" effect="plain">{{ t }}</el-tag>
            </el-space>
          </el-descriptions-item>
          <el-descriptions-item label="Authors" :span="2">
            <el-space wrap>
              <el-tag v-for="a in detail?.meta?.authors || []" :key="a" size="small">{{ a }}</el-tag>
            </el-space>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <el-divider>简介</el-divider>
      <div class="text-sm leading-6 text-gray-700 whitespace-pre-wrap">
        {{
          detail?.plugin?.introduction?.zh_cn || detail?.plugin?.introduction?.en_us || detail?.meta?.description?.zh_cn || detail?.meta?.description?.en_us || '无'
        }}
      </div>

      <template v-if="hasDependenciesInDetail">
        <el-divider>依赖信息 (最新版本)</el-divider>
        <div class="table-card" style="margin-bottom: 20px;">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="插件依赖" v-if="detail?.latest?.meta?.dependencies">
              <el-space wrap v-if="Object.keys(detail?.latest?.meta?.dependencies || {}).length > 0">
                <el-tag v-for="(version, name) in (detail?.latest?.meta?.dependencies || {})" :key="name" size="small"
                        type="primary" effect="dark">
                  {{ name }}: {{ version }}
                </el-tag>
              </el-space>
              <span v-else>无</span>
            </el-descriptions-item>
            <el-descriptions-item label="Python库依赖" v-if="detail?.latest?.meta?.requirements">
              <el-space wrap v-if="(detail?.latest?.meta?.requirements || []).length > 0">
                <el-tag v-for="req in (detail?.latest?.meta?.requirements || [])" :key="req" size="small" type="success"
                        effect="plain">
                  {{ req }}
                </el-tag>
              </el-space>
              <span v-else>无</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </template>

      <el-divider>发布历史（最多 10 条）</el-divider>
      <el-timeline>
        <el-timeline-item v-for="(r, idx) in (detail?.release?.releases || []).slice(0, 10)" :key="idx"
                          :timestamp="formatDate(r.created_at)" :type="r.prerelease ? 'warning' : 'primary'">
          <div class="flex items-center justify-between gap-2">
            <div>
              <div class="font-medium">{{ r.name || r.tag_name }}</div>
              <div class="text-xs text-gray-500">{{ r.description || '——' }}</div>
            </div>
            <div class="flex items-center gap-2">
              <el-button-group>
                <el-button v-if="r.asset?.browser_download_url" size="small" type="primary"
                           @click="go(r.asset.browser_download_url)">下载
                </el-button>
                <el-button size="small" type="success" :icon="Upload" @click="detail && handleInstallOnlineRow(detail, r)">
                  安装
                </el-button>
              </el-button-group>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>

    <!-- Install Confirm Dialog -->
    <el-dialog v-if="installConfirmDialogVisible" v-model="installConfirmDialogVisible" title="安装确认" width="70%"
               top="8vh" append-to-body>
      <el-table :data="pluginsToInstall" stripe border max-height="60vh">
        <el-table-column label="插件" width="360">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag type="primary" effect="plain" size="small">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name }}</div>
                <div class="plugin-description">
                  {{ (row.meta.description?.zh_cn || row.meta.description?.en_us || '-').substring(0, 50) }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="120">
          <template #default="{ row }">
            <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
              {{ getPluginInstallStatus(row.meta.id) }}
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="安装版本" width="130">
          <template #default="{ row }">
            <el-select v-if="row.availableVersions && row.availableVersions.length > 0" v-model="row.selectedVersion"
                       placeholder="选择版本" size="small" style="width: 100px;">
              <el-option v-for="version in row.availableVersions" :key="version" :label="version" :value="version"/>
            </el-select>
            <span v-else>无可用版本</span>
          </template>
        </el-table-column>
        <el-table-column label="依赖" min-width="250">
          <template #default="{ row }">
            <el-space wrap>
              <el-tooltip v-for="(version, dep) in row.meta.dependencies" :key="dep"
                          :content="`插件依赖: ${dep} (版本: ${version})`">
                <el-tag size="small" type="info">{{ dep }}</el-tag>
              </el-tooltip>
              <el-tooltip v-for="req in row.meta.requirements" :key="req" :content="`Python库: ${req}`">
                <el-tag size="small" type="warning">{{ req }}</el-tag>
              </el-tooltip>
              <span v-if="!row.meta.dependencies && !row.meta.requirements">无</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="installConfirmDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="executeInstallation" :loading="isInstallingPlugins">确认安装</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-if="addDbPluginDialogVisible" v-model="addDbPluginDialogVisible" title="从数据库添加插件" width="60%"
               top="8vh" destroy-on-close>
      <div class="plugin-toolbar">
        <el-input v-model="dbPluginsQuery" placeholder="搜索：名称 / 文件名" clearable style="width: 300px;"></el-input>
      </div>
      <el-table :data="filteredDbPlugins" v-loading="dbPluginsLoading" @selection-change="handleDbSelectionChange"
                stripe border height="50vh" row-key="id">
        <el-table-column type="selection" width="55" reserve-selection/>
        <el-table-column label="插件" min-width="260">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag v-if="row.meta.id" type="primary" effect="plain" size="small">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name || row.file_name }}</div>
                <div class="plugin-description">
                  {{ (row.meta.description?.zh_cn || row.meta.description?.en_us || '').substring(0, 50) }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="插件版本" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.meta.version" type="success" size="small">{{ row.meta.version || "未知" }}</el-tag>
            <el-tag v-else type="info" size="small">未知</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="130">
          <template #default="{ row }">
            <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
              {{ getPluginInstallStatus(row.meta.id) }}
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="160">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
              <span v-if="getAuthorsArray(row.meta).length === 0">未知</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addDbPluginDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleInstallDbPlugins" :loading="isInstallingPlugins"
                     :disabled="dbPluginsSelected.length === 0">
            安装已选 ({{ dbPluginsSelected.length }})
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {ref, onMounted, computed, watch} from 'vue';
import {ElMessage, ElNotification} from 'element-plus';
import {Search, Refresh, Plus, Coin, Delete, Download, Star, Upload} from '@element-plus/icons-vue';
import PluginNameCell from '@/components/PluginNameCell.vue';
import AuthorTagsCell from '@/components/AuthorTagsCell.vue';
import apiClient, { isRequestCanceled } from '@/api';
import PluginToolbar from './server-plugin-manager/PluginToolbar.vue';
import PluginServerPicker from './server-plugin-manager/PluginServerPicker.vue';
import { useUiStore } from '@/store/ui'
import { useTasksStore } from '@/store/tasks'
import { useTransfersStore } from '@/store/transfers'
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'
const { asideCollapsed, asideCollapsing } = storeToRefs(useUiStore())
const { fetchTasks } = useTasksStore()
const { startDownload } = useTransfersStore()
const { activeGroupIds } = storeToRefs(useUserStore())

// --- Interfaces ---
interface Asset {
  id?: number;
  name?: string;
  size?: number;
  download_count?: number;
  created_at?: string;
  browser_download_url?: string
}

interface Meta {
  schema_version?: number;
  id: string;
  name: string;
  version?: string;
  link?: string | null;
  authors?: string[];
  dependencies?: Record<string, string>;
  requirements?: string[];
  description?: Record<string, string>
}

interface ReleaseItem {
  url?: string;
  name?: string;
  tag_name?: string;
  created_at?: string;
  description?: string | null;
  prerelease?: boolean;
  asset?: Asset;
  meta?: Meta
}

interface ReleaseBlock {
  schema_version?: number;
  id?: string;
  latest_version?: string;
  latest_version_index?: number;
  releases?: ReleaseItem[]
}

interface PluginBlock {
  schema_version?: number;
  id?: string;
  authors?: string[];
  repository?: string;
  branch?: string;
  related_path?: string;
  labels?: string[];
  introduction?: Record<string, string>;
  introduction_urls?: Record<string, string>
}

interface Repository {
  url?: string;
  name?: string;
  full_name?: string;
  html_url?: string;
  description?: string | null;
  archived?: boolean;
  stargazers_count?: number;
  watchers_count?: number;
  forks_count?: number;
  readme?: string | null;
  readme_url?: string | null;
  license?: any
}

interface PluginEntry {
  meta: Meta;
  plugin?: PluginBlock;
  release?: ReleaseBlock;
  repository?: Repository;
  latest?: ReleaseItem | null
  searchText?: string
}

interface ServerInfo {
  id: number;
  name: string;
  plugins_count?: number;
  [key: string]: any;
}

interface InstallResult {
  name: string;
  status: 'fulfilled' | 'rejected';
  reason?: string;
}

// --- Page State ---
const servers = ref<ServerInfo[]>([]);
const serversLoading = ref(false);
const selectedServerId = ref<number | null>(null);
const serverPluginsMap = new Map();
const currentPlugins = ref<any[]>([]);
const pluginsLoading = ref(false);

// Left panel search & aggregates
const serverQuery = ref('');
const filteredServers = computed(() => {
  const q = serverQuery.value.trim().toLowerCase();
  if (!q) return servers.value;
  return servers.value.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q));
});
const totalPluginCount = computed(() => servers.value.reduce((sum, s) => sum + (Number(s.plugins_count) || 0), 0));

// --- Filtering & Pagination State ---
const query = ref('');
const filterStatus = ref('all');
const page = ref(1);
const pageSize = ref(20);

// --- Dialogs & Installation State ---
const addOnlinePluginDialogVisible = ref(false);
const addDbPluginDialogVisible = ref(false);
const installConfirmDialogVisible = ref(false);
const isInstallingPlugins = ref(false);

// Online Explorer State
const onlinePlugins = ref<PluginEntry[]>([]);
const onlinePluginsLoading = ref(false);
const onlineStats = ref({total: 0, updatedAt: ''});
const onlineQuery = ref('');
const onlineSelectedLabels = ref<string[]>([]);
const onlineSortBy = ref<'latestDate' | 'downloads' | 'stars' | 'name'>('downloads');
const onlineShowPrerelease = ref(false);
const onlineHideArchived = ref(true);
const onlinePage = ref(1);
const onlinePageSize = ref(10);
const detailVisible = ref(false);
const detail = ref<PluginEntry | null>(null);

const pluginsToInstall = ref<any[]>([]);

const dbPlugins = ref<any[]>([]);
const dbPluginsLoading = ref(false);
const dbPluginsQuery = ref('');
const dbPluginsSelected = ref<any[]>([]);

watch([onlineSelectedLabels, onlineSortBy, onlineShowPrerelease, onlineHideArchived], () => {
  onlinePage.value = 1
});

// --- Computed Properties ---
const selectedServer = computed(() => {
  return servers.value.find(s => s.id === selectedServerId.value) || null;
});

const filteredPlugins = computed(() => {
  return currentPlugins.value.filter(p => {
    const q = query.value.toLowerCase();
    const matchesQuery = !q || p.file_name.toLowerCase().includes(q) || (p.meta.name && p.meta.name.toLowerCase().includes(q)) || (p.meta.id && p.meta.id.toLowerCase().includes(q));
    const matchesFilter = filterStatus.value === 'all' || (filterStatus.value === 'enabled' && p.enabled) || (filterStatus.value === 'disabled' && !p.enabled);
    return matchesQuery && matchesFilter;
  });
});

const pagedPlugins = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredPlugins.value.slice(start, start + pageSize.value);
});

// Online Explorer Computed
const onlineAllLabels = computed(() => {
  const s = new Set<string>()
  onlinePlugins.value.forEach(i => (i.plugin?.labels || []).forEach(l => s.add(l)))
  return Array.from(s).sort()
})

const onlineBaseList = computed(() => {
  let result = onlinePlugins.value
  if (!onlineShowPrerelease.value) {
    result = result.filter(i => !(i.latest?.prerelease))
  }
  if (onlineHideArchived.value) {
    result = result.filter(i => !i.repository?.archived)
  }
  return result
})

const onlineSortedBase = computed(() => {
  const result = [...onlineBaseList.value]
  result.sort((a, b) => {
    if (onlineSortBy.value === 'name') return (a.meta.name || a.meta.id).localeCompare(b.meta.name || b.meta.id)
    if (onlineSortBy.value === 'stars') return (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0)
    if (onlineSortBy.value === 'downloads') return (b.latest?.asset?.download_count ?? 0) - (a.latest?.asset?.download_count ?? 0)
    const da = a.latest?.created_at ? new Date(a.latest.created_at).getTime() : 0
    const db = b.latest?.created_at ? new Date(b.latest.created_at).getTime() : 0
    return db - da
  })
  return result
})

const onlineFiltered = computed(() => {
  let result = onlineSortedBase.value
  const q = onlineQuery.value.trim().toLowerCase()
  if (q) {
    result = result.filter(i => (i.searchText || '').includes(q))
  }
  if (onlineSelectedLabels.value.length) {
    result = result.filter(i => onlineSelectedLabels.value.every(l => (i.plugin?.labels || []).includes(l)))
  }
  return result
})

const onlinePaged = computed(() => {
  const start = (onlinePage.value - 1) * onlinePageSize.value
  return onlineFiltered.value.slice(start, start + onlinePageSize.value)
})

const onlinePluginsMap = computed(() => {
  const entries = onlinePlugins.value
    .map(p => [p?.meta?.id || '', p] as [string, PluginEntry])
    .filter(([k]) => !!k);
  return new Map<string, PluginEntry>(entries);
});

const filteredDbPlugins = computed(() => {
  if (!dbPluginsQuery.value) return dbPlugins.value;
  const q = dbPluginsQuery.value.toLowerCase();
  return dbPlugins.value.filter(p => p.file_name.toLowerCase().includes(q) || (p.meta.name && p.meta.name.toLowerCase().includes(q)));
});

const hasDependenciesInDetail = computed(() => {
  const meta = detail.value?.latest?.meta
  return !!(meta?.dependencies || meta?.requirements)
})

// --- Helper Functions ---
function joinRecordValues(record?: Record<string, string> | null): string {
  if (!record) return ''
  return Object.values(record).filter(Boolean).join(' ')
}

function buildSearchText(entry: PluginEntry): string {
  const parts = [
    entry.meta?.id,
    entry.meta?.name,
    (entry.meta?.authors || []).join(' '),
    (entry.plugin?.labels || []).join(' '),
    joinRecordValues(entry.meta?.description),
    joinRecordValues(entry.plugin?.introduction),
    entry.repository?.full_name,
  ]
  return parts.filter(Boolean).join(' ').toLowerCase()
}

function normalize(data: any): PluginEntry[] {
  const map = data?.plugins || {}
  return Object.keys(map).map((k: string) => {
    const p = map[k]
    const latest = p?.release?.releases?.[0] ?? null
    const entry: PluginEntry = {meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest}
    entry.searchText = buildSearchText(entry)
    return entry
  })
}

function formatDate(d?: string) {
  if (!d) return '-'
  return new Date(d).toLocaleString()
}

function go(url?: string) {
  if (url) window.open(url, '_blank')
}

// --- Main Methods ---
const initialLoad = async (forceOnlineRefresh = false) => {
  serversLoading.value = true;
  try {
    const [{ data: serverData }] = await Promise.all([
      apiClient.get('/api/servers'),
      fetchOnlinePlugins(forceOnlineRefresh)
    ]);

    servers.value = serverData || [];
    prefetchAllServerPlugins(servers.value);

    if (selectedServerId.value) {
      await fetchCurrentServerPlugins();
    }
  } catch (error: any) {
    if (!isRequestCanceled(error)) ElMessage.error('加载服务器列表失败: ' + (error.response?.data?.detail || error.message));
  } finally {
    serversLoading.value = false;
  }
};

const selectServer = async (serverId: number | null) => {
  if (serverId === null) {
    selectedServerId.value = null;
    currentPlugins.value = [];
    return;
  }
  if (selectedServerId.value === serverId && currentPlugins.value.length > 0) return;
  selectedServerId.value = serverId;
  page.value = 1;
  query.value = '';
  filterStatus.value = 'all';
  await fetchCurrentServerPlugins();
};

const fetchCurrentServerPlugins = async () => {
  if (!selectedServerId.value) return;
  const cached = serverPluginsMap.get(selectedServerId.value);
  if (cached) {
    currentPlugins.value = cached;
    return;
  }

  pluginsLoading.value = true;
  try {
    const { data } = await apiClient.get(`/api/plugins/server/${selectedServerId.value}`);
    const plugins = (data.data || []).map((p: any) => ({ ...p, loading: false }));
    serverPluginsMap.set(selectedServerId.value, plugins);
    currentPlugins.value = plugins;
  } catch (error: any) {
    if (!isRequestCanceled(error)) ElMessage.error(`加载插件列表失败: ${error.response?.data?.detail || error.message}`);
    currentPlugins.value = [];
  } finally {
    pluginsLoading.value = false;
  }
};

const prefetchAllServerPlugins = async (serverList: any[] = []) => {
  if (!Array.isArray(serverList) || serverList.length === 0) return;
  const concurrency = 5;
  const queue = [...serverList];
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, () => (async () => {
    while (queue.length > 0) {
      const srv = queue.shift();
      if (!srv) break;
      const id = srv.id;
      if (serverPluginsMap.has(id)) continue;
      try {
        const { data } = await apiClient.get(`/api/plugins/server/${id}`);
        const plugins = (data.data || []).map((p: any) => ({ ...p, loading: false }));
        serverPluginsMap.set(id, plugins);
        if (selectedServerId.value === id && currentPlugins.value.length === 0) {
          currentPlugins.value = plugins;
        }
      } catch {
        serverPluginsMap.set(id, []);
      }
    }
  })());

  await Promise.allSettled(workers);
};

const pluginRowClassName = ({row}: {row: any}) => row.enabled ? '' : 'disabled-plugin-row';

const getAuthorsArray = (meta: any) => {
  if (!meta) return [];
  if (meta.authors && Array.isArray(meta.authors)) return meta.authors.filter(Boolean);
  if (meta.author) {
    if (Array.isArray(meta.author)) return meta.author.filter(Boolean);
    if (typeof meta.author === 'string') return [meta.author];
  }
  return [];
};

const handlePluginSwitch = async (plugin: any) => {
  plugin.loading = true;
  const enable = plugin.enabled;
  try {
    await apiClient.post(`/api/plugins/server/${selectedServerId.value}/switch/${plugin.file_name}?enable=${enable}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已${enable ? '启用' : '禁用'}`);
  } catch (error: any) {
    ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    plugin.enabled = !enable; // Revert on failure
  } finally {
    plugin.loading = false;
  }
};

const handlePluginDownload = async (plugin: any) => {
  if (!selectedServerId.value) return;
  plugin.loading = true;
  try {
    const downloadFilename = plugin.type === 'FOLDER' ? `${plugin.file_name}.zip` : plugin.file_name;
    await startDownload({
      url: `/api/plugins/download/${selectedServerId.value}/${plugin.file_name}`,
      title: plugin.meta?.name || plugin.file_name,
      fallbackFilename: downloadFilename,
    });
  } catch (error: any) {
    ElMessage.error(`下载失败: ${error.response?.data?.detail || error.message}`);
  } finally {
    plugin.loading = false;
  }
};
const handlePluginDelete = async (plugin: any) => {
  plugin.loading = true;
  try {
    await apiClient.delete(`/api/plugins/server/${selectedServerId.value}/${plugin.file_name}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已删除`);
    await initialLoad();
  } catch (error: any) {
    ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    plugin.loading = false;
  }
};

const openAddOnlinePluginDialog = async () => {
  onlineQuery.value = '';
  addOnlinePluginDialogVisible.value = true;
  await fetchOnlinePlugins();
};

const openAddDbPluginDialog = async () => {
  dbPluginsQuery.value = '';
  dbPluginsSelected.value = [];
  addDbPluginDialogVisible.value = true;
  await fetchDbPlugins();
};

const fetchOnlinePlugins = async (force = false) => {
  if (onlinePlugins.value.length > 0 && !force) return;
  onlinePluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/mcdr/versions');
    onlinePlugins.value = normalize(data)
    onlineStats.value.total = onlinePlugins.value.length
    onlineStats.value.updatedAt = new Date().toLocaleString()
  } catch (error: any) {
    if (!isRequestCanceled(error)) ElMessage.error(`加载 MCDR 市场插件失败: ${error.message}`);
  } finally {
    onlinePluginsLoading.value = false;
  }
};

const fetchDbPlugins = async () => {
  dbPluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/db');
    dbPlugins.value = data || [];
  } catch (error: any) {
    if (!isRequestCanceled(error)) ElMessage.error(`加载数据库插件失败: ${error.message}`);
  } finally {
    dbPluginsLoading.value = false;
  }
};

const installedPluginVersionMap = computed(() => {
  const map = new Map();
  (currentPlugins.value || []).forEach(p => {
    const id = p?.meta?.id;
    if (!id) return;
    map.set(id, typeof p.meta?.version === 'string' ? p.meta.version : null);
  });
  return map;
});

const getPluginInstallStatus = (pluginId: string) => {
  if (!pluginId) return null;
  if (!installedPluginVersionMap.value.has(pluginId)) return null;
  return installedPluginVersionMap.value.get(pluginId) || '已安装';
};

const handleDbSelectionChange = (selection: any[]) => dbPluginsSelected.value = selection;

const compareVersions = (v1: string, v2: string) => {
  if (typeof v1 !== 'string' || typeof v2 !== 'string') return 0;
  const parts1 = v1.replace(/^v/, '').split('-')[0].split('.').map(part => parseInt(part, 10) || 0);
  const parts2 = v2.replace(/^v/, '').split('-')[0].split('.').map(part => parseInt(part, 10) || 0);
  const len = Math.max(parts1.length, parts2.length);
  for (let i = 0; i < len; i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
};

const isUpdateAvailable = (installedPlugin: any) => {
  if (!installedPlugin.meta.id) return false;
  const onlinePlugin = onlinePluginsMap.value.get(installedPlugin.meta.id);
  if (!onlinePlugin || !onlinePlugin.latest?.meta?.version || !installedPlugin.meta.version) return false;
  // Use onlinePlugin.latest.meta.version instead of onlinePlugin.release.latest_version if inconsistent
  // But strictly, normalized onlinePlugin has 'release.latest_version'
  return compareVersions(onlinePlugin.release?.latest_version || '', installedPlugin.meta.version) > 0;
};

const handleUpdatePlugin = async (plugin: any) => {
  const onlinePlugin = onlinePluginsMap.value.get(plugin.meta.id);
  if (!onlinePlugin) return ElMessage.error("在市场中找不到该插件，无法更新。");
  plugin.loading = true;
  try {
    const latestVersion = onlinePlugin.release?.latest_version;
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(latestVersion || '')}`;
    await apiClient.post(url);
    ElNotification({
      title: '更新任务已创建',
      message: `插件 "${plugin.meta.name}" 已加入后台更新队列。`,
      type: 'success'
    });
    setTimeout(initialLoad, 3000); 
  } catch (error: any) {
    ElNotification({
      title: '更新请求失败',
      message: `插件 "${plugin.meta.name}": ${error.response?.data?.detail || error.message}`,
      type: 'error',
      duration: 0
    });
  } finally {
    plugin.loading = false;
  }
};

const openOnlineDetail = (row: PluginEntry) => {
  detail.value = row;
  detailVisible.value = true;
}

const handleInstallOnlineRow = (plugin: PluginEntry, release?: ReleaseItem) => {
  // Use the provided release or the latest one
  const targetRelease = release || plugin.latest;
  const availableVersions = plugin.release?.releases?.map(r => r.meta?.version || r.tag_name).filter(Boolean) || [];
  
  // Construct the object expected by executeInstallation
  // We mock a list of 1 item
  const itemToInstall = {
    ...plugin,
    availableVersions,
    selectedVersion: targetRelease?.meta?.version || targetRelease?.tag_name || availableVersions[0] || null
  };
  
  pluginsToInstall.value = [itemToInstall];
  installConfirmDialogVisible.value = true;
}

const executeInstallation = async () => {
  if (pluginsToInstall.value.length === 0) return;
  isInstallingPlugins.value = true;
  const installPromises = pluginsToInstall.value.map(plugin => {
    const version = plugin.selectedVersion;
    if (!version) return Promise.resolve({name: plugin.meta.name, status: 'rejected' as const, reason: '未选择安装版本'});
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(version)}`;
    return apiClient.post(url).then(() => ({
      name: plugin.meta.name,
      status: 'fulfilled' as const
    })).catch(err => ({name: plugin.meta.name, status: 'rejected' as const, reason: err.response?.data?.detail || err.message}));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach((result: InstallResult) => {
    if (result.status === 'fulfilled') {
      successCount++;
      ElNotification({title: '安装任务已创建', message: `插件 "${result.name}" 已加入后台安装队列。`, type: 'success'});
    } else {
      ElNotification({
        title: '安装请求失败',
        message: `插件 "${result.name}": ${result.reason}`,
        type: 'error',
        duration: 0
      });
    }
  });

  isInstallingPlugins.value = false;
  if (successCount > 0) {
    installConfirmDialogVisible.value = false;
    fetchTasks().catch(() => {});
    setTimeout(initialLoad, 1000);
  }
};

const handleInstallDbPlugins = async () => {
  if (dbPluginsSelected.value.length === 0) return;
  isInstallingPlugins.value = true;
  const installPromises = dbPluginsSelected.value.map(plugin => {
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-db/${plugin.id}`;
    return apiClient.post(url).then(() => ({
      name: plugin.meta.name || plugin.file_name,
      status: 'fulfilled' as const
    })).catch(err => ({
      name: plugin.meta.name || plugin.file_name,
      status: 'rejected' as const,
      reason: err.response?.data?.detail || err.message
    }));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach((result: InstallResult) => {
    if (result.status === 'fulfilled') {
      successCount++;
      ElNotification({title: '安装成功', message: `插件 "${result.name}" 已安装。`, type: 'success'});
    } else {
      ElNotification({
        title: '安装失败',
        message: `插件 "${result.name}": ${result.reason}`,
        type: 'error',
        duration: 0
      });
    }
  });

  isInstallingPlugins.value = false;
  if (successCount > 0) {
    addDbPluginDialogVisible.value = false;
    fetchTasks().catch(() => {});
    await initialLoad();
  }
};

// --- Lifecycle ---
// 监听组切换，重新加载服务器和插件列表
watch(activeGroupIds, () => {
  selectedServerId.value = null
  currentPlugins.value = []
  serverPluginsMap.clear()
  initialLoad()
}, { deep: true })

onMounted(() => {
  initialLoad();
});
</script>

<style scoped>
/* ── Page layout ─────────────────────────────────────────── */
.pm-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - var(--el-header-height) - 48px);
  overflow: hidden;
  min-height: 0;
}

/* ── Placeholder (no server selected) ────────────────────── */
.pm-placeholder {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-self: center;
  width: 100%;
  max-width: 520px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 32px rgba(119, 181, 254, 0.10);
}
:global(.dark) .pm-placeholder {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
}

/* ── Glass card (server selected) ────────────────────────── */
.pm-glass-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 32px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.80);
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.pm-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .pm-glass-card {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* shimmer accent line at top of card */
.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, var(--brand-primary) 0%, #a78bfa 50%, var(--brand-primary) 100%);
  background-size: 200% 100%;
  animation: shimmer-slide 3s linear infinite;
  border-radius: 3px 3px 0 0;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.pm-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  padding: 0 4px;
}

/* ── Native table ────────────────────────────────────────── */
.native-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
}
thead { position: sticky; top: 0; z-index: 10; }
.thead-row {
  background: rgba(248, 250, 255, 0.96);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
}
:global(.dark) .thead-row { background: rgba(15, 23, 42, 0.96); }
.th-cell {
  padding: 10px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
  opacity: 0.72;
  white-space: nowrap;
  text-align: left;
}
.th-center { text-align: center; }
.th-right  { text-align: right; padding-right: 16px; }
.tbl-row {
  border-bottom: 1px solid rgba(119, 181, 254, 0.07);
  transition: background 0.12s ease;
}
.tbl-row:last-child { border-bottom: none; }
.tbl-row:hover { background: rgba(119, 181, 254, 0.05); }
.tbl-row.row-disabled { opacity: 0.55; }
.td-cell {
  padding: 12px 12px;
  vertical-align: middle;
}
.td-center { text-align: center; }
.td-right  { text-align: right; padding-right: 16px; }
.td-empty  { text-align: center; padding: 48px 0; }

/* ── Shared cell styles ───────────────────────────────────── */
.version-cell { display: flex; align-items: center; gap: 8px; }
.version-cell .el-button.is-circle .el-icon { display: inline-flex; align-items: center; justify-content: center; }
.size-cell { font-family: 'Maple Mono', ui-monospace, monospace; font-size: 12px; color: var(--el-text-color-secondary); }

/* ── Stat chips ──────────────────────────────────────────── */
.stats-cell { display: inline-flex; align-items: center; gap: 6px; }
.stat-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 600; white-space: nowrap;
}
.stat-star { background: rgba(245,158,11,0.10); color: #f59e0b; border: 1px solid rgba(245,158,11,0.22); }
.stat-dl-chip { background: rgba(119,181,254,0.10); color: var(--brand-primary); border: 1px solid rgba(119,181,254,0.22); }

/* ── Row action buttons ──────────────────────────────────── */
.row-actions { display: inline-flex; align-items: center; gap: 4px; }
.act-btn {
  display: inline-flex; align-items: center; gap: 4px;
  height: 26px; padding: 0 10px; border-radius: 8px;
  border: 1px solid rgba(119,181,254,0.20);
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: 12px; font-weight: 500; font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}
.act-btn:not(:disabled):hover { transform: translateY(-1px); }
.act-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.act-detail:hover { background: rgba(119,181,254,0.10); color: var(--brand-primary); border-color: rgba(119,181,254,0.35); }
.act-dl:not(:disabled):hover { background: rgba(52,211,153,0.10); color: #10b981; border-color: rgba(52,211,153,0.30); }
.act-danger:not(:disabled):hover { background: rgba(239,68,68,0.10); color: #ef4444; border-color: rgba(239,68,68,0.30); }
.act-install { background: linear-gradient(135deg, var(--brand-primary), #a78bfa); color: #fff; border-color: transparent; }
.act-install:hover { box-shadow: 0 4px 12px rgba(119,181,254,0.40); transform: translateY(-1px); }

/* ── Table card (in dialogs/drawers) ────────────────────── */
.table-card { margin-bottom: 16px; border-radius: 8px; overflow: hidden; }

/* ── Dialog / toolbar util ───────────────────────────────── */
.plugin-toolbar { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; }

.mb-3 { margin-bottom: 12px; }
.mt-3 { margin-top: 12px; }
.mr-1 { margin-right: 4px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.font-medium { font-weight: 500; }
.text-base { font-size: 14px; }
.text-sm { font-size: 13px; }
.text-xs { font-size: 12px; }
.text-gray-500 { color: #909399; }
.text-gray-700 { color: #606266; }
.leading-6 { line-height: 24px; }
.whitespace-pre-wrap { white-space: pre-wrap; }


</style>