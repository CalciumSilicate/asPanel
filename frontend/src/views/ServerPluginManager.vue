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
                  <button class="act-btn act-danger" :disabled="row.loading" @click="openDeleteConfirm(row)">
                    <el-icon :size="12"><Delete /></el-icon>删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>

    <!-- ───────────────────────── Dialogs ───────────────────────── -->

    <!-- Online Plugin Explorer -->
    <el-dialog
      v-if="addOnlinePluginDialogVisible"
      v-model="addOnlinePluginDialogVisible"
      width="88%"
      top="4vh"
      destroy-on-close
      append-to-body
      class="pm-online-dialog"
      :show-close="false"
    >
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--market">
            <el-icon :size="18"><Coin /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">MCDR 插件市场</span>
            <span class="dlg-subtitle">
              <template v-if="onlineStats.total">共 {{ onlineStats.total }} 个插件</template>
              <template v-if="onlineStats.updatedAt"> · 更新于 {{ onlineStats.updatedAt }}</template>
            </span>
          </div>
          <!-- Page nav in header -->
          <div v-if="onlineFiltered.length > onlinePageSize" class="dlg-page-nav">
            <div class="toolbar-divider" />
            <div class="page-nav">
              <button class="page-btn" :disabled="onlinePage <= 1" @click="onlinePage--">
                <el-icon :size="12"><ArrowLeft /></el-icon>
              </button>
              <span class="page-indicator">{{ onlinePage }}<span class="page-sep">/</span>{{ Math.ceil(onlineFiltered.length / onlinePageSize) }}</span>
              <button class="page-btn" :disabled="onlinePage >= Math.ceil(onlineFiltered.length / onlinePageSize)" @click="onlinePage++">
                <el-icon :size="12"><ArrowRight /></el-icon>
              </button>
            </div>
            <div class="toolbar-divider" />
          </div>
          <button class="dlg-btn-refresh" :disabled="onlinePluginsLoading" @click="fetchOnlinePlugins(true)">
            <el-icon :size="12" :class="{ 'is-loading': onlinePluginsLoading }"><Refresh /></el-icon>刷新
          </button>
          <button class="dlg-close-btn" @click="addOnlinePluginDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <!-- Filter bar -->
      <div class="pm-filter-bar">
        <el-input
          v-model="onlineQuery"
          placeholder="搜索：名称 / ID / 作者 / 标签"
          clearable
          class="pm-filter-search"
          @input="onlinePage = 1"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select
          v-model="onlineSelectedLabels"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="标签筛选"
          class="pm-filter-labels"
        >
          <el-option v-for="l in onlineAllLabels" :key="l" :label="l" :value="l" />
        </el-select>
        <el-select v-model="onlineSortBy" placeholder="排序" class="pm-filter-sort">
          <el-option label="最新发布" value="latestDate" />
          <el-option label="下载最多" value="downloads" />
          <el-option label="Star 最多" value="stars" />
          <el-option label="名称" value="name" />
        </el-select>
        <div class="pm-filter-checks">
          <el-checkbox v-model="onlineShowPrerelease">包含预发布</el-checkbox>
          <el-checkbox v-model="onlineHideArchived">隐藏已归档</el-checkbox>
        </div>
      </div>

      <!-- Table -->
      <div class="pm-online-table-wrap" v-loading="onlinePluginsLoading" element-loading-background="transparent">
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
                      <el-icon :size="11"><Star /></el-icon>
                      {{ row.repository?.stargazers_count ?? 0 }}
                    </span>
                  </el-tooltip>
                  <el-tooltip content="下载量">
                    <span class="stat-chip stat-dl-chip">
                      <el-icon :size="11"><Download /></el-icon>
                      {{ row.latest?.asset?.download_count ?? 0 }}
                    </span>
                  </el-tooltip>
                </div>
              </td>
              <td class="td-cell td-right">
                <div class="row-actions">
                  <button class="act-btn act-detail" @click="openOnlineDetail(row)">详情</button>
                  <button class="act-btn act-dl" :disabled="!row.latest?.asset?.browser_download_url" @click="go(row.latest?.asset?.browser_download_url)">
                    <el-icon :size="12"><Download /></el-icon>下载
                  </button>
                  <button class="act-btn act-install" @click="handleInstallOnlineRow(row)">
                    <el-icon :size="12"><Upload /></el-icon>安装
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </el-dialog>

    <!-- Plugin Detail Drawer -->
    <el-drawer v-model="detailVisible" size="50%" direction="rtl" :destroy-on-close="true" append-to-body class="pm-detail-drawer">
      <template #header>
        <div class="drw-header">
          <div class="drw-header-shimmer" aria-hidden="true" />
          <div class="drw-header-body">
            <div class="drw-header-icon">
              <el-icon :size="18"><Coin /></el-icon>
            </div>
            <div class="drw-title-group">
              <div class="drw-title">{{ detail?.meta?.name }}</div>
              <div class="drw-subtitle">
                <span class="drw-id">{{ detail?.meta?.id }}</span>
                <el-tag size="small" :type="detail?.latest?.prerelease ? 'warning' : 'success'" effect="light">
                  {{ detail?.release?.latest_version }}
                </el-tag>
                <el-tag v-if="detail?.repository?.archived" size="small" type="danger" effect="light">Archived</el-tag>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div class="drw-body">
        <!-- Meta info card -->
        <div class="drw-card">
          <div class="drw-info-grid">
            <div class="drw-info-row">
              <span class="drw-info-label">Repo</span>
              <span class="drw-info-value">
                <a v-if="detail?.repository?.html_url" :href="detail?.repository?.html_url" target="_blank" class="drw-link">
                  {{ detail?.repository?.full_name }}
                </a>
                <span v-else class="drw-none">—</span>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.repository?.stargazers_count ?? 0) > 0 || (detail?.latest?.asset?.download_count ?? 0) > 0">
              <span class="drw-info-label">统计</span>
              <span class="drw-info-value drw-stats">
                <span class="stat-chip stat-star">
                  <el-icon :size="11"><Star /></el-icon>
                  {{ detail?.repository?.stargazers_count ?? 0 }}
                </span>
                <span class="stat-chip stat-dl-chip">
                  <el-icon :size="11"><Download /></el-icon>
                  {{ detail?.latest?.asset?.download_count ?? 0 }}
                </span>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.plugin?.labels || []).length > 0">
              <span class="drw-info-label">标签</span>
              <span class="drw-info-value drw-tags">
                <el-tag v-for="t in detail?.plugin?.labels || []" :key="t" size="small" effect="plain">{{ t }}</el-tag>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.meta?.authors || []).length > 0">
              <span class="drw-info-label">作者</span>
              <span class="drw-info-value drw-tags">
                <el-tag v-for="a in detail?.meta?.authors || []" :key="a" size="small" type="primary" effect="light">{{ a }}</el-tag>
              </span>
            </div>
          </div>
        </div>

        <!-- Introduction -->
        <div class="drw-section">
          <div class="drw-section-title">
            <span class="drw-section-dot" />简介
          </div>
          <div class="drw-intro">
            {{ detail?.plugin?.introduction?.zh_cn || detail?.plugin?.introduction?.en_us || detail?.meta?.description?.zh_cn || detail?.meta?.description?.en_us || '暂无介绍' }}
          </div>
        </div>

        <!-- Dependencies -->
        <template v-if="hasDependenciesInDetail">
          <div class="drw-section">
            <div class="drw-section-title">
              <span class="drw-section-dot drw-section-dot--purple" />依赖信息
              <span class="drw-section-badge">最新版本</span>
            </div>
            <div class="drw-card drw-card--deps">
              <div class="drw-info-row" v-if="detail?.latest?.meta?.dependencies">
                <span class="drw-info-label">插件依赖</span>
                <span class="drw-info-value drw-tags">
                  <template v-if="Object.keys(detail?.latest?.meta?.dependencies || {}).length > 0">
                    <el-tag v-for="(version, name) in (detail?.latest?.meta?.dependencies || {})" :key="name"
                            size="small" type="primary" effect="dark">{{ name }}: {{ version }}</el-tag>
                  </template>
                  <span v-else class="drw-none">无</span>
                </span>
              </div>
              <div class="drw-info-row" v-if="detail?.latest?.meta?.requirements">
                <span class="drw-info-label">Python 库</span>
                <span class="drw-info-value drw-tags">
                  <template v-if="(detail?.latest?.meta?.requirements || []).length > 0">
                    <el-tag v-for="req in (detail?.latest?.meta?.requirements || [])" :key="req"
                            size="small" type="success" effect="plain">{{ req }}</el-tag>
                  </template>
                  <span v-else class="drw-none">无</span>
                </span>
              </div>
            </div>
          </div>
        </template>

        <!-- Release history -->
        <div class="drw-section">
          <div class="drw-section-title">
            <span class="drw-section-dot drw-section-dot--green" />发布历史
            <span class="drw-section-badge">最多 10 条</span>
          </div>
          <div class="drw-timeline">
            <div v-for="(r, idx) in (detail?.release?.releases || []).slice(0, 10)" :key="idx" class="drw-release-card">
              <div class="drw-release-dot" :class="r.prerelease ? 'drw-release-dot--warn' : 'drw-release-dot--ok'" />
              <div class="drw-release-body">
                <div class="drw-release-head">
                  <div class="drw-release-name">
                    {{ r.name || r.tag_name }}
                    <el-tag v-if="r.prerelease" size="small" type="warning" effect="plain" class="drw-pre-tag">预发布</el-tag>
                  </div>
                  <div class="drw-release-actions">
                    <button v-if="r.asset?.browser_download_url" class="act-btn act-dl" @click="go(r.asset?.browser_download_url)">
                      <el-icon :size="11"><Download /></el-icon>下载
                    </button>
                    <button v-if="r.url" class="act-btn act-detail" @click="go(r.url)">发布页</button>
                    <button class="act-btn act-install" @click="detail && handleInstallOnlineRow(detail, r)">
                      <el-icon :size="11"><Upload /></el-icon>安装
                    </button>
                  </div>
                </div>
                <div class="drw-release-meta">
                  <span class="drw-release-time">{{ formatDate(r.created_at) }}</span>
                  <span v-if="r.description" class="drw-release-desc">{{ r.description }}</span>
                </div>
              </div>
            </div>
            <div v-if="!(detail?.release?.releases || []).length" class="drw-empty">暂无发布记录</div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Install Confirm Dialog -->
    <el-dialog v-if="installConfirmDialogVisible" v-model="installConfirmDialogVisible"
               width="600px" top="8vh" append-to-body destroy-on-close
               class="pm-install-dialog" :show-close="false">
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--install">
            <el-icon :size="18"><Upload /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">安装确认</span>
            <span class="dlg-subtitle">共 {{ pluginsToInstall.length }} 个插件待安装至 {{ selectedServer?.name }}</span>
          </div>
          <button class="dlg-close-btn" @click="installConfirmDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="pm-install-list">
        <div v-for="(row, idx) in pluginsToInstall" :key="row.meta.id || idx" class="pm-install-item">
          <div class="pm-install-item-head">
            <PluginNameCell
              :id="row.meta.id"
              :name="row.meta.name"
              :description="(row.meta.description?.zh_cn || row.meta.description?.en_us || '').substring(0, 60)"
            />
            <div class="pm-install-status">
              <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small" effect="light">
                已装 {{ getPluginInstallStatus(row.meta.id) }}
              </el-tag>
              <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
            </div>
          </div>
          <div class="pm-install-item-meta">
            <div class="pm-install-meta-row">
              <span class="pm-install-meta-label">安装版本</span>
              <el-select v-if="row.availableVersions?.length > 0" v-model="row.selectedVersion"
                         placeholder="选择版本" size="small" class="pm-version-select">
                <el-option v-for="v in row.availableVersions" :key="v" :label="v" :value="v" />
              </el-select>
              <span v-else class="pm-install-none">无可用版本</span>
            </div>
            <div class="pm-install-meta-row" v-if="row.meta.dependencies && Object.keys(row.meta.dependencies).length > 0">
              <span class="pm-install-meta-label">插件依赖</span>
              <div class="pm-install-tags">
                <el-tooltip v-for="(ver, dep) in row.meta.dependencies" :key="dep" :content="`${dep}: ${ver}`">
                  <el-tag size="small" type="primary" effect="dark">{{ dep }}</el-tag>
                </el-tooltip>
              </div>
            </div>
            <div class="pm-install-meta-row" v-if="(row.meta.requirements || []).length > 0">
              <span class="pm-install-meta-label">Python 库</span>
              <div class="pm-install-tags">
                <el-tag v-for="req in row.meta.requirements" :key="req" size="small" type="success" effect="plain">{{ req }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="pm-install-footer">
          <button class="dlg-btn-ghost" @click="installConfirmDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" :disabled="isInstallingPlugins" @click="executeInstallation">
            <el-icon v-if="isInstallingPlugins" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Upload /></el-icon>
            {{ isInstallingPlugins ? '安装中…' : '确认安装' }}
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Add from DB Dialog -->
    <el-dialog v-if="addDbPluginDialogVisible" v-model="addDbPluginDialogVisible"
               width="76%" top="6vh" destroy-on-close append-to-body
               class="pm-db-dialog" :show-close="false">
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--db">
            <el-icon :size="18"><Box /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">从数据库添加插件</span>
            <span class="dlg-subtitle">
              <template v-if="filteredDbPlugins.length">共 {{ filteredDbPlugins.length }} 个</template>
              <template v-if="dbPluginsSelected.length"> · 已选 {{ dbPluginsSelected.length }} 个</template>
            </span>
          </div>
          <el-input v-model="dbPluginsQuery" placeholder="搜索名称 / 文件名" clearable class="dlg-search" style="width:220px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <button class="dlg-close-btn" @click="addDbPluginDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <div class="pm-db-table-wrap" v-loading="dbPluginsLoading" element-loading-background="transparent">
        <table class="native-table">
          <colgroup>
            <col style="width:48px" />
            <col style="min-width:260px" />
            <col style="width:120px" />
            <col style="width:130px" />
            <col style="min-width:160px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell" style="text-align:center">
                <input type="checkbox" class="pm-db-checkbox"
                       :checked="isAllDbSelected"
                       @change="toggleAllDb" />
              </th>
              <th class="th-cell">插件</th>
              <th class="th-cell">版本</th>
              <th class="th-cell">当前状态</th>
              <th class="th-cell">作者</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!dbPluginsLoading && filteredDbPlugins.length === 0">
              <td colspan="5" class="td-empty">
                <el-empty description="暂无插件" :image-size="60" />
              </td>
            </tr>
            <tr v-for="row in filteredDbPlugins" :key="row.id"
                :class="['tbl-row', { 'tbl-row--checked': isDbRowSelected(row) }]"
                @click="toggleDbRow(row)">
              <td class="td-cell" style="text-align:center" @click.stop>
                <input type="checkbox" class="pm-db-checkbox"
                       :checked="isDbRowSelected(row)" @change="toggleDbRow(row)" />
              </td>
              <td class="td-cell">
                <PluginNameCell :id="row.meta.id" :name="row.meta.name || row.file_name"
                                :filename="row.file_name"
                                :description="(row.meta.description?.zh_cn || row.meta.description?.en_us || '').substring(0,55)" />
              </td>
              <td class="td-cell">
                <el-tag v-if="row.meta.version" type="success" size="small">{{ row.meta.version }}</el-tag>
                <el-tag v-else type="info" size="small">未知</el-tag>
              </td>
              <td class="td-cell">
                <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
                  {{ getPluginInstallStatus(row.meta.id) }}
                </el-tag>
                <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
              </td>
              <td class="td-cell">
                <AuthorTagsCell :authors="getAuthorsArray(row.meta)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="addDbPluginDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" :disabled="isInstallingPlugins || dbPluginsSelected.length === 0" @click="handleInstallDbPlugins">
            <el-icon v-if="isInstallingPlugins" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Upload /></el-icon>
            安装已选 ({{ dbPluginsSelected.length }})
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Delete Confirm Dialog -->
    <el-dialog v-if="deleteConfirmVisible" v-model="deleteConfirmVisible"
               width="420px" top="30vh" destroy-on-close append-to-body
               class="pm-delete-dialog" :show-close="false">
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--danger">
            <el-icon :size="17"><Delete /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">确认删除插件</span>
            <span class="dlg-subtitle">此操作将从服务器移除插件文件</span>
          </div>
          <button class="dlg-close-btn" @click="deleteConfirmVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <div class="dlg-delete-body">
        <div class="dlg-delete-plugin-name">{{ pluginToDelete?.meta?.name || pluginToDelete?.file_name }}</div>
        <div class="dlg-delete-hint">文件：<span class="dlg-delete-file">{{ pluginToDelete?.file_name }}</span></div>
      </div>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="deleteConfirmVisible = false">取消</button>
          <button class="dlg-btn-danger" @click="executePluginDelete">
            <el-icon :size="13"><Delete /></el-icon>确认删除
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {ref, onMounted, computed, watch} from 'vue';
import {ElMessage, ElNotification} from 'element-plus';
import {Search, Refresh, Coin, Close, Delete, Download, Star, Upload, ArrowLeft, ArrowRight} from '@element-plus/icons-vue';
import PluginNameCell from '@/components/PluginNameCell.vue';
import AuthorTagsCell from '@/components/AuthorTagsCell.vue';
import apiClient, { isRequestCanceled } from '@/api';
import PluginToolbar from './server-plugin-manager/PluginToolbar.vue';
import PluginServerPicker from './server-plugin-manager/PluginServerPicker.vue';
import { useTasksStore } from '@/store/tasks'
import { useTransfersStore } from '@/store/transfers'
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'
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

// Left panel aggregates
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

// DB table selection helpers (for native table)
function isDbRowSelected(row: any): boolean {
  return dbPluginsSelected.value.some((p: any) => p.id === row.id);
}
function toggleDbRow(row: any) {
  const idx = dbPluginsSelected.value.findIndex((p: any) => p.id === row.id);
  if (idx >= 0) dbPluginsSelected.value.splice(idx, 1);
  else dbPluginsSelected.value.push(row);
}
const isAllDbSelected = computed(() =>
  filteredDbPlugins.value.length > 0 && filteredDbPlugins.value.every((r: any) => isDbRowSelected(r))
);
function toggleAllDb() {
  if (isAllDbSelected.value) dbPluginsSelected.value = [];
  else dbPluginsSelected.value = [...filteredDbPlugins.value];
}

// Delete confirm dialog
const deleteConfirmVisible = ref(false);
const pluginToDelete = ref<any>(null);
function openDeleteConfirm(plugin: any) {
  pluginToDelete.value = plugin;
  deleteConfirmVisible.value = true;
}
async function executePluginDelete() {
  if (!pluginToDelete.value) return;
  deleteConfirmVisible.value = false;
  await handlePluginDelete(pluginToDelete.value);
}

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

/* ── Online plugin dialog: global overrides ──────────────── */
:global(.pm-online-dialog) {
  border-radius: 20px !important;
  overflow: hidden !important;
  border: 1px solid rgba(119, 181, 254, 0.18) !important;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.14), 0 8px 32px rgba(119, 181, 254, 0.12) !important;
}
:global(.dark .pm-online-dialog) {
  background: rgba(11, 17, 32, 0.94) !important;
  border-color: rgba(119, 181, 254, 0.13) !important;
}
:global(.pm-online-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.pm-online-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.pm-online-dialog .el-dialog__footer) { padding: 0 !important; }

/* ── Dialog header ───────────────────────────────────────── */
.dlg-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.10);
}
.dlg-icon {
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.dlg-icon--market { background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%); }
.dlg-title-group { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.dlg-title    { font-size: 15px; font-weight: 700; color: var(--color-text); line-height: 1.2; }
.dlg-subtitle { font-size: 12px; color: var(--el-text-color-secondary); }
.dlg-close-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 8px;
  border: 1px solid rgba(119, 181, 254, 0.18);
  background: transparent; color: var(--el-text-color-secondary);
  cursor: pointer; transition: all 0.15s ease; flex-shrink: 0;
}
.dlg-close-btn:hover { background: rgba(248, 113, 113, 0.10); border-color: rgba(248, 113, 113, 0.28); color: #ef4444; }

/* Refresh button in header */
.dlg-btn-refresh {
  display: inline-flex; align-items: center; gap: 5px;
  height: 30px; padding: 0 12px; border-radius: 9px;
  border: 1px solid rgba(119, 181, 254, 0.22);
  background: transparent; color: var(--el-text-color-regular);
  font-size: 12px; font-weight: 500; font-family: inherit; cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  flex-shrink: 0;
}
.dlg-btn-refresh:not(:disabled):hover { background: rgba(119, 181, 254, 0.08); border-color: rgba(119, 181, 254, 0.40); }
.dlg-btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Filter bar ──────────────────────────────────────────── */
.pm-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.08);
  background: rgba(248, 250, 255, 0.60);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  flex-wrap: wrap;
}
:global(.dark) .pm-filter-bar {
  background: rgba(15, 23, 42, 0.50);
}
.pm-filter-search { flex: 1 1 220px; min-width: 180px; }
.pm-filter-labels { width: 180px; flex-shrink: 0; }
.pm-filter-sort   { width: 120px; flex-shrink: 0; }
.pm-filter-checks {
  display: flex; align-items: center; gap: 14px;
  flex-shrink: 0;
  font-size: 13px;
}

/* ── Online table wrap ───────────────────────────────────── */
.pm-online-table-wrap {
  overflow-x: auto;
  overflow-y: auto;
  max-height: calc(100vh - 4vh - 56px - 57px - 57px - 60px);
  min-height: 200px;
  scrollbar-width: thin;
}

/* ── Compact page navigation (in dialog header) ──────────── */
.dlg-page-nav { display: inline-flex; align-items: center; gap: 8px; }
.toolbar-divider {
  width: 1px; height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
  flex-shrink: 0;
}
.page-nav { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; }
.page-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 8px;
  border: 1px solid rgba(119,181,254,0.22);
  background: rgba(119,181,254,0.06);
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
  flex-shrink: 0;
}
.page-btn:not(:disabled):hover {
  background: rgba(119,181,254,0.14); border-color: rgba(119,181,254,0.45);
  color: var(--brand-primary); transform: scale(1.08);
}
.page-btn:disabled { opacity: 0.32; cursor: not-allowed; }
:global(.dark) .page-btn { border-color: rgba(119,181,254,0.16); background: rgba(119,181,254,0.04); }
.page-indicator {
  font-size: 12px; font-weight: 700; color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums; min-width: 36px; text-align: center; user-select: none;
}
.page-sep { color: var(--el-text-color-placeholder); margin: 0 1px; font-weight: 400; }

/* ── Install Confirm Dialog ──────────────────────────────── */
:global(.pm-install-dialog) {
  border-radius: 20px !important;
  overflow: hidden;
  background: rgba(255,255,255,0.88) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18) !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.18), 0 4px 20px rgba(119,181,254,0.12) !important;
}
:global(.dark .pm-install-dialog) {
  background: rgba(15,23,42,0.88) !important;
  border-color: rgba(119,181,254,0.14) !important;
}
:global(.pm-install-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.pm-install-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.pm-install-dialog .el-dialog__footer) { padding: 0 !important; }

.dlg-icon--install { background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%); }

.dlg-btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 16px; border-radius: 10px;
  border: 1px solid rgba(119,181,254,0.22);
  background: transparent; color: var(--el-text-color-regular);
  font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}
.dlg-btn-ghost:hover { background: rgba(119,181,254,0.07); border-color: rgba(119,181,254,0.40); }

.dlg-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 18px; border-radius: 10px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 600; font-family: inherit; color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119,181,254,0.35);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.dlg-btn-primary:hover:not(:disabled) { box-shadow: 0 6px 22px rgba(119,181,254,0.55); transform: translateY(-1px); }
.dlg-btn-primary:active:not(:disabled) { transform: scale(0.97); }
.dlg-btn-primary:disabled { opacity: 0.42; cursor: not-allowed; box-shadow: none; }

/* Install list body */
.pm-install-list {
  padding: 16px 20px;
  display: flex; flex-direction: column; gap: 10px;
  max-height: 60vh; overflow-y: auto; scrollbar-width: thin;
}
.pm-install-item {
  border: 1px solid rgba(119,181,254,0.14);
  border-radius: 14px;
  background: rgba(255,255,255,0.50);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  overflow: hidden;
  transition: border-color 0.15s ease;
}
.pm-install-item:hover { border-color: rgba(119,181,254,0.28); }
:global(.dark) .pm-install-item {
  background: rgba(15,23,42,0.50);
  border-color: rgba(119,181,254,0.10);
}
.pm-install-item-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(119,181,254,0.08);
}
.pm-install-status { flex-shrink: 0; }
.pm-install-item-meta {
  display: flex; flex-direction: column;
  padding: 0;
}
.pm-install-meta-row {
  display: flex; align-items: center; gap: 12px;
  padding: 9px 16px;
  border-bottom: 1px solid rgba(119,181,254,0.06);
}
.pm-install-meta-row:last-child { border-bottom: none; }
.pm-install-meta-label {
  flex-shrink: 0; width: 68px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.7;
}
.pm-install-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.pm-install-none { font-size: 12px; color: var(--el-text-color-placeholder); }
.pm-version-select { width: 160px; }

/* Install footer */
.pm-install-footer {
  display: flex; justify-content: flex-end; align-items: center; gap: 10px;
  padding: 14px 20px 18px;
  border-top: 1px solid rgba(119,181,254,0.09);
}

/* ── Add-from-DB Dialog ──────────────────────────────────── */
:global(.pm-db-dialog) {
  border-radius: 20px !important; overflow: hidden;
  background: rgba(255,255,255,0.88) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18) !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.18), 0 4px 20px rgba(119,181,254,0.12) !important;
}
:global(.dark .pm-db-dialog) { background: rgba(15,23,42,0.88) !important; border-color: rgba(119,181,254,0.14) !important; }
:global(.pm-db-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.pm-db-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.pm-db-dialog .el-dialog__footer) { padding: 0 !important; }

/* ── Delete Confirm Dialog ───────────────────────────────── */
:global(.pm-delete-dialog) {
  border-radius: 20px !important; overflow: hidden;
  background: rgba(255,255,255,0.92) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(248,113,113,0.20) !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.18), 0 4px 20px rgba(239,68,68,0.12) !important;
}
:global(.dark .pm-delete-dialog) { background: rgba(15,23,42,0.92) !important; border-color: rgba(248,113,113,0.18) !important; }
:global(.pm-delete-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.pm-delete-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.pm-delete-dialog .el-dialog__footer) { padding: 0 !important; }

/* Shared new icon colors */
.dlg-icon--db     { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
.dlg-icon--danger { background: linear-gradient(135deg, #f87171 0%, #ef4444 100%); }

/* Shared footer (for db + delete dialogs) */
.dlg-footer {
  display: flex; justify-content: flex-end; align-items: center; gap: 10px;
  padding: 14px 20px 18px;
  border-top: 1px solid rgba(119,181,254,0.09);
}

/* Danger button */
.dlg-btn-danger {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 18px; border-radius: 10px; border: none; font-family: inherit;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
  box-shadow: 0 4px 14px rgba(239,68,68,0.30);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.dlg-btn-danger:hover { box-shadow: 0 6px 22px rgba(239,68,68,0.50); transform: translateY(-1px); }
.dlg-btn-danger:disabled { opacity: 0.42; cursor: not-allowed; box-shadow: none; }

/* Search in dialog header */
.dlg-search :deep(.el-input__wrapper) {
  border-radius: 18px !important; background: rgba(255,255,255,0.55) !important;
  border: 1px solid rgba(119,181,254,0.20) !important; box-shadow: none !important;
}
:global(.dark) .dlg-search :deep(.el-input__wrapper) {
  background: rgba(15,23,42,0.55) !important; border-color: rgba(119,181,254,0.16) !important;
}

/* DB table */
.pm-db-table-wrap {
  min-height: 0; max-height: 55vh; overflow-y: auto; overflow-x: hidden; scrollbar-width: thin;
}
.pm-db-checkbox {
  width: 15px; height: 15px; cursor: pointer; accent-color: var(--brand-primary);
}
.tbl-row--checked { background: rgba(119,181,254,0.07); }
.tbl-row--checked:hover { background: rgba(119,181,254,0.11); }

/* Delete dialog body */
.dlg-delete-body {
  padding: 20px 24px 16px;
  display: flex; flex-direction: column; gap: 6px;
}
.dlg-delete-plugin-name {
  font-size: 15px; font-weight: 700; color: var(--color-text);
}
.dlg-delete-hint { font-size: 12px; color: var(--el-text-color-secondary); }
.dlg-delete-file {
  font-family: 'Maple Mono', ui-monospace, monospace;
  font-size: 11px; color: var(--el-text-color-regular);
  background: rgba(248,113,113,0.08); border-radius: 4px; padding: 1px 5px;
}

/* ── Detail Drawer ──────────────────────────────────────── */
:global(.pm-detail-drawer) { --el-drawer-padding-primary: 0; }
:global(.pm-detail-drawer .el-drawer__header) { margin-bottom: 0; padding: 0; border-bottom: none; }
:global(.pm-detail-drawer .el-drawer__body) { padding: 0; overflow: hidden; }

.drw-header {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, rgba(119,181,254,0.12) 0%, rgba(167,139,250,0.08) 100%);
  border-bottom: 1px solid rgba(119,181,254,0.14);
}
.drw-header-shimmer {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, rgba(119,181,254,0.7), rgba(167,139,250,0.6), transparent);
  background-size: 200% 100%;
  animation: shimmer-slide 4s linear infinite;
}
@keyframes shimmer-slide { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.drw-header-body { display: flex; align-items: center; gap: 12px; padding: 16px 20px 14px; }
.drw-header-icon {
  flex-shrink: 0; width: 38px; height: 38px; border-radius: 12px;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  display: flex; align-items: center; justify-content: center;
  color: #fff; box-shadow: 0 4px 12px rgba(119,181,254,0.35);
}
.drw-title-group { min-width: 0; flex: 1; }
.drw-title {
  font-size: 15px; font-weight: 700; color: var(--color-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.3;
}
.drw-subtitle { display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
.drw-id {
  font-family: 'Maple Mono', ui-monospace, monospace;
  font-size: 11px; color: var(--el-text-color-secondary);
  background: rgba(119,181,254,0.10); border: 1px solid rgba(119,181,254,0.18);
  border-radius: 6px; padding: 1px 6px;
}
.drw-body {
  height: calc(100% - 72px); overflow-y: auto; overflow-x: hidden;
  scrollbar-width: thin; padding: 20px;
  display: flex; flex-direction: column; gap: 16px;
}
.drw-card {
  background: rgba(255,255,255,0.55); border: 1px solid rgba(119,181,254,0.14);
  border-radius: 14px; overflow: hidden;
  backdrop-filter: saturate(160%) blur(12px); -webkit-backdrop-filter: saturate(160%) blur(12px);
}
:global(.dark) .drw-card { background: rgba(15,23,42,0.55); border-color: rgba(119,181,254,0.10); }
.drw-card--deps { margin-top: 0; }
.drw-info-grid { display: flex; flex-direction: column; }
.drw-info-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 16px; border-bottom: 1px solid rgba(119,181,254,0.07);
}
.drw-info-row:last-child { border-bottom: none; }
.drw-info-label {
  flex-shrink: 0; width: 68px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.7; padding-top: 2px;
}
.drw-info-value { flex: 1; min-width: 0; font-size: 13px; color: var(--color-text); }
.drw-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.drw-stats { display: flex; align-items: center; gap: 6px; }
.drw-link { color: var(--brand-primary); text-decoration: none; font-size: 13px; transition: opacity 0.15s; }
.drw-link:hover { opacity: 0.75; text-decoration: underline; }
.drw-none { color: var(--el-text-color-placeholder); font-size: 13px; }
.drw-section { display: flex; flex-direction: column; gap: 10px; }
.drw-section-title {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.8;
}
.drw-section-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand-primary); box-shadow: 0 0 6px rgba(119,181,254,0.6);
}
.drw-section-dot--purple { background: #a78bfa; box-shadow: 0 0 6px rgba(167,139,250,0.6); }
.drw-section-dot--green  { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.5); }
.drw-section-badge {
  font-size: 10px; font-weight: 500; letter-spacing: 0; text-transform: none;
  color: var(--el-text-color-placeholder);
  background: rgba(119,181,254,0.08); border: 1px solid rgba(119,181,254,0.14);
  border-radius: 99px; padding: 1px 7px;
}
.drw-intro {
  font-size: 13px; line-height: 1.7; color: var(--el-text-color-regular); white-space: pre-wrap;
  background: rgba(255,255,255,0.45); border: 1px solid rgba(119,181,254,0.10);
  border-radius: 12px; padding: 14px 16px;
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
}
:global(.dark) .drw-intro { background: rgba(15,23,42,0.45); border-color: rgba(119,181,254,0.08); }
.drw-timeline { display: flex; flex-direction: column; gap: 0; }
.drw-release-card {
  display: flex; gap: 14px; padding: 12px 0;
  border-bottom: 1px solid rgba(119,181,254,0.07); position: relative;
}
.drw-release-card:last-child { border-bottom: none; }
.drw-release-dot {
  flex-shrink: 0; width: 10px; height: 10px; border-radius: 50%;
  margin-top: 5px; position: relative; z-index: 1;
}
.drw-release-dot--ok   { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.55); }
.drw-release-dot--warn { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.55); }
.drw-release-body { flex: 1; min-width: 0; }
.drw-release-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;
}
.drw-release-name {
  font-size: 13px; font-weight: 600; color: var(--color-text);
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.drw-pre-tag { vertical-align: middle; }
.drw-release-actions { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; }
.drw-release-meta { display: flex; align-items: baseline; gap: 10px; margin-top: 4px; flex-wrap: wrap; }
.drw-release-time { font-size: 11px; color: var(--el-text-color-placeholder); font-variant-numeric: tabular-nums; }
.drw-release-desc {
  font-size: 12px; color: var(--el-text-color-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px;
}
.drw-empty { text-align: center; padding: 32px 0; color: var(--el-text-color-placeholder); font-size: 13px; }

</style>