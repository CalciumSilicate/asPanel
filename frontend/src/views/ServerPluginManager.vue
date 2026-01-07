<template>
  <div class="server-plugin-manager-layout" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
  
    <!-- 左侧边栏：参考 PrimeBackup 风格 -->
    <div class="table-card left-panel">
      <el-card shadow="never" v-loading="serversLoading">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base font-medium">选择服务器</span>
            </div>
            <div class="flex items-center gap-2">
              <el-tag type="success">总插件数：{{ totalPluginCount }}</el-tag>
            </div>
          </div>
        </template>

        <el-input v-model="serverQuery" placeholder="搜索服务器" clearable class="mb-2">
          <template #prefix><el-icon><Search/></el-icon></template>
        </el-input>

        <el-table :data="filteredServers" size="small" stripe height="100%" @row-click="(row: ServerInfo) => selectServer(row.id)">
          <el-table-column label="服务器" min-width="180">
            <template #default="{ row }">
              <div class="flex items-center justify-between w-full">
                <div class="server-cell">
                  <div class="server-name">{{ row.name }}</div>
                  <div class="muted">ID: {{ row.id }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="插件数" width="100" align="center">
            <template #default="{ row }">
              <span>{{ Number(row.plugins_count) || 0 }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Main Content Area -->
    <el-main class="plugin-content-area">
      <div v-if="!selectedServer" class="main-placeholder">
        <el-empty description="请从左侧选择一个服务器以管理插件"/>
      </div>

      <div v-else>
        <!-- Toolbar -->
        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ selectedServer ? selectedServer.name : '请选择服务器' }}</span>
                <el-tag type="info" v-if="selectedServer">共 {{ currentPlugins.length }} 个插件</el-tag>
              </div>
              <div class="flex items-center gap-2">
                <el-button-group>
                  <el-button type="success" :icon="Plus" @click="openAddOnlinePluginDialog" :disabled="!selectedServer">添加联网插件</el-button>
                  <el-button type="primary" :icon="Coin" @click="openAddDbPluginDialog" :disabled="!selectedServer">添加数据库插件</el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          <div class="flex items-center gap-2">
            <el-input v-model="query" placeholder="搜索：名称 / ID / 文件名" clearable style="max-width: 300px;">
              <template #prefix>
                <el-icon>
                  <Search/>
                </el-icon>
              </template>
            </el-input>
            <el-radio-group v-model="filterStatus">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="enabled">已启用</el-radio-button>
              <el-radio-button value="disabled">已禁用</el-radio-button>
            </el-radio-group>
          </div>
        </el-card>

        <!-- Plugin List Table -->
        <div class="table-card">
          <el-table :data="pagedPlugins" v-loading="pluginsLoading" stripe size="small"
                    :row-class-name="pluginRowClassName">
          
          <el-table-column label="插件" min-width="280">
            <template #default="{ row }">
              <div class="plugin-cell-layout">
                <el-tag type="primary" effect="plain" size="small" v-if="row.meta.id">{{ row.meta.id }}</el-tag>
                <div>
                  <div class="plugin-name">{{ row.meta.name || '未知名称' }}</div>
                  <div class="plugin-description">
                    {{ row.meta.description?.zh_cn || row.meta.description?.en_us || row.file_name }}
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="作者" min-width="160">
            <template #default="{ row }">
              <el-space wrap>
                <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
                <span v-if="getAuthorsArray(row.meta).length === 0"><el-tag size="small"
                                                                            type="info">未知</el-tag></span>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column label="版本" width="180">
            <template #default="{ row }">
              <div class="version-cell">
                <el-tag size="small" :type="row.meta.version ? 'success' : 'info'">{{
                    row.meta.version || '未知'
                  }}
                </el-tag>
                <el-tooltip :content="`有新版：${onlinePluginsMap.get(row.meta.id)?.release?.latest_version || ''}`" placement="top-start" effect="light" v-if="isUpdateAvailable(row)">
                  <el-button size="small" type="warning" circle plain :icon="Refresh" :loading="row.loading" @click="handleUpdatePlugin(row)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="文件大小" width="100" align="center">
            <template #default="{ row }">
              <span>{{ (row.size / 1024).toFixed(1) }} KB</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="handlePluginSwitch(row)" :loading="row.loading"/>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" align="center">
            <template #default="{ row }">
              <el-button size="small" type="success" :icon="Download" :loading="row.loading"
                         @click="handlePluginDownload(row)">下载
              </el-button>
              <el-popconfirm title="确定删除这个插件吗？" width="220" @confirm="handlePluginDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger" :icon="Delete" :loading="row.loading">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
          </el-table>
        </div>

        <!-- Pagination -->
        <div class="mt-3 flex items-center justify-end">
          <el-pagination
              background
              layout="prev, pager, next, sizes, total"
              :page-sizes="[10, 20, 50, 100]"
              :page-size="pageSize"
              :current-page="page"
              :total="filteredPlugins.length"
              @current-change="(p: number) => page = p"
              @size-change="(s: number) => { pageSize = s; page = 1; }"
          />
        </div>
      </div>
    </el-main>

    <!-- [MODIFIED] New Online Plugin Explorer Dialog -->
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
        <el-table :data="onlinePaged" v-loading="onlinePluginsLoading" stripe size="small" @row-dblclick="openOnlineDetail">
          <el-table-column label="插件" min-width="260">
            <template #default="{ row }">
              <div class="flex items-start gap-2" style="display: flex; gap: 8px;">
                <el-tag type="primary" effect="plain">{{ row.meta.id }}</el-tag>
                <div>
                  <div class="font-medium leading-5" style="font-weight: 500;">{{ row.meta.name }}</div>
                  <div class="text-xs text-gray-500 leading-4" style="font-size: 12px; color: #909399;">
                    {{ row.meta.description?.zh_cn || row.meta.description?.en_us || '-' }}
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="release.latest_version" label="最新版本" width="130">
            <template #default="{ row }">
              <el-tag size="small" :type="row.latest?.prerelease ? 'warning' : 'success'">
                {{ row.release?.latest_version || '-' }}
              </el-tag>
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
                <el-tag v-for="a in row.meta?.authors || []" :key="a" size="small">{{ a }}</el-tag>
              </el-space>
            </template>
          </el-table-column>

          <el-table-column label="统计" width="160" align="center">
            <template #default="{ row }">
              <el-space>
                <el-tooltip content="Repo Stars">
                  <el-tag type="info" size="small">
                    <el-icon class="mr-1"><Star/></el-icon>
                    {{ row.repository?.stargazers_count ?? 0 }}
                  </el-tag>
                </el-tooltip>
                <el-tooltip content="Latest Asset Downloads">
                  <el-tag type="info" size="small">
                    <el-icon class="mr-1"><Download/></el-icon>
                    {{ row.latest?.asset?.download_count ?? 0 }}
                  </el-tag>
                </el-tooltip>
              </el-space>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="220" align="center">
            <template #default="{ row }">
              <el-button-group>
                <el-button size="small" @click="openOnlineDetail(row)">详情</el-button>
                <el-button size="small" type="primary" :disabled="!row.latest?.asset?.browser_download_url"
                           @click="go(row.latest?.asset?.browser_download_url)">下载
                </el-button>
                <el-button size="small" type="success" :icon="Upload" @click="handleInstallOnlineRow(row)">
                  安装
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
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
import apiClient, { isRequestCanceled } from '@/api';
import { asideCollapsed, asideCollapsing } from '@/store/ui'
import { fetchTasks } from '@/store/tasks'

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

const selectServer = async (serverId: number) => {
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
    const response = await apiClient.get(
        `/api/plugins/download/${selectedServerId.value}/${plugin.file_name}`,
        {responseType: 'blob'}
    );
    const downloadFilename = plugin.type === 'FOLDER' ? `${plugin.file_name}.zip` : plugin.file_name;
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', downloadFilename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
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
onMounted(() => {
  initialLoad();
});
</script>

<style scoped>
/* Main layout */
.server-plugin-manager-layout {
  display: flex;
  align-items: stretch; /* 让右侧主视图占满高度，保证可滚动 */
  gap: 16px; /* 与 PB 左右间距一致 */
  /* 与全局头部高度一致，且扣除 el-main 上下各 24px 的内边距 */
  height: calc(100vh - var(--el-header-height) - 48px);
  /* 限制外溢，滚动交由内部区域处理 */
  overflow: hidden;
  min-height: 0;
  background-color: transparent;
}

/* Sidebar */
.server-sidebar {
  background-color: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  overflow: hidden;
}

.sidebar-inner { display: flex; flex-direction: column; }

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 刷新按钮样式优化：更轻的文本按钮 + 悬浮色 */
.refresh-btn {
  color: var(--el-text-color-secondary);
}
.refresh-btn:hover {
  color: var(--el-color-primary);
}

.server-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.server-list-item {
  padding: 12px 15px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s;
  border-bottom: 1px solid #f0f2f5;
}

.server-list-item:hover {
  background-color: #ecf5ff;
}

.server-list-item.is-active {
  background-color: #d9ecff;
  color: #409EFF;
  font-weight: 500;
}

.server-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 10px;
}

.no-servers-placeholder {
  padding-top: 40px;
}

/* Main Content Area */
.plugin-content-area {
  padding: 0 20px 20px;
  flex: 1 1 auto;
  min-height: 0; /* 允许在父 flex 容器内收缩，避免溢出 */
  overflow: auto; /* 内部滚动 */
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}

/* 左侧面板（与 PB 对齐） */
.left-panel { width: 320px; flex-shrink: 0; align-self: stretch; height: 100%; min-height: 0; }
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.left-panel :deep(.el-card) { height: 100%; display: flex; flex-direction: column; }
.left-panel :deep(.el-card__body) { padding: 8px; flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }
.left-panel :deep(.el-input), .left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.left-panel :deep(.el-table) { flex: 1 1 auto; min-height: 0; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }

/* Element Plus 自定义滚动条保持可见 */
.server-plugin-manager-layout :deep(.el-scrollbar__bar) { opacity: 0.9; }

.main-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

/* Reused Styles & Dialog Styles */
.mb-3 {
  margin-bottom: 12px;
}

.mt-3 {
  margin-top: 12px;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.justify-between {
  justify-content: space-between;
}

.justify-end {
  justify-content: flex-end;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}

.gap-4 {
  gap: 16px;
}

.font-medium {
  font-weight: 500;
}

.text-base {
  font-size: 14px;
}

.plugin-cell-layout {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.plugin-name {
  font-weight: 500;
  line-height: 1.2;
}

.plugin-description {
  font-size: 12px;
  color: #909399;
  line-height: 1.3;
}

.version-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 圆形按钮内图标可见性（当前版本旁刷新按钮） */
.version-cell .el-button.is-circle .el-icon { display: inline-flex; align-items: center; justify-content: center; }
.version-cell .el-button.el-button--primary.is-circle:not(.is-plain) .el-icon { color: #fff; }
.version-cell .el-button.el-button--primary.is-circle.is-plain .el-icon { color: var(--brand-primary); }

.plugin-toolbar {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
  align-items: center;
}

/* 表格圆角统一样式 */
.rounded-table {
  border-radius: 8px;
  overflow: hidden;
}

:deep(.disabled-plugin-row) {
  color: #a8abb2;
  background-color: #fafafa;
}

:deep(.disabled-plugin-row:hover > td) {
  background-color: #f5f5f5 !important;
}
</style>