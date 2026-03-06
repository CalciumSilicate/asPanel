<template>
  <div class="sl-page" v-loading="isBatchProcessing" element-loading-text="正在处理批量操作...">

    <!-- Toolbar -->
    <ServerListToolbar
      v-model="viewMode"
      :search-query="searchQuery"
      :status-filter="statusFilter"
      :selected-count="selectedServers.length"
      :servers="serverList"
      :has-admin="hasRole('ADMIN')"
      :is-platform-admin="isPlatformAdmin"
      :current-page="currentPage"
      :page-size="pageSize"
      :total-filtered="sortedFilteredList.length"
      @update:search-query="searchQuery = $event"
      @update:status-filter="statusFilter = $event"
      @create="openCreateDialog"
      @import="openImportDialog"
      @batch-action="handleBatchAction"
      @prev-page="currentPage > 1 && currentPage--"
      @next-page="currentPage < Math.ceil(sortedFilteredList.length / pageSize) && currentPage++"
    />

    <!-- Glass card: main content -->
    <div class="sl-glass-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- Grid: skeleton & views share same cell, no height jump -->
      <div class="sl-view-grid">

        <!-- Skeleton while loading -->
        <Transition name="pg-skeleton">
          <div v-if="!loaded" class="sk-servers" aria-hidden="true">
            <div v-for="i in 8" :key="i" class="sk-server-card shimmer"></div>
          </div>
        </Transition>

        <!-- Real views once loaded -->
        <Transition name="pg-content">
          <div v-if="loaded" class="sl-views-wrap">
            <!-- Card view -->
            <ServerCardView
              v-if="viewMode === 'card'"
              :servers="pagedServerList"
              :loading="loading"
              :has-admin="hasRole('ADMIN')"
              :has-helper="hasRole('HELPER')"
              :copy-path="copyPath"
              @start="startServer"
              @stop="stopServer"
              @restart="restartServer"
              @config="openConfigDialog"
              @console="goToConsole"
              @archive="handleCreateArchive"
              @copy="openCopyDialog"
              @rename="openRenameDialog"
              @force-kill="forceKillServer"
              @delete="handleDeleteServer"
            />
            <!-- Table view -->
            <ServerTableView
              v-else
              ref="tableViewRef"
              :servers="pagedServerList"
              :loading="loading"
              :auto-start-saving="autoStartSaving"
              :has-admin="hasRole('ADMIN')"
              :has-helper="hasRole('HELPER')"
              :has-user="hasRole('USER')"
              @selection-change="handleSelectionChange"
              @start="startServer"
              @stop="stopServer"
              @restart="restartServer"
              @config="openConfigDialog"
              @console="goToConsole"
              @archive="handleCreateArchive"
              @copy="openCopyDialog"
              @rename="openRenameDialog"
              @force-kill="forceKillServer"
              @delete="handleDeleteServer"
              @auto-start="setAutoStart"
              @copy-path="copyPath"
            />
          </div>
        </Transition>

      </div>
    </div>

    <!-- ───────────────────────── Dialogs ───────────────────────── -->

    <!-- Create server -->
    <el-dialog v-model="createDialogVisible" width="460px" align-center class="srv-action-dialog" :show-close="false" destroy-on-close>
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--create">
            <el-icon :size="18"><Monitor /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">新建服务器</span>
            <span class="dlg-subtitle">创建新的 MCDR 服务器实例</span>
          </div>
          <button class="dlg-close-btn" @click="createDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="formRef" :model="newServerForm" :rules="formRules" label-position="top">
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="newServerForm.name" placeholder="例如: Survival" />
        </el-form-item>
        <el-form-item label="服务器组" prop="serverLinkGroupIds" required>
          <el-select v-model="newServerForm.serverLinkGroupIds" multiple filterable placeholder="请选择服务器组" style="width:100%" :loading="serverLinkGroupsLoading">
            <el-option v-for="g in selectableGroups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <div class="dlg-field-hint" v-if="selectableGroups.length === 0 && !serverLinkGroupsLoading">
            暂无可用的服务器组<template v-if="!isPlatformAdmin">（需要组 ADMIN 权限）</template>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="createDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="handleCreateServer" :disabled="selectableGroups.length === 0">
            <el-icon :size="13"><Plus /></el-icon>创建服务器
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Import server -->
    <el-dialog v-model="importDialogVisible" width="520px" align-center class="srv-action-dialog" :show-close="false" destroy-on-close>
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--import">
            <el-icon :size="18"><FolderAdd /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">导入本地服务器</span>
            <span class="dlg-subtitle">将现有 MCDR 实例接入管理面板</span>
          </div>
          <button class="dlg-close-btn" @click="importDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="importFormRef" :model="importServerForm" :rules="importFormRules" label-position="top">
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="importServerForm.name" placeholder="为导入的服务器设置一个名称" />
        </el-form-item>
        <el-form-item label="服务器绝对路径" prop="path">
          <el-input v-model="importServerForm.path" placeholder="例如: /home/user/my_mcdr_server" />
          <div class="dlg-field-hint">请输入服务器上 MCDR 实例的根目录绝对路径（包含 config.yml 文件的目录）。</div>
        </el-form-item>
        <el-form-item label="服务器组" prop="serverLinkGroupIds" required>
          <el-select v-model="importServerForm.serverLinkGroupIds" multiple filterable placeholder="请选择服务器组" style="width:100%" :loading="serverLinkGroupsLoading">
            <el-option v-for="g in serverLinkGroups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <div class="dlg-field-hint" v-if="serverLinkGroups.length === 0 && !serverLinkGroupsLoading">
            暂无服务器组，请先<a class="text-link" @click="goToServerLinkGroups">创建服务器组</a>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="importDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="handleImportServer" :disabled="serverLinkGroups.length === 0">
            <el-icon :size="13"><FolderAdd /></el-icon>导入服务器
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Copy server -->
    <el-dialog v-model="copyDialogVisible" width="500px" align-center class="srv-action-dialog" :show-close="false" destroy-on-close>
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--copy">
            <el-icon :size="17"><DocumentCopy /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">复制服务器</span>
            <span class="dlg-subtitle">将现有服务器完整复制为新实例</span>
          </div>
          <button class="dlg-close-btn" @click="copyDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="copyFormRef" :model="copyServerForm" :rules="copyFormRules" label-position="top">
        <el-form-item label="新服务器名称" prop="name">
          <el-input v-model="copyServerForm.name" placeholder="为新服务器设置一个名称" />
        </el-form-item>
        <el-form-item label="服务器组" prop="serverLinkGroupIds" required>
          <el-select v-model="copyServerForm.serverLinkGroupIds" multiple filterable placeholder="请选择服务器组" style="width:100%" :loading="serverLinkGroupsLoading">
            <el-option v-for="g in selectableGroups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <div class="dlg-field-hint" v-if="selectableGroups.length === 0 && !serverLinkGroupsLoading">
            暂无可用的服务器组<template v-if="!isPlatformAdmin">（需要组 ADMIN 权限）</template>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="copyDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="handleCopyServer" :disabled="selectableGroups.length === 0">
            <el-icon :size="13"><DocumentCopy /></el-icon>复制服务器
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Rename server -->
    <el-dialog v-model="renameDialogVisible" width="400px" align-center class="srv-action-dialog" :show-close="false" destroy-on-close>
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--rename">
            <el-icon :size="17"><Edit /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">重命名服务器</span>
            <span class="dlg-subtitle">修改服务器的显示名称</span>
          </div>
          <button class="dlg-close-btn" @click="renameDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-form ref="renameFormRef" :model="renameForm" :rules="renameFormRules" label-position="top">
        <el-form-item label="新名称" prop="newName">
          <el-input v-model="renameForm.newName" placeholder="请输入新的服务器名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="renameDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="handleRenameServer" :disabled="renameLoading">
            <el-icon :size="13" class="is-loading" v-if="renameLoading"><Loading /></el-icon>
            <el-icon :size="13" v-else><Check /></el-icon>确认重命名
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Batch command -->
    <el-dialog v-model="commandDialogVisible" width="500px" align-center class="srv-action-dialog" :show-close="false" destroy-on-close>
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--cmd">
            <el-icon :size="17"><Promotion /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">批量发送指令</span>
            <span class="dlg-subtitle">向所有选中的服务器发送同一条命令</span>
          </div>
          <button class="dlg-close-btn" @click="commandDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-input v-model="batchCommand" placeholder="例如：say Hello / stop" class="cmd-input" />
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="commandDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="handleSendCommand">
            <el-icon :size="13"><Promotion /></el-icon>发送
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Config dialog -->
    <el-dialog
      v-model="configDialogVisible"
      width="800px"
      top="8vh"
      align-center
      destroy-on-close
      class="config-dialog srv-action-dialog"
      :show-close="false"
      @close="resetDialogState"
    >
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--config">
            <el-icon :size="17"><Setting /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">{{ dialogTitle }}</span>
            <span class="dlg-subtitle" v-if="currentConfigServer?.name">{{ currentConfigServer.name }}</span>
          </div>
          <button class="dlg-close-btn" @click="configDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <div v-loading="configLoading" element-loading-text="正在加载配置...">
        <el-scrollbar max-height="65vh" class="config-form-scrollbar" always>
          <!-- View 1: select type -->
          <div v-if="currentView === 'select_type'">
            <el-form label-position="top">
              <el-form-item label="请选择服务器类型">
                <el-select v-model="selectedServerTypeForSetup" placeholder="选择类型" style="width:100%">
                  <el-option v-for="item in serverTypes" :key="item.value" :label="item.label" :value="item.value" :disabled="(item as any).disabled" />
                </el-select>
              </el-form-item>
              <el-alert title="请注意" type="warning" :closable="false" show-icon style="margin-top:10px">
                服务器类型选择后将无法更改，它决定了服务器核心文件的基础结构。
              </el-alert>
            </el-form>
          </div>

          <!-- View 2: Velocity initial setup -->
          <div v-if="currentView === 'velocity_initial_setup'">
            <el-form :model="configFormData" label-position="top">
              <el-form-item>
                <div class="form-item-label"><span>Velocity 版本</span><small>将从 PaperMC API 下载</small></div>
                <el-select v-model="configFormData.core_config.core_version" placeholder="加载版本..." filterable :loading="isFetchingVersions" style="width:220px">
                  <el-option v-for="v in velocityVersions" :key="v" :label="v" :value="v" />
                </el-select>
              </el-form-item>
              <el-divider>启动命令</el-divider>
              <el-form-item>
                <div class="form-item-wrapper">
                  <div class="form-item-label"><span>编辑模式</span><small>在 JVM 配置 与 直接编辑启动命令 间切换</small></div>
                  <div class="form-item-control">
                    <el-radio-group v-model="commandEditMode" size="small">
                      <el-radio-button label="start_command">直接编辑启动命令</el-radio-button>
                      <el-radio-button label="jvm">JVM 配置</el-radio-button>
                    </el-radio-group>
                  </div>
                </div>
              </el-form-item>
              <template v-if="commandEditMode === 'jvm'">
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器Java命令</span><small>默认使用全局设置，可单独覆盖</small></div>
                    <div class="form-item-control">
                      <el-select class="input-long" v-model="configFormData.jvm.java_command" filterable allow-create default-first-option clearable placeholder="例如：java 或 /usr/bin/java">
                        <el-option v-for="cmd in javaCmdOptions" :key="cmd" :label="cmd" :value="cmd" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
                    <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.min_memory" placeholder="128M" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
                    <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.max_memory" placeholder="512M" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
                    <div class="form-item-control"><el-input class="input-long" v-model="configFormData.jvm.extra_args" placeholder="如：-XX:+UseG1GC" /></div>
                  </div>
                </el-form-item>
              </template>
              <template v-else>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>start_command</span><small>保存时将解析为 JVM 配置</small></div>
                    <div class="form-item-control"><el-input class="input-long" v-model="configFormData.start_command" type="textarea" :rows="3" placeholder="例如：java -Xms1G -Xmx4G -jar server.jar" /></div>
                  </div>
                </el-form-item>
              </template>
            </el-form>
          </div>

          <!-- View 3: full config -->
          <div v-if="currentView === 'full_config'">
            <el-form :model="configFormData" label-position="top">
              <div v-if="isVanillaFamily || isForgeType">
                <!-- Game version -->
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label">
                      <span>游戏版本</span>
                      <small v-if="isForgeType">选择 Forge 支持的游戏版本</small>
                      <small v-else>更改会重新下载核心</small>
                    </div>
                    <div class="form-item-control version-control">
                      <el-select v-model="configFormData.core_config.core_version" :placeholder="isForgeType ? '从 Forge 列表加载版本...' : '从 Mojang API 加载版本...'" filterable clearable :loading="isForgeType ? isFetchingForgeGameVersions : isFetchingVersions">
                        <template v-if="isForgeType">
                          <el-option v-for="v in forgeGameVersions" :key="v" :label="v" :value="v" />
                        </template>
                        <template v-else>
                          <el-option v-for="v in filteredMojangVersions" :key="v.id" :label="v.id" :value="v.id" />
                        </template>
                      </el-select>
                      <div v-if="isVanillaFamily" class="version-checkboxes">
                        <el-checkbox v-model="showSnapshots" size="small">显示快照版</el-checkbox>
                        <el-checkbox v-model="showExperiments" size="small">显示实验版</el-checkbox>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <!-- Fabric -->
                <el-form-item v-if="isVanillaFamily">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>启用Fabric</span><small>Enable Fabric</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.core_config.is_fabric" :disabled="!(isFabricAvailable || configFormData.core_config.server_type === 'beta18')" />
                      <small v-if="!isFabricAvailable && configFormData.core_config.core_version" style="color:var(--el-color-warning);margin-left:10px">该游戏版本无可用Fabric</small>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="isVanillaFamily && configFormData.core_config.is_fabric">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Fabric版本</span><small>Fabric Loader Version</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.loader_version" placeholder="加载Fabric版本..." filterable :loading="isFetchingFabricVersions" class="input-medium">
                        <el-option v-for="v in fabricLoaderVersions" :key="v" :label="v" :value="v" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="isForgeType">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Forge版本</span><small>Forge Loader Version</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.loader_version" placeholder="选择 Forge 版本" filterable :loading="isFetchingForgeLoaderVersions" class="input-medium">
                        <el-option v-for="v in forgeLoaderVersions" :key="v" :label="v" :value="v" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>启动命令</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>编辑模式</span><small>在 JVM 配置 与 直接编辑启动命令 间切换</small></div>
                    <div class="form-item-control">
                      <el-radio-group v-model="commandEditMode" size="small">
                        <el-radio-button label="start_command">直接编辑启动命令</el-radio-button>
                        <el-radio-button label="jvm">JVM 配置</el-radio-button>
                      </el-radio-group>
                    </div>
                  </div>
                </el-form-item>
                <template v-if="commandEditMode === 'jvm'">
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>服务器Java命令</span><small>默认使用全局设置，可单独覆盖</small></div>
                      <div class="form-item-control">
                        <el-select class="input-long" v-model="configFormData.jvm.java_command" filterable allow-create default-first-option clearable placeholder="例如：java 或 /usr/bin/java">
                          <el-option v-for="cmd in javaCmdOptions" :key="cmd" :label="cmd" :value="cmd" />
                        </el-select>
                      </div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
                      <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.min_memory" placeholder="1G" /></div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
                      <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.max_memory" placeholder="4G" /></div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
                      <div class="form-item-control"><el-input class="input-long" v-model="configFormData.jvm.extra_args" placeholder="如：-XX:+UseG1GC" /></div>
                    </div>
                  </el-form-item>
                </template>
                <template v-else>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>start_command</span><small>保存时将解析为 JVM 配置</small></div>
                      <div class="form-item-control"><el-input class="input-long" v-model="configFormData.start_command" type="textarea" :rows="3" placeholder="例如：java -Xms1G -Xmx4G -jar server.jar" /></div>
                    </div>
                  </el-form-item>
                </template>
                <el-divider>server.properties 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>种子</span><small>level-seed</small></div>
                    <div class="form-item-control"><el-input class="input-long" v-model="configFormData.vanilla_server_properties.seed" placeholder="如：123123" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>正版验证</span><small>online-mode</small></div>
                    <div class="form-item-control"><el-switch v-model="configFormData.vanilla_server_properties['online-mode']" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>游戏模式</span><small>gamemode</small></div>
                    <div class="form-item-control">
                      <el-select class="input-medium" v-model="configFormData.vanilla_server_properties.gamemode">
                        <el-option v-for="m in gamemodeOptions" :key="m.value" :label="m.label" :value="m.value" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>游戏难度</span><small>difficulty</small></div>
                    <div class="form-item-control">
                      <el-select class="input-medium" v-model="configFormData.vanilla_server_properties.difficulty">
                        <el-option v-for="item in difficultyOptions" :key="item.value" :label="item.label" :value="item.value" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>极限模式</span><small>hardcore</small></div>
                    <div class="form-item-control"><el-switch v-model="configFormData.vanilla_server_properties.hardcore" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器端口</span><small>server-port</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short" v-model="configFormData.vanilla_server_properties['server-port']" :min="1024" :max="65535" controls-position="right" />
                      <el-button :icon="Cpu" text @click="testPort(configFormData.vanilla_server_properties['server-port'])">测试</el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器公告</span><small>motd</small></div>
                    <div class="form-item-control"><el-input class="input-long" v-model="configFormData.vanilla_server_properties.motd" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最大玩家数</span><small>max-players</small></div>
                    <div class="form-item-control"><el-input-number class="input-short" v-model="configFormData.vanilla_server_properties['max-players']" :min="1" controls-position="right" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>视距</span><small>view-distance</small></div>
                    <div class="form-item-control"><el-input-number class="input-short" v-model="configFormData.vanilla_server_properties['view-distance']" :min="2" :max="32" controls-position="right" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>命令方块</span><small>enable-command-block</small></div>
                    <div class="form-item-control"><el-switch v-model="configFormData.vanilla_server_properties['enable-command-block']" /></div>
                  </div>
                </el-form-item>
                <el-divider>RCON 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>开启RCON</span><small>enable-rcon</small></div>
                    <div class="form-item-control"><el-switch v-model="configFormData.vanilla_server_properties['enable-rcon']" /></div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.vanilla_server_properties?.['enable-rcon']">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>RCON端口</span><small>rcon.port</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short" v-model="configFormData.vanilla_server_properties['rcon.port']" :min="1024" :max="65535" controls-position="right" />
                      <el-button :icon="Cpu" text @click="testPort(configFormData.vanilla_server_properties['rcon.port'])">测试</el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.vanilla_server_properties?.['enable-rcon']">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>RCON密码</span><small>rcon.password</small></div>
                    <div class="form-item-control"><el-input class="input-medium" v-model="configFormData.vanilla_server_properties['rcon.password']" show-password /></div>
                  </div>
                </el-form-item>
              </div>

              <!-- Velocity full config -->
              <div v-if="configFormData.core_config?.server_type === 'velocity'">
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Velocity 版本</span><small>更改会重新下载核心</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.core_version" placeholder="加载版本..." filterable :loading="isFetchingVersions" style="width:220px">
                        <el-option v-for="v in velocityVersions" :key="v" :label="v" :value="v" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>启动命令</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>编辑模式</span></div>
                    <div class="form-item-control">
                      <el-radio-group v-model="commandEditMode" size="small">
                        <el-radio-button label="start_command">直接编辑启动命令</el-radio-button>
                        <el-radio-button label="jvm">JVM 配置</el-radio-button>
                      </el-radio-group>
                    </div>
                  </div>
                </el-form-item>
                <template v-if="commandEditMode === 'jvm'">
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>服务器Java命令</span></div>
                      <div class="form-item-control">
                        <el-select class="input-long" v-model="configFormData.jvm.java_command" filterable allow-create default-first-option clearable placeholder="例如：java 或 /usr/bin/java">
                          <el-option v-for="cmd in javaCmdOptions" :key="cmd" :label="cmd" :value="cmd" />
                        </el-select>
                      </div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>最小内存</span></div>
                      <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.min_memory" placeholder="1G" /></div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>最大内存</span></div>
                      <div class="form-item-control"><el-input class="input-short" v-model="configFormData.jvm.max_memory" placeholder="4G" /></div>
                    </div>
                  </el-form-item>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>其他JVM参数</span></div>
                      <div class="form-item-control"><el-input class="input-long" v-model="configFormData.jvm.extra_args" placeholder="如：-XX:+UseG1GC" /></div>
                    </div>
                  </el-form-item>
                </template>
                <template v-else>
                  <el-form-item>
                    <div class="form-item-wrapper">
                      <div class="form-item-label"><span>直接编辑启动命令</span></div>
                      <div class="form-item-control"><el-input class="input-long" v-model="configFormData.start_command" type="textarea" :rows="3" /></div>
                    </div>
                  </el-form-item>
                </template>
                <el-divider>velocity.toml 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>正版验证</span><small>online-mode</small></div>
                    <div class="form-item-control"><el-switch v-model="configFormData.velocity_toml['online-mode']" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>监听地址</span><small>bind</small></div>
                    <div class="form-item-control input-long">
                      <el-input v-model="configFormData.velocity_toml.bind" placeholder="0.0.0.0:25565">
                        <template #append><el-button @click="testPort(configFormData.velocity_toml.bind.split(':')[1])">测试端口</el-button></template>
                      </el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器公告</span><small>motd</small></div>
                    <div class="form-item-control input-long"><el-input v-model="configFormData.velocity_toml.motd" /></div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>玩家信息转发</span><small>player-info-forwarding-mode</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.velocity_toml['player-info-forwarding-mode']" class="input-medium">
                        <el-option label="None (不推荐)" value="none" />
                        <el-option label="Modern (推荐，最安全)" value="modern" />
                        <el-option label="BungeeGuard" value="bungeeguard" />
                        <el-option label="Legacy" value="legacy" />
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.velocity_toml?.['player-info-forwarding-mode'] === 'modern'">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>转发秘钥</span><small>forwarding.secret</small></div>
                    <div class="form-item-control input-long"><el-input v-model="configFormData.velocity_toml.forwarding_secret" /></div>
                  </div>
                </el-form-item>
                <el-divider>子服务器配置</el-divider>
                <div class="content-wrapper">
                  <el-form-item class="full-width-item">
                    <el-table :data="velocitySubServersList" style="width:100%" size="small" border>
                      <el-table-column label="服务器名" prop="name">
                        <template #default="{ row }"><el-input v-model="row.name" placeholder="例如: Survival" /></template>
                      </el-table-column>
                      <el-table-column label="域名/IP" prop="ip">
                        <template #default="{ row }"><el-input v-model="row.ip" placeholder="127.0.0.1" /></template>
                      </el-table-column>
                      <el-table-column label="端口" prop="port">
                        <template #default="{ row }"><el-input v-model="row.port" placeholder="25565" type="number" /></template>
                      </el-table-column>
                      <el-table-column label="操作" width="80" align="center">
                        <template #default="scope">
                          <el-button type="danger" :icon="Delete" @click="removeSubServer(scope.$index)" circle plain />
                        </template>
                      </el-table-column>
                    </el-table>
                    <div style="margin-top:10px;width:100%;text-align:right">
                      <el-button @click="addManualSubServer">手动添加</el-button>
                      <el-button type="primary" @click="openAddSubServerDialog">从服务器列表中添加</el-button>
                    </div>
                  </el-form-item>
                </div>
                <div class="content-wrapper">
                  <el-form-item class="full-width-item">
                    <el-select v-model="velocityTryOrderNames" multiple placeholder="请选择登录服务器" style="width:100%;margin-bottom:10px" :disabled="velocitySubServersList.length === 0" clearable>
                      <el-option v-for="srv in velocitySubServersList" :key="srv.id" :label="srv.name" :value="srv.name" :disabled="!srv.name?.trim()" />
                    </el-select>
                    <div class="draggable-list-wrapper">
                      <draggable v-model="velocityTryOrderNames" item-key="element" class="draggable-tag-list" ghost-class="ghost">
                        <template #item="{ element }">
                          <el-tag class="draggable-tag-item" closable @close="removeTryServer(element)">
                            <el-icon><Rank /></el-icon> {{ element }}
                          </el-tag>
                        </template>
                      </draggable>
                      <p v-if="velocityTryOrderNames.length === 0" class="empty-try-text">请从上方选择服务器作为初始登录点，并可拖拽标签来排序。</p>
                    </div>
                  </el-form-item>
                </div>
              </div>

              <!-- Map upload (vanilla / forge) -->
              <template v-if="isVanillaFamily || isForgeType">
                <el-divider>地图配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>位置地图 (主世界 + 下界)</span><small>the_nether.json</small></div>
                    <div class="form-item-control map-upload-control">
                      <div class="map-upload-row">
                        <el-tag v-if="currentConfigServer?.map?.nether_json" type="success" plain>已配置</el-tag>
                        <el-tag v-else type="info" plain>未配置</el-tag>
                        <el-upload ref="netherMapUploaderRef" v-model:file-list="netherMapFileList" action="#" :auto-upload="false" :limit="1" accept=".json" :on-exceed="(files: any[]) => handleMapExceed('nether', files)" :on-change="(file: any) => handleMapFileChange('nether', file)">
                          <el-button :icon="Upload">选择文件</el-button>
                          <el-button type="primary" @click="handleUploadMapJson('nether')" :loading="isUploadingMap.nether">上传</el-button>
                        </el-upload>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>位置地图 (末地)</span><small>the_end.json</small></div>
                    <div class="form-item-control map-upload-control">
                      <div class="map-upload-row">
                        <el-tag v-if="currentConfigServer?.map?.end_json" type="success" plain>已配置</el-tag>
                        <el-tag v-else type="info" plain>未配置</el-tag>
                        <el-upload ref="endMapUploaderRef" v-model:file-list="endMapFileList" action="#" :auto-upload="false" :limit="1" accept=".json" :on-exceed="(files: any[]) => handleMapExceed('end', files)" :on-change="(file: any) => handleMapFileChange('end', file)">
                          <el-button :icon="Upload">选择文件</el-button>
                          <el-button type="primary" @click="handleUploadMapJson('end')" :loading="isUploadingMap.end">上传</el-button>
                        </el-upload>
                      </div>
                    </div>
                  </div>
                </el-form-item>
              </template>

            </el-form>
          </div>

          <!-- View 3b: unsupported type -->
          <div v-if="currentView === 'unsupported_type'" style="padding:20px">
            <p>此服务器类型 ({{ configFormData.core_config?.server_type }}) 的配置界面暂未支持。</p>
          </div>

          <!-- View 4: downloading -->
          <div v-if="currentView === 'downloading'" class="downloading-prompt">
            <el-progress type="circle" :percentage="downloadProgress" />
            <p>正在下载并安装核心文件，请稍候...</p>
          </div>

          <!-- View 5: needs first start -->
          <div v-if="currentView === 'needs_first_start'" class="initial-start-prompt">
            <el-alert title="需要首次启动以生成配置文件" type="warning" :closable="false" show-icon description="服务器核心文件已准备就绪。请启动一次服务器以生成默认配置文件，之后您才能进行详细配置。" />
            <div class="prompt-actions">
              <el-button type="primary" :icon="VideoPlay" @click="startAndContinue">启动并继续配置</el-button>
            </div>
          </div>
        </el-scrollbar>
      </div>

      <!-- View 6: waiting startup -->
      <div v-if="currentView === 'waiting_for_startup'" class="waiting-prompt">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p>服务器启动中，正在等待生成配置文件...</p>
        <small>请稍候，完成后将自动进入下一步。</small>
      </div>

      <template #footer>
        <div class="dlg-footer dlg-footer--split">
          <div class="footer-file-btns">
            <template v-if="currentView === 'full_config' && !dialogState.isNewSetup">
              <button class="dlg-btn-ghost dlg-btn-file" @click="openFileEditor('mcdr_config')">
                <el-icon :size="12"><Document /></el-icon>config.yml
              </button>
              <button v-if="configFormData.core_config?.server_type === 'vanilla' || configFormData.core_config?.server_type === 'beta18'" class="dlg-btn-ghost dlg-btn-file" @click="openFileEditor('mc_properties')">
                <el-icon :size="12"><Document /></el-icon>server.properties
              </button>
              <button v-if="configFormData.core_config?.server_type === 'velocity'" class="dlg-btn-ghost dlg-btn-file" @click="openFileEditor('velocity_toml')">
                <el-icon :size="12"><Document /></el-icon>velocity.toml
              </button>
            </template>
          </div>
          <div class="footer-right-buttons">
            <button class="dlg-btn-ghost" @click="configDialogVisible = false">取消</button>
            <button v-if="currentView === 'select_type'" class="dlg-btn-primary" @click="confirmServerType" :disabled="!selectedServerTypeForSetup">
              下一步 →
            </button>
            <button
              v-if="currentView === 'velocity_initial_setup' || currentView === 'full_config'"
              class="dlg-btn-primary"
              @click="handleSaveConfig"
              :disabled="isSavingConfig || isDownloading || configLoading"
            >
              <el-icon :size="13" class="is-loading" v-if="isSavingConfig"><Loading /></el-icon>
              <el-icon :size="13" v-else><Check /></el-icon>
              {{ dialogState.isNewSetup ? (configFormData.core_config?.server_type === 'velocity' ? '下载并准备' : '创建并保存') : '保存配置' }}
            </button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Velocity add sub-server dialog -->
    <el-dialog v-model="addSubServerDialogVisible" width="500px" append-to-body class="srv-action-dialog" :show-close="false">
      <template #header>
        <div class="dlg-head">
          <div class="dlg-icon dlg-icon--subserver">
            <el-icon :size="17"><Plus /></el-icon>
          </div>
          <div class="dlg-title-group">
            <span class="dlg-title">添加子服务器</span>
            <span class="dlg-subtitle">从已有服务器列表中选择加入</span>
          </div>
          <button class="dlg-close-btn" @click="addSubServerDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <el-table ref="subServerSelectionTable" :data="availableSubServers" @selection-change="handleSubServerSelectionChange" height="300px" row-key="id">
        <el-table-column type="selection" width="55" reserve-selection />
        <el-table-column property="name" label="服务器名称" />
        <el-table-column property="port" label="端口" />
      </el-table>
      <template #footer>
        <div class="dlg-footer">
          <button class="dlg-btn-ghost" @click="addSubServerDialogVisible = false">取消</button>
          <button class="dlg-btn-primary" @click="confirmAddSubServers">
            <el-icon :size="13"><Check /></el-icon>确认添加
          </button>
        </div>
      </template>
    </el-dialog>

    <ConfigEditor
      v-model:visible="editorDialog.visible"
      :title="editorDialog.title"
      :language="editorDialog.language"
      :loading="editorDialog.loading"
      :is-saving="editorDialog.saving"
      :initial-content="editorDialog.content"
      @save="handleSaveFile"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Cpu, Delete, Document, VideoPlay, Rank, Upload, Loading, Plus, Close, FolderAdd, Monitor, DocumentCopy, Edit, Promotion, Setting, Check } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import ConfigEditor from '@/components/ConfigEditor.vue'
import { useServerList } from '@/composables/useServerList'
import ServerListToolbar from './server-list/ServerListToolbar.vue'
import ServerCardView from './server-list/ServerCardView.vue'
import ServerTableView from './server-list/ServerTableView.vue'

const {
  viewMode, searchQuery, statusFilter,
  serverList, filteredServerList, loading, loaded, selectedServers, isBatchProcessing, autoStartSaving,
  tableRef, subServerSelectionTable, netherMapUploaderRef, endMapUploaderRef,
  currentPage, pageSize, pagedServerList, sortedFilteredList,
  serverLinkGroups, serverLinkGroupsLoading, selectableGroups,
  createDialogVisible, importDialogVisible, copyDialogVisible, commandDialogVisible,
  configDialogVisible, renameDialogVisible, addSubServerDialogVisible,
  formRef, importFormRef, copyFormRef, renameFormRef,
  newServerForm, importServerForm, copyServerForm, renameForm, batchCommand,
  formRules, importFormRules, copyFormRules, renameFormRules, renameLoading,
  configLoading, isSavingConfig, currentConfigServer, configFormData,
  selectedServerTypeForSetup, commandEditMode, currentView, dialogState, dialogTitle,
  velocityVersions, fabricLoaderVersions, isFetchingVersions,
  isFetchingFabricVersions, forgeGameVersions, forgeLoaderVersions,
  isFetchingForgeGameVersions, isFetchingForgeLoaderVersions,
  showSnapshots, showExperiments, isDownloading, downloadProgress, javaCmdOptions,
  filteredMojangVersions, availableSubServers, isFabricAvailable,
  isVanillaFamily, isForgeType,
  serverTypes, gamemodeOptions, difficultyOptions,
  velocitySubServersList, velocityTryOrderNames,
  netherMapFileList, endMapFileList, isUploadingMap,
  editorDialog,
  isPlatformAdmin, hasRole,
  handleSelectionChange,
  startServer, stopServer, restartServer, setAutoStart, handleDeleteServer, forceKillServer,
  handleBatchAction, handleSendCommand,
  openCreateDialog, handleCreateServer, openImportDialog, handleImportServer,
  openCopyDialog, handleCopyServer, openRenameDialog, handleRenameServer,
  openConfigDialog, resetDialogState, confirmServerType, handleSaveConfig, startAndContinue,
  addManualSubServer, removeSubServer, openAddSubServerDialog,
  handleSubServerSelectionChange, confirmAddSubServers, removeTryServer,
  handleMapFileChange, handleMapExceed, handleUploadMapJson,
  openFileEditor, handleSaveFile,
  goToConsole, goToServerLinkGroups, copyPath, testPort, handleCreateArchive,
} = useServerList()

// Wire the exposed inner table ref back to the composable's tableRef
const tableViewRef = ref<any>(null)
watch(tableViewRef, (v) => { tableRef.value = v?.tableEl ?? null }, { immediate: true })
</script>

<style scoped>
/* ─── Page layout ────────────────────────────────────────────── */
.sl-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
  min-height: 0;
}

/* ─── Glass card ─────────────────────────────────────────────── */
.sl-glass-card {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  overflow: hidden;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.sl-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .sl-glass-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Shimmer line */
.shimmer-line {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(119,181,254,0.7), rgba(239,183,186,0.6), rgba(167,139,250,0.5), transparent);
  background-size: 200% 100%;
  animation: shimmer 5s linear infinite;
  z-index: 2;
  pointer-events: none;
}
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* ─── Config dialog styles ───────────────────────────────────── */
.config-form-scrollbar { padding: 5px 25px 5px 15px; margin: 0 -25px 0 -15px; }
.config-dialog :deep(.el-form-item) {
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 8px;
  display: flex;
  flex-wrap: wrap;
}
.config-dialog :deep(.el-form-item:last-child) { border-bottom: none; }
.form-item-wrapper { display: flex; align-items: center; justify-content: flex-start; width: 100%; }
.form-item-label {
  flex: 0 0 35%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  padding-left: 3%;
  padding-right: 20px;
  white-space: normal;
}
.form-item-label span { font-size: 14px; color: var(--el-text-color-regular); line-height: 1.4; }
.form-item-label small { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.3; }
.form-item-control { flex: 0 1 55%; display: flex; justify-content: flex-start; align-items: center; gap: 10px; }
.map-upload-control { flex-direction: column; align-items: flex-start; gap: 6px; }
.map-upload-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.config-dialog :deep(.input-short) { width: 120px; }
.config-dialog :deep(.input-medium) { width: 220px; }
.config-dialog :deep(.input-long) { width: 100%; max-width: 350px; }
.config-dialog :deep(.full-width-item) { flex-direction: column; align-items: flex-start; border-bottom: 1px solid var(--el-border-color-lighter); }
.config-dialog :deep(.full-width-item .el-form-item__label) { justify-content: flex-start; margin-bottom: 8px; width: 100%; }
.config-dialog :deep(.full-width-item .el-form-item__content) { width: 100%; margin-left: 0 !important; }
.version-control { width: 100%; display: flex; justify-content: space-between; align-items: center; }
.version-control .el-select { width: 220px; }
.version-checkboxes { display: flex; flex-direction: column; align-items: flex-start; }
.config-dialog :deep(.version-checkboxes .el-checkbox) { height: 18px; }
.content-wrapper { width: 100%; padding-left: 3%; padding-right: 38px; box-sizing: border-box; }

.initial-start-prompt, .downloading-prompt, .waiting-prompt {
  padding: 20px; display: flex; flex-direction: column; align-items: center;
  gap: 20px; min-height: 200px; justify-content: center;
}
.waiting-prompt { gap: 15px; color: var(--el-text-color-regular); }
.waiting-prompt small { color: var(--el-text-color-secondary); }
.prompt-actions { margin-top: 20px; }

.draggable-list-wrapper { border: 1px solid var(--el-border-color); border-radius: 4px; padding: 10px; }
.draggable-tag-list { display: flex; width: 100%; flex-wrap: wrap; gap: 8px; }
.draggable-tag-item { cursor: grab; display: flex; align-items: center; gap: 5px; padding: 0 10px; height: 23px; font-size: 13px; }
.draggable-tag-item:active { cursor: grabbing; }
.ghost { opacity: 0.5; background: var(--el-color-primary-light-7); }
.empty-try-text { text-align: center; color: var(--el-text-color-secondary); font-size: 14px; margin: 10px 0; }

/* Form item info helper */
.el-form-item__info { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; margin-top: 4px; }
.text-link { color: var(--el-color-primary); text-decoration: underline; cursor: pointer; }
.text-link:hover { color: var(--el-color-primary-light-3); }

/* ─── Beautiful action dialogs (create / import) ─────────────── */
/* Global overrides — dialogs are teleported out of scoped context */
:global(.srv-action-dialog) {
  border-radius: 20px !important;
  overflow: hidden !important;
  border: 1px solid rgba(119, 181, 254, 0.18) !important;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.14), 0 8px 32px rgba(119, 181, 254, 0.12) !important;
}
:global(.dark .srv-action-dialog) {
  background: rgba(11, 17, 32, 0.94) !important;
  border-color: rgba(119, 181, 254, 0.13) !important;
}
:global(.srv-action-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.srv-action-dialog .el-dialog__body) { padding: 20px 22px 6px !important; }
:global(.srv-action-dialog .el-dialog__footer) { padding: 0 !important; }

/* Inputs inside dialog */
:global(.srv-action-dialog .el-input__wrapper) {
  border-radius: 12px !important;
  background: rgba(255, 255, 255, 0.62) !important;
  border: 1px solid rgba(119, 181, 254, 0.20) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
:global(.srv-action-dialog .el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.38) !important;
}
:global(.srv-action-dialog .el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.55) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.10) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark .srv-action-dialog .el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.16) !important;
}
:global(.dark .srv-action-dialog .el-input__wrapper.is-focus) {
  background: rgba(15, 23, 42, 0.85) !important;
}
:global(.srv-action-dialog .el-form-item__label) {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--el-text-color-regular) !important;
  padding-bottom: 5px !important;
}
:global(.srv-action-dialog .el-form-item) { margin-bottom: 18px !important; }

/* cmd-input: monospace font for command input */
:global(.srv-action-dialog .cmd-input .el-input__inner) {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace !important;
  font-size: 13px !important;
}

/* Config dialog body: narrower padding, scrollbar handles its own spacing */
:global(.config-dialog.srv-action-dialog .el-dialog__body) { padding: 4px 22px 0 !important; }

/* Dialog header */
.dlg-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.10);
  position: relative;
}
.dlg-icon {
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.dlg-icon--create   { background: var(--brand-primary); }
.dlg-icon--import   { background: #10b981; }
.dlg-icon--copy     { background: #a78bfa; }
.dlg-icon--rename   { background: var(--brand-primary); }
.dlg-icon--cmd      { background: #10b981; }
.dlg-icon--config   { background: #f59e0b; }
.dlg-icon--subserver { background: #06b6d4; }
.dlg-title-group { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.dlg-title { font-size: 15px; font-weight: 700; color: var(--color-text); line-height: 1.2; }
.dlg-subtitle { font-size: 12px; color: var(--el-text-color-secondary); }
.dlg-close-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 8px;
  border: 1px solid rgba(119, 181, 254, 0.18);
  background: transparent; color: var(--el-text-color-secondary);
  cursor: pointer; transition: all 0.15s ease; flex-shrink: 0;
}
.dlg-close-btn:hover { background: rgba(248, 113, 113, 0.10); border-color: rgba(248, 113, 113, 0.28); color: #ef4444; }

/* Dialog footer */
.dlg-footer {
  display: flex; justify-content: flex-end; align-items: center; gap: 10px;
  padding: 14px 20px 18px;
  border-top: 1px solid rgba(119, 181, 254, 0.09);
}
.dlg-footer--split { justify-content: space-between; }
.footer-file-btns { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.footer-right-buttons { display: flex; align-items: center; gap: 8px; }
.dlg-field-hint { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 5px; line-height: 1.5; }

.dlg-btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 16px; border-radius: 10px;
  border: 1px solid rgba(119, 181, 254, 0.22);
  background: transparent; color: var(--el-text-color-regular);
  font-size: 13px; font-weight: 500; cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}
.dlg-btn-ghost:hover { background: rgba(119, 181, 254, 0.07); border-color: rgba(119, 181, 254, 0.40); }

.dlg-btn-file {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}

.dlg-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 18px; border-radius: 10px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.35);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.dlg-btn-primary:hover:not(:disabled) { box-shadow: 0 6px 22px rgba(119, 181, 254, 0.55); transform: translateY(-1px); }
.dlg-btn-primary:active:not(:disabled) { transform: scale(0.97); }
.dlg-btn-primary:disabled { opacity: 0.42; cursor: not-allowed; box-shadow: none; }

/* ─── View grid: skeleton & content share same cell ──────── */
.sl-view-grid {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
}
.sk-servers,
.sl-views-wrap {
  grid-area: 1 / 1;
  min-height: 0;
}
.sl-views-wrap {
  display: flex;
  flex-direction: column;
}

/* ─── Page transitions ───────────────────────────────────── */
.pg-skeleton-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
  pointer-events: none;
  z-index: 1;
}
.pg-skeleton-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
.pg-content-enter-active {
  animation: pg-rise 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes pg-rise {
  from { opacity: 0; transform: translateY(24px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ─── Server list skeleton ───────────────────────────────── */
.sk-servers {
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  align-content: start;
  overflow: hidden;
}
@media (max-width: 1199px) { .sk-servers { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 899px)  { .sk-servers { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .sk-servers { grid-template-columns: 1fr; } }

.sk-server-card {
  height: 162px;
  border-radius: 16px;
}

/* ─── Shimmer ────────────────────────────────────────────── */
@keyframes shimmer-move {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
.shimmer {
  background: linear-gradient(90deg,
    rgba(128,128,128,0.08) 25%,
    rgba(128,128,128,0.18) 50%,
    rgba(128,128,128,0.08) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
}
:global(.dark) .shimmer {
  background: linear-gradient(90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.10) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
}
</style>
