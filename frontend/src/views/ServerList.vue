<template>
  <div class="server-list-container">
    <el-card shadow="never" v-loading="isBatchProcessing" element-loading-text="正在处理批量操作...">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>服务器列表</span>
          </div>
          <div class="header-right">
            <el-button-group v-if="hasRole('ADMIN')">
              <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建服务器</el-button>
              <el-button type="success" :icon="FolderChecked" @click="openImportDialog">导入服务器</el-button>
              <el-dropdown
                  @command="handleBatchAction"
                  trigger="click"
                  :disabled="selectedServers.length === 0"
                  class="batch-dropdown"
              >
                <el-button type="primary" class="batch-action-btn" :disabled="selectedServers.length === 0" >
                  批量操作 (已选 {{ selectedServers.length }} 项)
                  <el-icon class="el-icon--right">
                    <arrow-down/>
                  </el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="start" :icon="VideoPlay">启动</el-dropdown-item>
                    <el-dropdown-item command="stop" :icon="SwitchButton">停止</el-dropdown-item>
                    <el-dropdown-item command="restart" :icon="Refresh">重启</el-dropdown-item>
                    <el-dropdown-item command="delete" :icon="Delete">删除</el-dropdown-item>
                    <el-dropdown-item command="command" :icon="Promotion">发送指令</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button-group>
          </div>
        </div>
      </template>

      <el-table ref="tableRef" :data="serverList" style="width: 100%" v-loading="loading" row-key="id" height="100%"
                @selection-change="handleSelectionChange" class="table">
        <el-table-column type="selection" width="55" align="center" fixed/>

        <el-table-column prop="name" label="服务器名称" width="180" sortable fixed>
          <template #default="scope">
            <el-tooltip
                effect="dark"
                :content="scope.row.path"
                placement="top-start"
                :show-after="500"
                :persistent="false"
            >
              <span class="server-name-link" @click="copyPath(scope.row.path)">
                {{ scope.row.name }}
              </span>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120" align="center" sortable>
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row)" effect="dark" round
                    :class="['status-tag', scope.row.status === 'pending' ? 'pending-tag' : '']">
              {{ getStatusTagText(scope.row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="服务器类型" width="120" align="center" sortable prop="core_config.server_type">
          <template #default="scope">
            <span v-if="scope.row.core_config && scope.row.core_config.is_fabric === true">
              fabric
            </span>
            <span v-else>
              {{ scope.row.core_config ? scope.row.core_config.server_type : '' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="core_config.core_version" label="核心版本" width="180" align="center" sortable/>

        <el-table-column prop="size_mb" label="服务器大小 (MB)" width="160" align="center" sortable>
          <template #default="scope">
            <span v-if="scope.row.size_mb != null">{{ scope.row.size_mb.toFixed(3) }} MB</span>
            <span v-else>N/A</span>
          </template>
        </el-table-column>

        <el-table-column prop="port" label="局域网端口" width="120" align="center" sortable/>
        <el-table-column prop="rcon_port" label="RCON端口" width="120" align="center" />
        <el-table-column prop="rcon_password" label="RCON密码" min-width="150" align="center"  v-if="hasRole('ADMIN')">
          <template #default="scope">
            <div
                v-if="scope.row.rcon_port !== '未启用RCON' && scope.row.rcon_password !== 'N/A' && scope.row.rcon_password !== '不适用' && scope.row.rcon_password !== '未设置'">
              <span v-if="scope.row.rcon_password_visible" class="rcon-pass">{{ scope.row.rcon_password }}</span>
              <span v-else>••••••••</span>
              <el-icon class="password-toggle-icon" @click="togglePasswordVisibility(scope.row)">
                <View v-if="!scope.row.rcon_password_visible"/>
                <Hide v-else/>
              </el-icon>
            </div>
            <span v-else>{{ scope.row.rcon_password }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="450" align="center" fixed="right" v-if="hasRole('HELPER')">
          <template #default="scope">
            <el-button-group>
              <el-button size="small" type="primary" :icon="VideoPlay" @click="startServer(scope.row)"
                         :disabled="scope.row.status === 'running' || scope.row.status === 'pending' || scope.row.status === 'new_setup'"
                         :loading="scope.row.loading" v-if="hasRole('USER')"/>
              <el-button size="small" type="danger" :icon="SwitchButton" @click="stopServer(scope.row)"
                         :disabled="scope.row.status !== 'running'" :loading="scope.row.loading" v-if="hasRole('ADMIN')"/>
              <el-button size="small" type="warning" :icon="Refresh" @click="restartServer(scope.row)"
                         :disabled="scope.row.status !== 'running'" :loading="scope.row.loading" v-if="hasRole('USER')"/>
            </el-button-group>

            <el-dropdown trigger="click" style="margin-left: 10px;">
              <el-button size="small">
                更多操作
                <el-icon class="el-icon--right">
                  <arrow-down/>
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :icon="Monitor" @click="goToConsole(scope.row.id)"
                                    :disabled="scope.row.status === 'new_setup'" v-if="hasRole('ADMIN')">控制台
                  </el-dropdown-item>
                  <el-dropdown-item :icon="Setting" @click="openConfigDialog(scope.row)">配置</el-dropdown-item>
                  <el-dropdown-item :icon="Document" @click="openPluginConfigDialog(scope.row)" v-if="hasRole('HELPER')">插件配置
                  </el-dropdown-item>
                  <el-dropdown-item :icon="FolderAdd" @click="handleCreateArchive(scope.row)"
                                    :disabled="scope.row.server_type === 'velocity'" v-if="hasRole('HELPER')">永久备份
                  </el-dropdown-item>
                  <el-dropdown-item :icon="DocumentCopy" @click="openCopyDialog(scope.row)"
                                    :disabled="scope.row.status === 'running'" v-if="hasRole('ADMIN')">复制服务器
                  </el-dropdown-item>
                  <el-dropdown-item divided :icon="CircleClose" @click="forceKillServer(scope.row)"
                                    :disabled="scope.row.status !== 'running' && scope.row.status !== 'pending'" v-if="hasRole('ADMIN')">强制关闭
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>

            <el-button style="margin-left: 10px;" size="small" type="danger" @click="handleDeleteServer(scope.row)"
                       :icon="Delete" plain v-if="hasRole('ADMIN')">删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建服务器" width="500px" align-center>
      <el-form ref="formRef" :model="newServerForm" :rules="formRules" label-width="100px">
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="newServerForm.name" placeholder="例如: Survival"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleCreateServer">创建</el-button>
        </span>
      </template>
    </el-dialog>
    <el-dialog v-model="importDialogVisible" title="导入本地服务器" width="600px" align-center>
      <el-form ref="importFormRef" :model="importServerForm" :rules="importFormRules" label-width="120px">
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="importServerForm.name" placeholder="为导入的服务器设置一个名称"></el-input>
        </el-form-item>
        <el-form-item label="服务器绝对路径" prop="path">
          <el-input v-model="importServerForm.path" placeholder="例如: /home/user/my_mcdr_server"></el-input>
          <div class="el-form-item__info">
            请输入服务器上 MCDR 实例的根目录绝对路径 (包含 config.yml 文件的目录)。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleImportServer">导入</el-button>
        </span>
      </template>
    </el-dialog>
    <!-- 新增：复制服务器对话框 -->
    <el-dialog v-model="copyDialogVisible" title="复制已有服务器" width="500px" align-center>
      <el-form ref="copyFormRef" :model="copyServerForm" :rules="copyFormRules" label-width="120px">
        <el-form-item label="新服务器名称" prop="name">
          <el-input v-model="copyServerForm.name" placeholder="为新服务器设置一个名称"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="copyDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleCopyServer">复制</el-button>
        </span>
      </template>
    </el-dialog>
    <el-dialog v-model="commandDialogVisible" title="批量发送指令" width="500px" align-center>
      <el-input v-model="batchCommand" placeholder="请输入要发送到所选服务器的指令"/>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="commandDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSendCommand">发送</el-button>
        </span>
      </template>
    </el-dialog>
    <el-dialog
        v-model="configDialogVisible"
        :title="dialogTitle"
        width="800px"
        top="8vh"
        align-center
        destroy-on-close
        class="config-dialog"
        @close="resetDialogState"
    >
      <div v-loading="configLoading" element-loading-text="正在加载配置...">
        <el-scrollbar max-height="65vh" class="config-form-scrollbar">
          <!-- 视图 1: 选择服务器类型 -->
          <div v-if="currentView === 'select_type'">
            <el-form label-position="top">
              <el-form-item label="请选择服务器类型">
                <el-select v-model="selectedServerTypeForSetup" placeholder="选择类型" style="width: 100%;">
                  <el-option v-for="item in serverTypes" :key="item.value" :label="item.label" :value="item.value"
                             :disabled="item.disabled"/>
                </el-select>
              </el-form-item>
              <el-alert title="请注意" type="warning" :closable="false" show-icon style="margin-top: 10px;">
                服务器类型选择后将无法更改，它决定了服务器核心文件的基础结构。
              </el-alert>
            </el-form>
          </div>

          <!-- 视图 2: Velocity 首次配置 (仅版本和JVM) -->
          <div v-if="currentView === 'velocity_initial_setup'">
            <el-form :model="configFormData" label-position="top">

              <el-form-item>
                <div class="form-item-label"><span>Velocity 版本</span><small>将从 PaperMC API 下载</small></div>
                <el-select v-model="configFormData.core_config.core_version" placeholder="加载版本..." filterable
                           :loading="isFetchingVersions" style="width: 220px;">
                  <el-option v-for="version in velocityVersions" :key="version" :label="version"
                             :value="version"/>
                </el-select>
                <div class="form-item-wrapper">
                  <div class="form-item-control">
                  </div>
                </div>
              </el-form-item>
              <el-divider>JVM 配置</el-divider>
              <el-form-item>
                <div class="form-item-wrapper">
                  <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
                  <div class="form-item-control">
                    <el-input class="input-short" v-model="configFormData.jvm.min_memory" placeholder="128M"></el-input>
                  </div>
                </div>
              </el-form-item>
              <el-form-item>
                <div class="form-item-wrapper">
                  <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
                  <div class="form-item-control">
                    <el-input class="input-short" v-model="configFormData.jvm.max_memory" placeholder="512M"></el-input>
                  </div>
                </div>
              </el-form-item>
              <el-form-item>
                <div class="form-item-wrapper">
                  <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
                  <div class="form-item-control">
                    <el-input class="input-long" v-model="configFormData.jvm.extra_args"
                              placeholder="如：-XX:+UseG1GC"></el-input>
                  </div>
                </div>
              </el-form-item>
              <el-form-item>
                <div class="form-item-wrapper">
                  <div class="form-item-label"><span>Java 命令</span><small>来自系统设置</small></div>
                  <div class="form-item-control">
                    <el-input class="input-long" :model-value="settings.java_command" disabled></el-input>
                    <div class="form-tip">如需修改，请前往 设置 → 系统设置</div>
                  </div>
                </div>
              </el-form-item>
            </el-form>
          </div>

          <!-- 视图 3: 完整配置 (Vanilla & Velocity) -->
          <div v-if="currentView === 'full_config'">
            <el-form :model="configFormData" label-position="top">
              <!-- Vanilla/Beta18 专属配置 -->
              <div v-if="isVanillaFamily || isForgeType">
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label">
                      <span>游戏版本</span>
                      <small v-if="isForgeType">选择 Forge 支持的游戏版本</small>
                      <small v-else>更改会重新下载核心</small>
                    </div>
                    <div class="form-item-control version-control">
                      <el-select v-model="configFormData.core_config.core_version"
                                 :placeholder="isForgeType ? '从 Forge 列表加载版本...' : '从 Mojang API 加载版本...'"
                                 filterable
                                 clearable
                                 :loading="isForgeType ? isFetchingForgeGameVersions : isFetchingVersions">
                        <template v-if="isForgeType">
                          <el-option v-for="version in forgeGameVersions" :key="version" :label="version"
                                     :value="version"/>
                        </template>
                        <template v-else>
                          <el-option v-for="version in filteredMojangVersions" :key="version.id" :label="version.id"
                                     :value="version.id"/>
                        </template>
                      </el-select>
                      <div v-if="isVanillaFamily" class="version-checkboxes">
                        <el-checkbox v-model="showSnapshots" size="small">显示快照版</el-checkbox>
                        <el-checkbox v-model="showExperiments" size="small">显示实验版</el-checkbox>
                      </div>
                    </div>
                  </div>
                </el-form-item>

                <el-form-item v-if="isVanillaFamily">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>启用Fabric</span><small>Enable Fabric</small></div>
                    <div class="form-item-control">
                      <el-switch
                          v-model="configFormData.core_config.is_fabric"
                          :disabled="!(isFabricAvailable || configFormData.core_config.server_type === 'beta18') "
                      />
                      <small v-if="!isFabricAvailable && configFormData.core_config.core_version"
                             style="color: var(--el-color-warning); margin-left: 10px;">
                        该游戏版本无可用Fabric
                      </small>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="isVanillaFamily && configFormData.core_config.is_fabric">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Fabric版本</span><small>Fabric Loader Version</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.loader_version"
                                 placeholder="加载Fabric版本..."
                                 filterable
                                 :loading="isFetchingFabricVersions" class="input-medium">
                        <el-option v-for="version in fabricLoaderVersions" :key="version" :label="version"
                                   :value="version"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="isForgeType">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Forge版本</span><small>Forge Loader Version</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.loader_version"
                                 placeholder="选择 Forge 版本"
                                 filterable
                                 :loading="isFetchingForgeLoaderVersions" class="input-medium">
                        <el-option v-for="version in forgeLoaderVersions" :key="version" :label="version"
                                   :value="version"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>JVM 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
                    <div class="form-item-control">
                      <el-input class="input-short" v-model="configFormData.jvm.min_memory"
                                placeholder="1G"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
                    <div class="form-item-control">
                      <el-input class="input-short" v-model="configFormData.jvm.max_memory"
                                placeholder="4G"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
                    <div class="form-item-control">
                      <el-input class="input-long" v-model="configFormData.jvm.extra_args"
                                placeholder="如：-XX:+UseG1GC"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>server.properties 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>种子</span><small>level-seed</small></div>
                    <div class="form-item-control">
                      <el-input class="input-long" v-model="configFormData.vanilla_server_properties.seed"
                                placeholder="如：123123"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>正版验证</span><small>online-mode</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.vanilla_server_properties['online-mode']"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>游戏模式</span><small>gamemode</small></div>
                    <div class="form-item-control">
                      <el-select class="input-medium" v-model="configFormData.vanilla_server_properties.gamemode">
                        <el-option v-for="mode in gamemodeOptions" :key="mode.value" :label="mode.label"
                                   :value="mode.value"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>游戏难度</span><small>difficulty</small></div>
                    <div class="form-item-control">
                      <el-select class="input-medium" v-model="configFormData.vanilla_server_properties.difficulty">
                        <el-option v-for="item in difficultyOptions" :key="item.value" :label="item.label"
                                   :value="item.value"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>极限模式</span><small>hardcore</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.vanilla_server_properties.hardcore"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器端口</span><small>server-port</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short"
                                       v-model="configFormData.vanilla_server_properties['server-port']"
                                       :min="1024" :max="65535" controls-position="right"/>
                      <el-button :icon="Cpu" text
                                 @click="testPort(configFormData.vanilla_server_properties['server-port'])">
                        测试
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器公告</span><small>motd</small></div>
                    <div class="form-item-control">
                      <el-input class="input-long" v-model="configFormData.vanilla_server_properties.motd"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最大玩家数</span><small>max-players</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short"
                                       v-model="configFormData.vanilla_server_properties['max-players']"
                                       :min="1" controls-position="right"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>视距</span><small>view-distance</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short"
                                       v-model="configFormData.vanilla_server_properties['view-distance']"
                                       :min="2" :max="32" controls-position="right"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>命令方块</span><small>enable-command-block</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.vanilla_server_properties['enable-command-block']"/>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>RCON 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>开启RCON</span><small>enable-rcon</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.vanilla_server_properties['enable-rcon']"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.vanilla_server_properties['enable-rcon']">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>RCON端口</span><small>rcon.port</small></div>
                    <div class="form-item-control">
                      <el-input-number class="input-short"
                                       v-model="configFormData.vanilla_server_properties['rcon.port']"
                                       :min="1024" :max="65535" controls-position="right"/>
                      <el-button :icon="Cpu" text
                                 @click="testPort(configFormData.vanilla_server_properties['rcon.port'])">测试
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.vanilla_server_properties['enable-rcon']">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>RCON密码</span><small>rcon.password</small></div>
                    <div class="form-item-control">
                      <el-input class="input-medium" v-model="configFormData.vanilla_server_properties['rcon.password']"
                                show-password/>
                    </div>
                  </div>
                </el-form-item>
              </div>

              <!-- Velocity 专属配置 -->
              <div v-if="configFormData.core_config.server_type === 'velocity'">
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>Velocity 版本</span><small>更改会重新下载核心</small></div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.core_config.core_version" placeholder="加载版本..." filterable
                                 :loading="isFetchingVersions" style="width: 220px;">
                        <el-option v-for="version in velocityVersions" :key="version" :label="version"
                                   :value="version"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="isDownloading">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>下载进度</span></div>
                    <div class="form-item-control">
                      <el-progress :percentage="downloadProgress" style="width: 100%;"/>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>JVM 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
                    <div class="form-item-control">
                      <el-input class="input-short" v-model="configFormData.jvm.min_memory"
                                placeholder="1G"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
                    <div class="form-item-control">
                      <el-input class="input-short" v-model="configFormData.jvm.max_memory"
                                placeholder="4G"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
                    <div class="form-item-control">
                      <el-input class="input-long" v-model="configFormData.jvm.extra_args"
                                placeholder="如：-XX:+UseG1GC"></el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>velocity.toml 配置</el-divider>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>正版验证</span><small>online-mode</small></div>
                    <div class="form-item-control">
                      <el-switch v-model="configFormData.velocity_toml['online-mode']"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>监听地址</span><small>bind</small></div>
                    <div class="form-item-control input-long">
                      <el-input v-model="configFormData.velocity_toml.bind" placeholder="0.0.0.0:25565">
                        <template #append>
                          <el-button @click="testPort(configFormData.velocity_toml.bind.split(':')[1])">测试端口
                          </el-button>
                        </template>
                      </el-input>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>服务器公告</span><small>motd</small></div>
                    <div class="form-item-control input-long">
                      <el-input v-model="configFormData.velocity_toml.motd" placeholder="A Velocity Server"/>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item>
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>玩家信息转发</span><small>player-info-forwarding-mode</small>
                    </div>
                    <div class="form-item-control">
                      <el-select v-model="configFormData.velocity_toml['player-info-forwarding-mode']"
                                 class="input-medium">
                        <el-option label="None (不推荐，相当于离线上服，MC版本<=1.18.2)" value="none"/>
                        <el-option label="Modern (推荐，最安全)" value="modern"/>
                        <el-option label="BungeeGuard (安全，MC版本<1.13)" value="bungeeguard"/>
                        <el-option label="Legacy (兼容性高，MC版本<1.13，需安装BungeeGuard插件)" value="legacy"/>
                      </el-select>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item v-if="configFormData.velocity_toml['player-info-forwarding-mode'] === 'modern'">
                  <div class="form-item-wrapper">
                    <div class="form-item-label"><span>转发秘钥</span>
                      <small>秘钥不相同的两个Velocity只能代理各自的子服</small>
                      <small>不支持Vanilla MC</small>
                      <small>Fabric MC版本要求：>=1.16.4</small>
                      <small>Forge MC版本要求：>=1.14</small>
                      <small>Paper MC版本要求：>=1.13.1b377</small>
                      <small>forwarding.secret</small>
                    </div>
                    <div class="form-item-control input-long">
                      <el-input v-model="configFormData.velocity_toml.forwarding_secret" placeholder="kpjTz1eLPXaK"/>
                    </div>
                  </div>
                </el-form-item>
                <el-divider>子服务器配置</el-divider>
                <div class="form-item-label">
                  <span>要代理的子服务器</span>
                  <small>servers[]</small>
                </div>
                <div class="content-wrapper">
                  <el-form-item class="full-width-item">

                    <el-table :data="velocitySubServersList" style="width: 100%" size="small" border>
                      <el-table-column label="服务器名" prop="name">
                        <template #default="{ row }">
                          <el-input v-model="row.name" placeholder="例如: Survival"></el-input>
                        </template>
                      </el-table-column>
                      <el-table-column label="域名/IP" prop="ip">
                        <template #default="{ row }">
                          <el-input v-model="row.ip" placeholder="127.0.0.1"></el-input>
                        </template>
                      </el-table-column>
                      <el-table-column label="端口" prop="port">
                        <template #default="{ row }">
                          <el-input v-model="row.port" placeholder="25565" type="number"></el-input>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="80" align="center">
                        <template #default="scope">
                          <el-button type="danger" :icon="Delete" @click="removeSubServer(scope.$index)" circle
                                     plain></el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                    <div style="margin-top: 10px; width: 100%; text-align: right;">
                      <el-button @click="addManualSubServer">手动添加</el-button>
                      <el-button type="primary" @click="openAddSubServerDialog">从服务器列表中添加</el-button>
                    </div>
                  </el-form-item>
                </div>
                <div class="form-item-label">
                  <span>初始登录服务器顺序</span>
                  <small>servers[].try</small>
                </div>
                <div class="content-wrapper">
                  <el-form-item class="full-width-item">
                    <el-select
                        v-model="velocityTryOrderNames"
                        multiple
                        placeholder="请选择登录服务器 (至少一项)"
                        style="width: 100%; margin-bottom: 10px;"
                        :disabled="velocitySubServersList.length === 0"
                        clearable
                    >
                      <el-option
                          v-for="server in velocitySubServersList"
                          :key="server.id"
                          :label="server.name"
                          :value="server.name"
                          :disabled="!server.name || !server.name.trim()"
                      />
                    </el-select>
                    <div class="draggable-list-wrapper">
                      <draggable
                          v-model="velocityTryOrderNames"
                          item-key="element"
                          class="draggable-tag-list"
                          ghost-class="ghost"
                      >
                        <template #item="{ element }">
                          <el-tag class="draggable-tag-item" closable @close="removeTryServer(element)">
                            <el-icon>
                              <Rank/>
                            </el-icon>
                            {{ element }}
                          </el-tag>
                        </template>
                      </draggable>
                      <p v-if="velocityTryOrderNames.length === 0" class="empty-try-text">
                        请从上方选择服务器作为初始登录点，并可拖拽标签来排序。
                      </p>
                    </div>
	                  </el-form-item>
	                </div>
	              </div>
	
	              <el-divider>地图配置</el-divider>
	              <el-form-item>
	                <div class="form-item-wrapper">
	                  <div class="form-item-label">
	                    <span>位置地图 (主世界 + 下界)</span>
	                    <small>the_nether.json</small>
	                  </div>
	                  <div class="form-item-control map-upload-control">
	                    <div class="map-upload-row">
	                      <el-upload
	                          ref="netherMapUploaderRef"
	                          v-model:file-list="netherMapFileList"
	                          action="#"
	                          :auto-upload="false"
	                          :limit="1"
	                          accept=".json"
	                          :on-exceed="files => handleMapExceed('nether', files)"
	                          :on-change="file => handleMapFileChange('nether', file)"
	                      >
	                        <el-button :icon="Upload">选择文件</el-button>
	                      </el-upload>
	                      <el-button type="primary" @click="handleUploadMapJson('nether')" :loading="isUploadingMap.nether">
	                        上传
	                      </el-button>
	                      <el-tag v-if="currentConfigServer?.map?.nether_json" type="success" plain>已配置</el-tag>
	                      <el-tag v-else type="info" plain>未配置</el-tag>
	                    </div>
	                    <div class="map-upload-hint">用于主世界 + 下界双维度路径渲染</div>
	                  </div>
	                </div>
	              </el-form-item>
	              <el-form-item>
	                <div class="form-item-wrapper">
	                  <div class="form-item-label">
	                    <span>位置地图 (末地)</span>
	                    <small>the_end.json</small>
	                  </div>
	                  <div class="form-item-control map-upload-control">
	                    <div class="map-upload-row">
	                      <el-upload
	                          ref="endMapUploaderRef"
	                          v-model:file-list="endMapFileList"
	                          action="#"
	                          :auto-upload="false"
	                          :limit="1"
	                          accept=".json"
	                          :on-exceed="files => handleMapExceed('end', files)"
	                          :on-change="file => handleMapFileChange('end', file)"
	                      >
	                        <el-button :icon="Upload">选择文件</el-button>
	                      </el-upload>
	                      <el-button type="primary" @click="handleUploadMapJson('end')" :loading="isUploadingMap.end">
	                        上传
	                      </el-button>
	                      <el-tag v-if="currentConfigServer?.map?.end_json" type="success" plain>已配置</el-tag>
	                      <el-tag v-else type="info" plain>未配置</el-tag>
	                    </div>
	                    <div class="map-upload-hint">用于末地单维度路径渲染</div>
	                  </div>
	                </div>
	              </el-form-item>
	              <!-- 其他不支持的类型 -->
	              <div v-if="currentView === 'unsupported_type'">
	                <p>此服务器类型 ({{ configFormData.core_config.server_type }}) 的配置界面暂未支持。</p>
	              </div>
	            </el-form>
          </div>

          <!-- 视图 4: 正在下载 -->
          <div v-if="currentView === 'downloading'" class="downloading-prompt">
            <el-progress type="circle" :percentage="downloadProgress"/>
            <p>正在下载并安装核心文件，请稍候...</p>
          </div>

          <!-- 视图 5: 需要首次启动 -->
          <div v-if="currentView === 'needs_first_start'" class="initial-start-prompt">
            <el-alert
                title="需要首次启动以生成配置文件"
                type="warning"
                :closable="false"
                show-icon
                description="服务器核心文件已准备就绪。请启动一次服务器以生成默认配置文件 (如 velocity.toml 或 server.properties)，之后您才能进行详细配置。"
            />
            <div class="prompt-actions">
              <el-button type="primary" :icon="VideoPlay" @click="startAndContinue">
                启动并继续配置
              </el-button>
            </div>
          </div>
        </el-scrollbar>
      </div>
      <!-- 视图 6: 等待服务器首次启动完成 -->
      <div v-if="currentView === 'waiting_for_startup'" class="waiting-prompt">
        <el-icon class="is-loading" :size="40">
          <Loading/>
        </el-icon>
        <p>服务器启动中，正在等待生成配置文件...</p>
        <small>请稍候，完成后将自动进入下一步。</small>
      </div>
      <template #footer>
        <div class="dialog-footer-flex">
          <div class="footer-left-buttons">
            <template v-if="currentView === 'full_config' && !dialogState.isNewSetup">
              <el-button @click="openFileEditor('mcdr_config')" :icon="Document">编辑 config.yml</el-button>
              <el-button
                  v-if="configFormData.core_config.server_type === 'vanilla' || configFormData.core_config.server_type === 'beta18'"
                  @click="openFileEditor('mc_properties')" :icon="Document">编辑 server.properties
              </el-button>
              <el-button v-if="configFormData.core_config.server_type === 'velocity'"
                         @click="openFileEditor('velocity_toml')"
                         :icon="Document">编辑 velocity.toml
              </el-button>
            </template>
          </div>
          <div class="footer-right-buttons">
            <el-button @click="configDialogVisible = false">取消</el-button>
            <el-button v-if="currentView === 'select_type'" type="primary" @click="confirmServerType"
                       :disabled="!selectedServerTypeForSetup">下一步
            </el-button>
            <el-button v-if="currentView === 'velocity_initial_setup' || currentView === 'full_config'"
                       type="primary" @click="handleSaveConfig" :loading="isSavingConfig"
                       :disabled="isDownloading || configLoading">
              {{
                dialogState.isNewSetup ? (configFormData.core_config.server_type === 'velocity' ? '下载并准备' : '创建并保存') : '保存配置'
              }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Velocity 添加子服务器弹窗 -->
    <el-dialog v-model="addSubServerDialogVisible" title="从列表添加子服务器" width="500px" append-to-body>
      <el-table ref="subServerSelectionTable" :data="availableSubServers"
                @selection-change="handleSubServerSelectionChange"
                height="300px" row-key="id">
        <el-table-column type="selection" width="55" reserve-selection/>
        <el-table-column property="name" label="服务器名称"/>
        <el-table-column property="port" label="端口"/>
      </el-table>
      <template #footer>
        <el-button @click="addSubServerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddSubServers">确认添加</el-button>
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

    <!-- 插件管理弹窗 -->
    <el-dialog v-if="pluginConfigDialogVisible" v-model="pluginConfigDialogVisible"
               :title="`插件管理 - ${currentServerForPlugins?.name}`" width="60%" top="8vh" destroy-on-close>
      <div class="plugin-toolbar">
        <el-input v-model="installedPluginsQuery" placeholder="搜索插件名称或ID" clearable
                  style="width: 240px;"></el-input>
        <el-radio-group v-model="installedPluginsFilter" size="small">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="enabled">已启用</el-radio-button>
          <el-radio-button label="disabled">已禁用</el-radio-button>
        </el-radio-group>
        <el-button @click="() => { fetchInstalledPlugins(); fetchOnlinePlugins(true); }" circle>
          <el-icon>
            <Refresh/>
          </el-icon>
        </el-button>
      </div>

      <el-table :data="filteredInstalledPlugins" v-loading="pluginsLoading || onlinePluginsLoading" stripe border
                size="small"
                :row-class-name="installedPluginRowClassName" height="55vh">
        <el-table-column label="插件" min-width="260">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag type="primary" effect="plain" size="small" v-if="row.meta.id">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name || row.file_name }}</div>
                <div class="plugin-description">
                  {{
                    (row.meta.description?.zh_cn || row.meta.description?.en_us || row.meta.description || '').substring(0, 50)
                  }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="150">
          <template #default="{ row }">
            <span>{{ getAuthorsArray(row.meta).join(', ') || '未知' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="150">
          <template #default="{ row }">
            <div class="version-cell">
              <el-tag size="small" :type="row.meta.version ? 'success' : 'info'">{{
                  row.meta.version || '未知'
                }}
              </el-tag>
              <el-tooltip content="有新版本可用，点击更新" placement="top" v-if="isUpdateAvailable(row)">
                <el-button
                    type="primary"
                    size="small"
                    circle
                    plain
                    :loading="row.loading"
                    @click="handleUpdatePlugin(row)"
                >
                  <el-icon>
                    <Refresh/>
                  </el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最新版本" width="120">
          <template #default="{ row }">
            <el-tag v-if="onlinePluginsMap.get(row.meta.id)" size="small">
              {{ onlinePluginsMap.get(row.meta.id).release?.latest_version || 'N/A' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" :type="row.enabled ? 'warning' : 'success'" @click="handlePluginSwitch(row)"
                         :loading="row.loading">{{ row.enabled ? '禁用' : '启用' }}
              </el-button>
              <el-popconfirm title="确定删除这个插件吗？" @confirm="handlePluginDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger" :icon="Delete" :loading="row.loading"></el-button>
                </template>
              </el-popconfirm>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <div class="dialog-footer-flex">
          <div class="footer-left-buttons">
            <el-button @click="openAddOnlinePluginDialog">添加联网插件</el-button>
            <el-button @click="openAddDbPluginDialog">添加数据库插件</el-button>
          </div>
          <div class="footer-right-buttons">
            <el-button type="primary" @click="pluginConfigDialogVisible = false">完成</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 添加联网插件弹窗 -->
    <el-dialog v-if="addOnlinePluginDialogVisible" v-model="addOnlinePluginDialogVisible" title="从 MCDR 市场添加插件"
               width="60%" top="8vh" destroy-on-close>
      <div class="plugin-toolbar">
        <el-input v-model="onlinePluginsQuery" placeholder="搜索：名称 / ID / 作者" clearable
                  style="width: 300px;"></el-input>
      </div>
      <el-table :data="filteredOnlinePlugins" v-loading="onlinePluginsLoading"
                @selection-change="handleOnlineSelectionChange" stripe border height="50vh" row-key="meta.id">
        <el-table-column type="selection" width="55" reserve-selection/>
        <el-table-column label="插件" min-width="260">
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
        <el-table-column label="最新版本" width="130">
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
              <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
              <span v-if="getAuthorsArray(row.meta).length === 0">未知</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addOnlinePluginDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="prepareInstallationConfirmation"
                     :disabled="onlinePluginsSelected.length === 0">
            安装已选 ({{ onlinePluginsSelected.length }})
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- [NEW] 安装确认弹窗 -->
    <el-dialog v-if="installConfirmDialogVisible" v-model="installConfirmDialogVisible" title="安装确认" width="60%"
               top="8vh">
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
            <el-select
                v-if="row.availableVersions && row.availableVersions.length > 0"
                v-model="row.selectedVersion"
                placeholder="请选择版本"
                size="small"
                style="width: 100px;"
            >
              <el-option
                  v-for="version in row.availableVersions"
                  :key="version"
                  :label="version"
                  :value="version"
              />
            </el-select>
            <span v-else>无可用版本</span>
          </template>
        </el-table-column>
        <el-table-column label="依赖插件" width="230">
          <template #default="{ row }">
            <el-space wrap v-if="Object.keys(row.meta.dependencies || {}).length > 0">
              <el-tag v-for="(version, dep) in row.meta.dependencies" :key="dep" size="small" type="info">
                {{ dep }}: {{ version }}
              </el-tag>
            </el-space>
            <span v-else>无</span>
          </template>
        </el-table-column>
        <el-table-column label="Python 库">
          <template #default="{ row }">
            <el-space wrap v-if="(row.meta.requirements || []).length > 0">
              <el-tag v-for="req in row.meta.requirements" :key="req" size="small" type="warning">{{ req }}</el-tag>
            </el-space>
            <span v-else>无</span>
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

    <!-- 添加数据库插件弹窗 -->
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
            <el-tag v-if="row.meta.version" type="success" size="small">
              {{ row.meta.version || "未知" }}
            </el-tag>
            <el-tag v-else type="info" size="small">
              未知
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

	<script setup>
	import {
	  Plus, VideoPlay, SwitchButton, Refresh, Monitor, ArrowDown, Promotion,
	  View, Hide, Setting, Cpu, Delete, Document, FolderAdd, FolderChecked, Rank, Loading, CircleClose, DocumentCopy, Upload
	} from '@element-plus/icons-vue';
	import {io} from 'socket.io-client';
	import apiClient from '@/api';
	import {ref, onMounted, onUnmounted, reactive, computed, nextTick, watch} from 'vue';
	import {useRouter} from 'vue-router';
import {ElMessage, ElMessageBox, ElLoading, ElNotification} from 'element-plus';
import ConfigEditor from '@/components/ConfigEditor.vue';
import draggable from 'vuedraggable';
import { settings } from '@/store/settings'
import { hasRole } from '@/store/user';

const router = useRouter();
const serverList = ref([]);
const loading = ref(true);
const selectedServers = ref([]);
const isBatchProcessing = ref(false);

// 状态标签统一渲染，避免多个标签同时过渡导致换行
const getStatusTagType = (row) => {
  const s = row?.status
  if (s === 'running') return 'success'
  if (s === 'pending') return 'info'
  if (s === 'stopped') return 'warning'
  if (s === 'new_setup') return 'info'
  return 'danger'
}
const getStatusTagText = (row) => {
  const s = row?.status
  if (s === 'running') return '运行中'
  if (s === 'pending') return '启动中'
  if (s === 'stopped') return '未启动'
  if (s === 'new_setup') return '未配置'
  // 其他状态带上返回码
  return row?.return_code != null ? `已停止 (${row.return_code})` : '已停止'
}

let pollInterval = null;
let socket = null;

const tableRef = ref(null);
const createDialogVisible = ref(false);
const importDialogVisible = ref(false);
const copyDialogVisible = ref(false); // 新增
const commandDialogVisible = ref(false);
	const configDialogVisible = ref(false);
	const formRef = ref(null);
	const newServerForm = ref({name: ''});
	const importFormRef = ref(null);
	const importServerForm = ref({name: '', path: ''});
const copyFormRef = ref(null); // 新增
const copyServerForm = ref({name: ''}); // 新增
const sourceServerToCopy = ref(null); // 新增
const batchCommand = ref('');
const configLoading = ref(false);
const isSavingConfig = ref(false);
const currentConfigServer = ref(null);
const configFormData = ref({});
const selectedServerTypeForSetup = ref('');
const mojangVersions = ref([]);
const velocityVersions = ref([]);
const fabricGameVersions = ref([]);
const isFetchingVersions = ref(false);
const fabricLoaderVersions = ref([]);
const isFetchingFabricVersions = ref(false);
const forgeGameVersions = ref([]);
const forgeLoaderVersions = ref([]);
const isFetchingForgeGameVersions = ref(false);
const isFetchingForgeLoaderVersions = ref(false);
const showSnapshots = ref(false);
const showExperiments = ref(false);
const isDownloading = ref(false);
const downloadProgress = ref(0);
	const currentView = ref('select_type');
	const dialogState = reactive({isNewSetup: false, coreFileExists: false, configFileExists: false});
	
	// --- 地图 JSON 上传状态 ---
	const netherMapUploaderRef = ref(null);
	const endMapUploaderRef = ref(null);
	const netherMapFileList = ref([]);
	const endMapFileList = ref([]);
	const netherMapFile = ref(null);
	const endMapFile = ref(null);
	const isUploadingMap = reactive({nether: false, end: false});
const editorDialog = reactive({
  visible: false,
  loading: false,
  saving: false,
  title: '',
  content: '',
  language: '',
  fileType: ''
});
const formRules = reactive({name: [{required: true, message: '请输入服务器名称', trigger: 'blur'}]});
const importFormRules = reactive({
  name: [{required: true, message: '请输入服务器名称', trigger: 'blur'}],
  path: [{required: true, message: '请输入服务器的绝对路径', trigger: 'blur'}]
});
// 新增：复制服务器表单验证规则
const copyFormRules = reactive({
  name: [{required: true, message: '请输入新服务器的名称', trigger: 'blur'}]
});

// --- Velocity 配置状态 ---
const velocitySubServersList = ref([]);
const velocityTryOrderNames = ref([]);
const addSubServerDialogVisible = ref(false);
const selectedSubServersFromDialog = ref([]);


// --- 插件管理状态 ---
const pluginConfigDialogVisible = ref(false);
const addOnlinePluginDialogVisible = ref(false);
const addDbPluginDialogVisible = ref(false);
const installConfirmDialogVisible = ref(false); // [NEW]
const currentServerForPlugins = ref(null);

const installedPlugins = ref([]);
const pluginsLoading = ref(false);
const installedPluginsQuery = ref('');
const installedPluginsFilter = ref('all');

const onlinePlugins = ref([]);
const onlinePluginsLoading = ref(false);
const onlinePluginsQuery = ref('');
const onlinePluginsSelected = ref([]);
const pluginsToInstall = ref([]); // [NEW]

const dbPlugins = ref([]);
const dbPluginsLoading = ref(false);
const dbPluginsQuery = ref('');
const dbPluginsSelected = ref([]);

const isInstallingPlugins = ref(false);
// --- 结束插件管理状态 ---


const dialogTitle = computed(() => {
  if (!currentConfigServer.value) return '配置服务器';
  if (dialogState.isNewSetup) {
    return `初始化服务器配置 - ${currentConfigServer.value.name}`;
  }
  return `配置服务器 - ${currentConfigServer.value.name}`;
});
const isVanillaFamily = computed(() => {
  const type = configFormData.value?.core_config?.server_type;
  return type === 'vanilla' || type === 'beta18';
});
const isForgeType = computed(() => configFormData.value?.core_config?.server_type === 'forge');

const filteredMojangVersions = computed(() => {
  return mojangVersions.value.filter(v => {
    if (v.type === 'release') return true;
    if (showSnapshots.value && v.type === 'snapshot') return true;
    if (showExperiments.value && v.type === 'old_beta') return true;
    return false;
  });
});

const availableSubServers = computed(() => {
  if (!currentConfigServer.value) return [];
  // 排除类型为 'velocity' 的服务器和当前正在配置的服务器
  return serverList.value.filter(s =>
      s.core_config.server_type !== 'velocity' && s.id !== currentConfigServer.value.id
  );
});

// --- 插件相关计算属性 ---
const onlinePluginsMap = computed(() => {
  return new Map(onlinePlugins.value.map(p => [p.meta.id, p]));
});

const filteredInstalledPlugins = computed(() => {
  return installedPlugins.value.filter(p => {
    const query = installedPluginsQuery.value.toLowerCase();
    const matchesQuery = !query ||
        p.file_name.toLowerCase().includes(query) ||
        (p.meta.name && p.meta.name.toLowerCase().includes(query)) ||
        (p.meta.id && p.meta.id.toLowerCase().includes(query));

    const matchesFilter = installedPluginsFilter.value === 'all' ||
        (installedPluginsFilter.value === 'enabled' && p.enabled) ||
        (installedPluginsFilter.value === 'disabled' && !p.enabled);

    return matchesQuery && matchesFilter;
  });
});

const filteredOnlinePlugins = computed(() => {
  if (!onlinePluginsQuery.value) return onlinePlugins.value;
  const q = onlinePluginsQuery.value.toLowerCase();
  return onlinePlugins.value.filter(p =>
      p.meta.id.toLowerCase().includes(q) ||
      p.meta.name.toLowerCase().includes(q) ||
      getAuthorsArray(p.meta).join(',').toLowerCase().includes(q)
  );
});

const filteredDbPlugins = computed(() => {
  if (!dbPluginsQuery.value) return dbPlugins.value;
  const q = dbPluginsQuery.value.toLowerCase();
  return dbPlugins.value.filter(p =>
      p.file_name.toLowerCase().includes(q) ||
      (p.meta.name && p.meta.name.toLowerCase().includes(q))
  );
});
// --- 结束插件相关计算属性 ---

const serverTypes = [{label: 'Vanilla / Fabric', value: 'vanilla'}, {
  label: 'Vanilla Legacy / Beta 1.8 (旧版官方)',
  value: 'beta18'
}, {label: 'Velocity (新一代群组服)', value: 'velocity'}, {
  label: 'Bukkit (暂不支持配置)',
  value: 'bukkit',
  disabled: true
}, {label: 'Forge', value: 'forge'}];
const gamemodeOptions = [{label: '生存 (Survival)', value: 'survival'}, {
  label: '创造 (Creative)',
  value: 'creative'
}, {label: '冒险 (Adventure)', value: 'adventure'}, {label: '观察者 (Spectator)', value: 'spectator'}];
const difficultyOptions = [{label: '和平 (Peaceful)', value: 'peaceful'}, {
  label: '简单 (Easy)',
  value: 'easy'
}, {label: '普通 (Normal)', value: 'normal'}, {label: '困难 (Hard)', value: 'hard'}];
const isFabricAvailable = computed(() => {
  if (configFormData.value?.core_config?.server_type !== 'vanilla') return false;
  if (!configFormData.value?.core_config?.core_version || fabricGameVersions.value.length === 0) {
    return false;
  }
  return fabricGameVersions.value.includes(configFormData.value.core_config.core_version);
});

watch(isFabricAvailable, (isAvailable) => {
  if (!isAvailable && configFormData.value?.core_config?.server_type === 'vanilla'
      && configFormData.value?.core_config?.is_fabric) {
    configFormData.value.core_config.is_fabric = false;
    if (configDialogVisible.value) {
      ElMessage.warning('当前游戏版本不支持 Fabric，已自动禁用。');
    }
  }
});
watch(
    () => configFormData.value?.core_config?.is_fabric,
    (enabled) => {
      if (!configDialogVisible.value) return;
      const coreConfig = configFormData.value?.core_config;
      if (!coreConfig || coreConfig.server_type !== 'vanilla') return;
      if (!enabled) {
        fabricLoaderVersions.value = [];
        if (coreConfig.loader_version) {
          coreConfig.loader_version = '';
        }
        return;
      }
      fetchFabricLoaderVersions(coreConfig.core_version);
    }
);
watch(
    () => configFormData.value?.core_config?.core_version,
    (newVersion) => {
      if (!configDialogVisible.value) return;
      const coreConfig = configFormData.value?.core_config;
      if (!coreConfig) return;
      if (coreConfig.server_type === 'vanilla' && coreConfig.is_fabric) {
        fetchFabricLoaderVersions(newVersion);
      }
      if (coreConfig.server_type === 'forge') {
        fetchForgeLoaderVersions(newVersion);
      }
    }
);
watch(
    () => configFormData.value?.core_config?.server_type,
    async (type) => {
      if (!configDialogVisible.value) return;
      if (type === 'forge') {
        await fetchForgeGameVersions();
        if (configFormData.value.core_config?.is_fabric) {
          configFormData.value.core_config.is_fabric = false;
        }
        if (configFormData.value.core_config?.core_version) {
          await fetchForgeLoaderVersions(configFormData.value.core_config.core_version);
        } else {
          forgeLoaderVersions.value = [];
        }
      } else {
        forgeLoaderVersions.value = [];
      }
      if (type !== 'vanilla' && fabricLoaderVersions.value.length > 0) {
        fabricLoaderVersions.value = [];
      }
    }
);


const fetchServers = async () => {
  loading.value = true;
  try {
    const {data} = await apiClient.get('/api/servers');
    const selectedIds = new Set(selectedServers.value.map(s => s.id));

    serverList.value = data.map(s => ({...s, loading: false, rcon_password_visible: false}));

    await nextTick();
    if (tableRef.value) {
      tableRef.value.clearSelection();
      serverList.value.forEach(server => {
        if (selectedIds.has(server.id)) {
          tableRef.value.toggleRowSelection(server, true);
        }
      });
    }

  } finally {
    loading.value = false;
  }
};

	const resetDialogState = () => {
	  if (pollInterval) clearInterval(pollInterval);
	  pollInterval = null;
	  configLoading.value = false;
	  isSavingConfig.value = false;
	  isDownloading.value = false;
	  downloadProgress.value = 0;
	  currentView.value = 'select_type';
	  configFormData.value = {};
	  selectedServerTypeForSetup.value = '';
	  netherMapFile.value = null;
	  endMapFile.value = null;
	  netherMapFileList.value = [];
	  endMapFileList.value = [];
	  isUploadingMap.nether = false;
	  isUploadingMap.end = false;
	  // 重置 Velocity 相关状态
	  velocitySubServersList.value = [];
	  velocityTryOrderNames.value = [];
	  addSubServerDialogVisible.value = false;
	  selectedSubServersFromDialog.value = [];
  Object.assign(dialogState, {isNewSetup: false, coreFileExists: false, configFileExists: false,});
};

	const openConfigDialog = async (server) => {
	  resetDialogState();

  currentConfigServer.value = server;
  configDialogVisible.value = true;
  configLoading.value = true;
  try {
    const {data} = await apiClient.get(`/api/servers/config?server_id=${server.id}`);
    configFormData.value = data.config;
    dialogState.isNewSetup = data.is_new_setup;
    dialogState.coreFileExists = data.core_file_exists;
    dialogState.configFileExists = data.config_file_exists;
    const type = configFormData.value.core_config.server_type;
    if (!type && dialogState.isNewSetup) {
      currentView.value = 'select_type';
    } else if (type === 'vanilla' && dialogState.isNewSetup) {
      currentView.value = 'select_type';
    } else if (type === 'velocity') {
      if (!dialogState.coreFileExists) {
        currentView.value = 'velocity_initial_setup';
        await fetchVelocityVersions();
      } else if (!dialogState.configFileExists) {
        currentView.value = 'needs_first_start';
      } else {
        currentView.value = 'full_config';
        await fetchVelocityVersions();
        // 初始化 Velocity 子服务器数据
        const servers = data.config.velocity_toml?.servers || {};
        const tryOrder = data.config.velocity_toml?.try || [];
        velocitySubServersList.value = Object.entries(servers).map(([name, address], index) => {
          const parts = address.split(':');
          const ip = parts[0];
          const port = parts[1] || '';
          return {id: `${name}-${index}`, name, ip, port};
        });
        velocityTryOrderNames.value = tryOrder.filter(name => servers[name]);
        if (velocityTryOrderNames.value.length === 0 && velocitySubServersList.value.length > 0) {
          velocityTryOrderNames.value.push(velocitySubServersList.value[0].name);
        }
      }
    } else if (type === 'forge') {
      currentView.value = 'full_config';
      await fetchForgeGameVersions();
      if (configFormData.value.core_config.core_version) {
        await fetchForgeLoaderVersions(configFormData.value.core_config.core_version);
      }
    } else if (type === 'vanilla' || type === 'beta18') {
      currentView.value = 'full_config';
      await fetchFabricGameVersions();
      await fetchMojangVersions();
      if (configFormData.value.core_config.is_fabric) {
        await fetchFabricLoaderVersions(configFormData.value.core_config.core_version);
      }
    } else {
      currentView.value = 'unsupported_type';
    }
  } catch (error) {
    ElMessage.error(`加载配置失败: ${error.response?.data?.detail || error.message}`);
    configDialogVisible.value = false;
  } finally {
    configLoading.value = false;
	  }
	};

	const handleMapFileChange = (kind, uploadFile) => {
	  const raw = uploadFile?.raw || null;
	  if (kind === 'nether') netherMapFile.value = raw;
	  if (kind === 'end') endMapFile.value = raw;
	};

	const handleMapExceed = (kind, files) => {
	  const uploader = kind === 'nether' ? netherMapUploaderRef.value : endMapUploaderRef.value;
	  uploader?.clearFiles?.();
	  uploader?.handleStart?.(files?.[0]);
	};

	const handleUploadMapJson = async (kind) => {
	  if (!currentConfigServer.value) return;
	  if (kind !== 'nether' && kind !== 'end') return;
	
	  const file = kind === 'nether' ? netherMapFile.value : endMapFile.value;
	  if (!file) {
	    ElMessage.warning('请选择要上传的 JSON 文件');
	    return;
	  }
	
	  isUploadingMap[kind] = true;
	  const formData = new FormData();
	  formData.append('file', file);
	  try {
	    const {data} = await apiClient.post(`/api/servers/${currentConfigServer.value.id}/map-json/${kind}`, formData);
	    ElMessage.success('地图 JSON 上传成功');
	    currentConfigServer.value.map = {...(currentConfigServer.value.map || {}), ...(data.map || {})};
	    if (kind === 'nether') {
	      netherMapFile.value = null;
	      netherMapFileList.value = [];
	      netherMapUploaderRef.value?.clearFiles?.();
	    } else {
	      endMapFile.value = null;
	      endMapFileList.value = [];
	      endMapUploaderRef.value?.clearFiles?.();
	    }
	  } catch (error) {
	    ElMessage.error(error.response?.data?.detail || '上传失败');
	  } finally {
	    isUploadingMap[kind] = false;
	  }
	};
const confirmServerType = async () => {
  configFormData.value.core_config.server_type = selectedServerTypeForSetup.value;
  const type = configFormData.value.core_config.server_type;
  if (type === 'vanilla' || type === 'beta18') {
    currentView.value = 'full_config';
    await fetchMojangVersions();
  } else if (type === 'forge') {
    currentView.value = 'full_config';
    await fetchForgeGameVersions();
  } else if (type === 'velocity') {
    currentView.value = 'velocity_initial_setup';
    await fetchVelocityVersions();
  } else {
    currentView.value = 'unsupported_type';
  }
};
const handleSaveConfig = async () => {
  isSavingConfig.value = true;

  // 在保存前，为 Velocity 配置转换数据格式
  if (configFormData.value.core_config.server_type === 'velocity' && configFormData.value.velocity_toml) {
    const newServers = {};
    for (const server of velocitySubServersList.value) {
      if (server.name && server.name.trim() && server.ip && server.ip.trim() && server.port) {
        newServers[server.name.trim()] = `${server.ip.trim()}:${server.port}`;
      }
    }
    configFormData.value.velocity_toml.servers = newServers;
    configFormData.value.velocity_toml.try = velocityTryOrderNames.value;
  }

  const payload = {
    server_id: currentConfigServer.value.id,
    config: {...configFormData.value},
  };
  try {
    const {data} = await apiClient.post('/api/servers/config', payload);
    if (data.status === 'downloading' && data.task_id) {
      currentView.value = 'downloading';
      pollDownloadStatus(data.task_id);
    } else {
      ElMessage.success(data.message || '配置已成功保存！');
      if (configFormData.value.core_config.server_type === 'velocity' && !dialogState.configFileExists) {
        currentView.value = 'needs_first_start';
        return;
      }
      configDialogVisible.value = false;
      await fetchServers();
    }
  } catch (error) {
    ElMessage.error(`保存配置失败: ${error.response?.data?.detail || error.message}`);
  } finally {
    if (currentView.value !== 'downloading') {
      isSavingConfig.value = false;
    }
  }
};
const pollDownloadStatus = (taskId) => {
  isSavingConfig.value = false;
  pollInterval = setInterval(async () => {
    try {
      const {data} = await apiClient.get(`/api/system/task-progress/${taskId}`);
      downloadProgress.value = data.progress;
      if (data.status === 'SUCCESS') {
        clearInterval(pollInterval);
        pollInterval = null;
        ElMessage.success('核心文件安装完成');
        dialogState.coreFileExists = true;
        if (configFormData.value.core_config.server_type === 'velocity' && !dialogState.configFileExists) {
          currentView.value = 'needs_first_start';
        } else {
          ElMessage.success('核心文件安装完成');
          configDialogVisible.value = false;
          await fetchServers();
        }
      } else if (data.status === 'FAILED') {
        clearInterval(pollInterval);
        pollInterval = null;
        ElMessage.error(`处理失败: ${data.error || '未知错误'}`);
        currentView.value = configFormData.value.core_config.server_type === 'velocity' ? 'velocity_initial_setup' : 'full_config';
      }
    } catch (error) {
      clearInterval(pollInterval);
      pollInterval = null;
      ElMessage.error('无法获取进度，请检查后端服务。');
      currentView.value = configFormData.value.core_config.server_type === 'velocity' ? 'velocity_initial_setup' : 'full_config';
    }
  }, 500);
};
const startAndContinue = async () => {
  if (!currentConfigServer.value) return;
  currentView.value = 'waiting_for_startup';
  try {
    await apiClient.post(`/api/servers/start-for-while?server_id=${currentConfigServer.value.id}`);
    ElMessage.info(`已发送启动命令至 "${currentConfigServer.value.name}"`);
  } catch (e) {
    ElMessage.error(`启动失败: ${e.response?.data?.detail || e.message}`);
    currentView.value = 'needs_first_start';
    return;
  }
  let attempts = 0;
  const maxAttempts = 15;
  pollInterval = setInterval(async () => {
    attempts++;
    if (attempts > maxAttempts) {
      clearInterval(pollInterval);
      pollInterval = null;
      ElMessage.error('服务器启动超时，请检查控制台日志。');
      currentView.value = 'needs_first_start';
      return;
    }
    try {
      const {data} = await apiClient.get(`/api/servers/config?server_id=${currentConfigServer.value.id}`);
      if (data.config_file_exists) {
        clearInterval(pollInterval);
        pollInterval = null;
        ElMessage.success('服务器已就绪，正在加载完整配置！');
        await openConfigDialog(currentConfigServer.value);
      }
    } catch (error) {
      console.warn(`Polling for config file existence failed (attempt ${attempts}):`, error.message);
    }
  }, 2000);
};
const fetchMojangVersions = async () => {
  if (mojangVersions.value.length > 0) return;
  isFetchingVersions.value = true;
  try {
    const {data} = await apiClient.get('/api/minecraft/versions');
    mojangVersions.value = data.versions;
  } catch (error) {
    ElMessage.error('获取 Minecraft 版本列表失败');
  } finally {
    isFetchingVersions.value = false;
  }
};
const fetchVelocityVersions = async () => {
  if (velocityVersions.value.length > 0) return;
  isFetchingVersions.value = true;
  try {
    const {data} = await apiClient.get('/api/velocity/versions');
    velocityVersions.value = data.versions;
  } catch (error) {
    ElMessage.error('获取 Velocity 版本列表失败');
  } finally {
    isFetchingVersions.value = false;
  }
}
const fetchFabricGameVersions = async () => {
  if (fabricGameVersions.value.length > 0) return;
  try {
    const {data} = await apiClient.get('/api/fabric/game-versions');
    fabricGameVersions.value = data.versions;
  } catch (error) {
    console.error('获取 Fabric 兼容的游戏版本列表失败:', error);
  }
};
const fetchFabricLoaderVersions = async (mcVersion) => {
  if (!mcVersion) {
    fabricLoaderVersions.value = [];
    return;
  }
  isFetchingFabricVersions.value = true;
  try {
    const {data} = await apiClient.get(`/api/fabric/loader-versions?version_id=${mcVersion}`);
    fabricLoaderVersions.value = data.versions;
  } catch (error) {
    ElMessage.error('获取 Fabric Loader 版本列表失败');
    fabricLoaderVersions.value = [];
  } finally {
    isFetchingFabricVersions.value = false;
  }
};
const fetchForgeGameVersions = async () => {
  if (forgeGameVersions.value.length > 0) return;
  isFetchingForgeGameVersions.value = true;
  try {
    const {data} = await apiClient.get('/api/forge/game-versions');
    forgeGameVersions.value = data.versions;
  } catch (error) {
    ElMessage.error('获取 Forge 支持的游戏版本失败');
  } finally {
    isFetchingForgeGameVersions.value = false;
  }
};
const fetchForgeLoaderVersions = async (mcVersion) => {
  if (!mcVersion) {
    forgeLoaderVersions.value = [];
    if (configFormData.value?.core_config?.server_type === 'forge' &&
        configFormData.value.core_config.loader_version) {
      configFormData.value.core_config.loader_version = '';
    }
    return;
  }
  isFetchingForgeLoaderVersions.value = true;
  try {
    const {data} = await apiClient.get(`/api/forge/loader-versions?version_id=${mcVersion}`);
    forgeLoaderVersions.value = data.versions;
    if (configFormData.value?.core_config?.server_type === 'forge' &&
        configFormData.value.core_config.loader_version &&
        !forgeLoaderVersions.value.includes(configFormData.value.core_config.loader_version)) {
      configFormData.value.core_config.loader_version = '';
    }
  } catch (error) {
    ElMessage.error('获取 Forge 版本列表失败');
    forgeLoaderVersions.value = [];
  } finally {
    isFetchingForgeLoaderVersions.value = false;
  }
};
const addManualSubServer = () => {
  velocitySubServersList.value.push({
    id: `manual-${Date.now()}`,
    name: '',
    ip: '127.0.0.1',
    port: ''
  });
};
const removeSubServer = (index) => {
  const removedServerName = velocitySubServersList.value[index].name;
  velocitySubServersList.value.splice(index, 1);
  const tryIndex = velocityTryOrderNames.value.indexOf(removedServerName);
  if (tryIndex > -1) {
    velocityTryOrderNames.value.splice(tryIndex, 1);
  }
};
const openAddSubServerDialog = () => {
  selectedSubServersFromDialog.value = [];
  addSubServerDialogVisible.value = true;
};
const handleSubServerSelectionChange = (selection) => {
  selectedSubServersFromDialog.value = selection;
};
const confirmAddSubServers = () => {
  const existingNames = new Set(velocitySubServersList.value.map(s => s.name));
  selectedSubServersFromDialog.value.forEach(serverToAdd => {
    if (!existingNames.has(serverToAdd.name)) {
      velocitySubServersList.value.push({
        id: serverToAdd.id,
        name: serverToAdd.name,
        ip: '127.0.0.1',
        port: serverToAdd.port,
      });
    }
  });
  addSubServerDialogVisible.value = false;
};
const removeTryServer = (serverName) => {
  const index = velocityTryOrderNames.value.indexOf(serverName);
  if (index > -1) {
    velocityTryOrderNames.value.splice(index, 1);
  }
};
const openCreateDialog = () => {
  createDialogVisible.value = true;
  if (formRef.value) formRef.value.resetFields();
  newServerForm.value = {name: ''};
};
const handleCreateServer = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const {data: newServer} = await apiClient.post('/api/servers/create', newServerForm.value);
        await fetchServers();
        ElMessage.success('服务器已创建，请选择服务器类型。');
        createDialogVisible.value = false;
        resetDialogState();
        currentConfigServer.value = newServer;
        dialogState.isNewSetup = true;
        configFormData.value = {jvm: {min_memory: '128M', max_memory: '512M', extra_args: ''}};
        currentView.value = 'select_type';
        await await openConfigDialog(newServer);
      } catch (e) {
        ElMessage.error(`创建失败: ${e.response?.data?.detail || e.message}`);
      }
    }
  });
};
const startServer = async (s) => {
  s.loading = true;
  try {
    // 交互上立即置为“启动中”，避免先显示“运行中”再跳回“启动中”的视觉抖动
    s.status = 'pending'
    await apiClient.post(`/api/servers/start?server_id=${s.id}`);
    ElMessage.success(`${s.name} 已发送启动命令`);
  } catch (e) {
    ElMessage.error(`启动失败: ${e.response?.data?.detail || e.message}`);
    // 回退到未启动
    s.status = 'stopped'
    s.loading = false;
  }
};
const stopServer = async (s) => {
  s.loading = true;
  try {
    await apiClient.post(`/api/servers/stop?server_id=${s.id}`);
    ElMessage.success(`${s.name} 已发送停止命令`);
  } catch (e) {
    ElMessage.error(`停止失败: ${e.response?.data?.detail || e.message}`);
    s.loading = false;
  }
};
const restartServer = async (s) => {
  s.loading = true;
  try {
    await apiClient.post(`/api/servers/restart?server_id=${s.id}`);
    ElMessage.success(`${s.name} 已发送重启命令`);
  } catch (e) {
    ElMessage.error(`重启失败: ${e.response?.data?.detail || e.message}`);
    s.loading = false;
  }
};
const handleDeleteServer = (server) => {
  if (server.status === 'running') {
    ElMessage.error('服务器正在运行，请先停止再删除！');
    return;
  }
  ElMessageBox.confirm(`您确定要删除服务器 "${server.name}" 吗？此操作将永久删除其所有文件和配置，且无法恢复。`, '危险操作：删除服务器', {
    confirmButtonText: '确认删除',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'el-button--danger',
  }).then(async () => {
    const loadingInstance = ElLoading.service({lock: true, text: `正在删除服务器 ${server.name}...`});
    try {
      await apiClient.delete(`/api/servers/${server.id}`);
      ElMessage.success(`服务器 "${server.name}" 已被成功删除`);
      await fetchServers();
    } catch (error) {
      ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      loadingInstance.close();
    }
  }).catch(() => {
    ElMessage.info('已取消删除操作');
  });
};
const handleBatchAction = (action) => {
  if (selectedServers.value.length === 0) {
    ElMessage.warning('请至少选择一个服务器');
    return;
  }
  if (action === 'command') {
    batchCommand.value = '';
    commandDialogVisible.value = true;
  } else {
    const text = {start: '启动', stop: '停止', restart: '重启', delete: '删除'}[action];
    ElMessageBox.confirm(`确定要批量 ${text} ${selectedServers.value.length} 个服务器吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => executeBatchAction(action)).catch(() => {
    });
  }
};
const executeBatchAction = async (action, command = null) => {
  isBatchProcessing.value = true;
  const payload = {ids: selectedServers.value.map(s => s.id), command};
  try {
    await apiClient.post('/api/servers/batch-action', payload, {params: {action}});
    ElMessage.success('批量操作指令已发送！');
  } catch (e) {
    ElMessage.error(`批量操作失败: ${e.response?.data?.detail || e.message}`);
  } finally {
    isBatchProcessing.value = false;
  }
};
const handleSendCommand = () => {
  if (!batchCommand.value.trim()) {
    ElMessage.warning('指令不能为空');
    return;
  }
  executeBatchAction('command', batchCommand.value);
  commandDialogVisible.value = false;
};
const forceKillServer = (server) => {
  ElMessageBox.confirm(`这是一个危险操作，它会立即终止服务器进程，可能导致数据损坏。您确定要强制关闭服务器 "${server.name}" 吗？`, '确认强制关闭', {
    confirmButtonText: '强制关闭',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'el-button--danger',
  }).then(async () => {
    server.loading = true;
    try {
      const {data} = await apiClient.post(`/api/servers/force-kill?server_id=${server.id}`);
      ElMessage.success(`${server.name} 已发送强制关闭命令: ${data.message}`);
    } catch (e) {
      ElMessage.error(`强制关闭失败: ${e.response?.data?.detail || e.message}`);
      server.loading = false;
    }
  }).catch(() => {
    ElMessage.info('已取消强制关闭操作');
  });
};
const openImportDialog = () => {
  importDialogVisible.value = true;
  if (importFormRef.value) importFormRef.value.resetFields();
  importServerForm.value = {name: '', path: ''};
};
const handleImportServer = async () => {
  if (!importFormRef.value) return;
  await importFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        await apiClient.post('/api/servers/import', importServerForm.value);
        ElMessage.success('服务器已成功导入！');
        importDialogVisible.value = false;
        await fetchServers();
      } catch (e) {
        ElMessage.error(`导入失败: ${e.response?.data?.detail || e.message}`);
      }
    }
  });
};
const openCopyDialog = (server) => {
  sourceServerToCopy.value = server;
  copyServerForm.value.name = ''; // 重置名称字段
  copyDialogVisible.value = true;
  nextTick(() => {
    if (copyFormRef.value) {
      copyFormRef.value.clearValidate();
    }
  });
};
const handleCopyServer = async () => {
  if (!copyFormRef.value) return;
  await copyFormRef.value.validate(async (valid) => {
    if (valid) {
      const payload = {
        name: copyServerForm.value.name,
        path: sourceServerToCopy.value.path // 使用源服务器的路径
      };
      try {
        await apiClient.post('/api/servers/import', payload);
        ElMessage.success('服务器已成功复制！');
        copyDialogVisible.value = false;
        await fetchServers(); // 刷新列表
      } catch (e) {
        ElMessage.error(`复制失败: ${e.response?.data?.detail || e.message}`);
      }
    }
  });
};
const handleCreateArchive = async (server) => {
  try {
    await ElMessageBox.confirm(`这会打包服务器 "${server.name}" 的主世界文件夹，并创建一个永久备份。`, '确认创建永久备份', {type: 'info'});
    const {data} = await apiClient.post('/api/archives/create/from-server', null, {params: {server_id: server.id}});
    ElMessage.success('创建备份任务已发起！将跳转至存档管理页面。');
    router.push({path: '/tools/archives', query: {new_task_id: data.task_id}});
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '发起创建备份任务失败');
    }
  }
};
const goToConsole = (serverId) => {
  router.push(`/console/${serverId}`);
};
const copyPath = async (path) => {
  if (!path) return;
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(path);
      ElMessage.success('服务器路径已复制！');
      return;
    }
  } catch (err) {
    // 继续尝试后备方案
  }
  try {
    const textarea = document.createElement('textarea');
    textarea.value = path;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    if (ok) {
      ElMessage.success('服务器路径已复制！');
    } else {
      throw new Error('execCommand 失败');
    }
  } catch (error) {
    console.error('复制失败:', error);
    ElMessage.error('复制失败，请手动复制。');
  }
};
const togglePasswordVisibility = (row) => row.rcon_password_visible = !row.rcon_password_visible;
const testPort = async (port) => {
  if (!port) return ElMessage.warning('请输入有效的端口号');
  const msg = ElMessage({message: `正在测试端口 ${port}...`, type: 'info', duration: 0});
  try {
    const {data} = await apiClient.get(`/api/utils/check-port?port=${port}`);
    if (data.is_available) {
      ElMessage.success(`端口 ${port} 当前可用`);
    } else {
      ElMessage.warning(`端口 ${port} 当前已被占用`);
    }
  } catch (e) {
    ElMessage.error(`测试失败: ${e.response?.data?.detail || e.message}`);
  } finally {
    msg.close();
  }
};
const openFileEditor = async (fileType) => {
  editorDialog.fileType = fileType;
  editorDialog.loading = true;
  editorDialog.visible = true;
  editorDialog.content = '';
  const fileTypeMap = {
    mcdr_config: {title: '编辑 MCDR 配置文件 (config.yml)', language: 'yaml'},
    mc_properties: {title: '编辑 MC 配置文件 (server.properties)', language: 'properties'},
    velocity_toml: {title: '编辑 Velocity 配置文件 (velocity.toml)', language: 'toml'},
  };
  Object.assign(editorDialog, fileTypeMap[fileType]);
  try {
    const response = await apiClient.get(`/api/servers/${currentConfigServer.value.id}/config-file`, {
      params: {file_type: fileType},
      transformResponse: [(data) => data]
    });
    editorDialog.content = response.data;
  } catch (error) {
    ElMessage.error(`加载文件内容失败: ${error.response?.data?.detail || error.message}`);
    editorDialog.visible = false;
  } finally {
    editorDialog.loading = false;
  }
};
const handleSaveFile = async (newContent) => {
  editorDialog.saving = true;
  try {
    await apiClient.post(`/api/servers/${currentConfigServer.value.id}/config-file`, {
      file_type: editorDialog.fileType,
      content: newContent
    });
    ElMessage.success('文件已成功保存！');
    await openConfigDialog(currentConfigServer.value);
    editorDialog.visible = false;
  } catch (error) {
    ElMessage.error(`保存文件失败: ${error.response?.data?.detail || error.message}`);
  } finally {
    editorDialog.saving = false;
  }
};
const handleSelectionChange = (selection) => selectedServers.value = selection;

// --- 插件管理方法 ---
const compareVersions = (v1, v2) => {
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

const getAuthorsArray = (meta) => {
  if (!meta) return [];
  if (meta.authors) {
    if (Array.isArray(meta.authors)) return meta.authors.filter(Boolean);
    if (typeof meta.authors === 'string' && meta.authors.trim()) return [meta.authors];
  }
  if (meta.author) {
    if (Array.isArray(meta.author)) return meta.author.filter(Boolean);
    if (typeof meta.author === 'string' && meta.author.trim()) return [meta.author];
  }
  return [];
};

const openPluginConfigDialog = async (server) => {
  currentServerForPlugins.value = server;
  installedPluginsQuery.value = '';
  installedPluginsFilter.value = 'all';
  pluginConfigDialogVisible.value = true;
  await Promise.all([
    fetchInstalledPlugins(),
    fetchOnlinePlugins()
  ]);
};

const installedPluginRowClassName = ({row}) => {
  if (!row.enabled) {
    return 'disabled-plugin-row';
  }
  return '';
};

const fetchInstalledPlugins = async () => {
  if (!currentServerForPlugins.value) return;
  pluginsLoading.value = true;
  try {
    const {data} = await apiClient.get(`/api/plugins/server/${currentServerForPlugins.value.id}`);
    installedPlugins.value = (data.data || []).map(p => ({...p, loading: false}));
  } catch (error) {
    ElMessage.error(`加载插件列表失败: ${error.response?.data?.detail || error.message}`);
    installedPlugins.value = [];
  } finally {
    pluginsLoading.value = false;
  }
};

const handlePluginSwitch = async (plugin) => {
  plugin.loading = true;
  const enable = !plugin.enabled;
  try {
    await apiClient.post(`/api/plugins/server/${currentServerForPlugins.value.id}/switch/${plugin.file_name}?enable=${enable}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已${enable ? '启用' : '禁用'}`);
    await fetchInstalledPlugins();
  } catch (error) {
    ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    const foundPlugin = installedPlugins.value.find(p => p.file_name === plugin.file_name);
    if (foundPlugin) foundPlugin.loading = false;
  }
};

const handlePluginDelete = async (plugin) => {
  plugin.loading = true;
  try {
    await apiClient.delete(`/api/plugins/server/${currentServerForPlugins.value.id}/${plugin.file_name}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已删除`);
    await fetchInstalledPlugins();
  } catch (error) {
    ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    plugin.loading = false;
  }
};

const openAddOnlinePluginDialog = async () => {
  addOnlinePluginDialogVisible.value = true;
  onlinePluginsQuery.value = '';
  onlinePluginsSelected.value = [];
  await fetchOnlinePlugins();
};

const openAddDbPluginDialog = async () => {
  addDbPluginDialogVisible.value = true;
  dbPluginsQuery.value = '';
  dbPluginsSelected.value = [];
  await fetchDbPlugins();
};

const fetchOnlinePlugins = async (force = false) => {
  if (onlinePlugins.value.length > 0 && !force) return;
  onlinePluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/mcdr/versions');
    const map = data?.plugins || {};
    onlinePlugins.value = Object.keys(map).map(k => {
      const p = map[k];
      const latest = p?.release?.releases?.[0] ?? null;
      return {meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest};
    }).sort((a, b) => (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0));
  } catch (error) {
    ElMessage.error(`加载 MCDR 市场插件失败: ${error.message}`);
  } finally {
    onlinePluginsLoading.value = false;
  }
};

const fetchDbPlugins = async () => {
  dbPluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/db');
    dbPlugins.value = data || [];
  } catch (error) {
    ElMessage.error(`加载数据库插件失败: ${error.message}`);
  } finally {
    dbPluginsLoading.value = false;
  }
};

const getPluginInstallStatus = (pluginId) => {
  if (!pluginId) return null;
  const installed = installedPlugins.value.find(p => p.meta.id === pluginId);
  return installed ? installed.meta.version : null;
};

const handleOnlineSelectionChange = (selection) => {
  onlinePluginsSelected.value = selection;
};

const handleDbSelectionChange = (selection) => {
  dbPluginsSelected.value = selection;
};

const isUpdateAvailable = (installedPlugin) => {
  if (!installedPlugin.meta.id) return false;
  const onlinePlugin = onlinePluginsMap.value.get(installedPlugin.meta.id);
  if (!onlinePlugin || !onlinePlugin.release?.latest_version || !installedPlugin.meta.version) {
    return false;
  }
  return compareVersions(onlinePlugin.release.latest_version, installedPlugin.meta.version) > 0;
};

const handleUpdatePlugin = async (plugin) => {
  const onlinePlugin = onlinePluginsMap.value.get(plugin.meta.id);
  if (!onlinePlugin) {
    ElMessage.error("在市场中找不到该插件，无法更新。");
    return;
  }
  plugin.loading = true;
  try {
    const serverId = currentServerForPlugins.value.id;
    const pluginId = plugin.meta.id;
    const latestVersion = onlinePlugin.release.latest_version;
    const url = `/api/plugins/server/${serverId}/install/from-online?plugin_id=${encodeURIComponent(pluginId)}&tag_name=${encodeURIComponent(latestVersion)}`;
    await apiClient.post(url);
    ElNotification({
      title: '更新任务已创建',
      message: `插件 "${plugin.meta.name}" 已加入后台更新队列。`,
      type: 'success'
    });
    setTimeout(fetchInstalledPlugins, 3000);
  } catch (error) {
    ElNotification({
      title: '更新请求失败',
      message: `插件 "${plugin.meta.name}": ${error.response?.data?.detail || error.message}`,
      type: 'error',
      duration: 0
    });
  } finally {
    plugin.loading = false;
  }
}

const prepareInstallationConfirmation = () => {
  if (onlinePluginsSelected.value.length === 0) return;

  pluginsToInstall.value = onlinePluginsSelected.value.map(plugin => {
    const availableVersions = plugin.release?.releases?.map(r => r.meta.version).filter(Boolean) || [];
    const latestVersion = plugin.release?.latest_version;
    return {
      ...plugin,
      availableVersions,
      selectedVersion: latestVersion || (availableVersions.length > 0 ? availableVersions[0] : null)
    };
  });

  installConfirmDialogVisible.value = true;
};

const executeInstallation = async () => {
  if (pluginsToInstall.value.length === 0) return;
  isInstallingPlugins.value = true;

  const serverId = currentServerForPlugins.value.id;
  const installPromises = pluginsToInstall.value.map(plugin => {
    const pluginId = plugin.meta.id;
    const version = plugin.selectedVersion;
    if (!version) {
      return Promise.resolve({
        name: plugin.meta.name,
        status: 'rejected',
        reason: '未选择安装版本'
      });
    }
    const url = `/api/plugins/server/${serverId}/install/from-online?plugin_id=${encodeURIComponent(pluginId)}&tag_name=${encodeURIComponent(version)}`;
    return apiClient.post(url)
        .then(() => ({name: plugin.meta.name, status: 'fulfilled'}))
        .catch(err => ({
          name: plugin.meta.name,
          status: 'rejected',
          reason: err.response?.data?.detail || err.message
        }));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach(result => {
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
    addOnlinePluginDialogVisible.value = false;
    setTimeout(fetchInstalledPlugins, 1000);
  }
};


const handleInstallDbPlugins = async () => {
  if (dbPluginsSelected.value.length === 0) return;
  isInstallingPlugins.value = true;

  const serverId = currentServerForPlugins.value.id;
  const installPromises = dbPluginsSelected.value.map(plugin => {
    const url = `/api/plugins/server/${serverId}/install/from-db/${plugin.id}`;
    return apiClient.post(url)
        .then(() => ({name: plugin.meta.name || plugin.file_name, status: 'fulfilled'}))
        .catch(err => ({
          name: plugin.meta.name || plugin.file_name,
          status: 'rejected',
          reason: err.response?.data?.detail || err.message
        }));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach(result => {
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
    fetchInstalledPlugins();
  }
};
// --- 结束插件管理方法 ---


// --- 生命周期钩子 ---
onMounted(() => {
  fetchServers();
  fetchFabricGameVersions();
  fetchForgeGameVersions();

  // 同源连接 WebSocket（开发环境走 Vite 代理 /ws，生产由反代处理）
  socket = io({ path: '/ws/socket.io' });

  socket.on('connect', () => {
    console.log('WebSocket for ServerList connected successfully.');
  });

  socket.on('server_status_update', (updatedServer) => {
    if (updatedServer && updatedServer.id) {
      const index = serverList.value.findIndex(s => s.id === updatedServer.id);
      if (index !== -1) {
        const originalServer = serverList.value[index];
        serverList.value[index] = {
          ...originalServer,
          ...updatedServer,
          loading: false
        };
      }
    }
  });

  socket.on('server_delete', () => {
    fetchServers();
  });

  socket.on('server_create', () => {
    fetchServers();
  });

  socket.on('disconnect', () => {
    console.log('WebSocket for ServerList disconnected.');
  });

  socket.on('connect_error', (err) => {
    console.error('WebSocket connection error:', err);
  });
});

onUnmounted(() => {
  if (socket) {
    socket.disconnect();
  }
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<style scoped>
/* 服务器列表主容器：占满可用高度，内卡片和表格自适应填充 */
.server-list-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.server-list-container > .el-card {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  width: 100%;
}
.server-list-container > .el-card :deep(.el-card__body) {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  padding: 0; /* 去掉卡片内边距，让表格占满宽度 */
}
.server-list-container > .el-card :deep(.el-table) {
  height: 100%;
  width: 100%;
}

.content-wrapper {
  width: 100%;
  padding-left: 3%;
  padding-right: 38px;
  box-sizing: border-box; /* 关键：确保 padding 不会撑大容器的总宽度 */
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-right {
  display: flex;
  align-items: center;
}

/* 让下拉按钮自然融入按钮组 */
:deep(.el-button-group .batch-dropdown .el-button) {
  /* 仅移除左侧圆角，使之与前一个按钮贴合 */
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  margin-left: -1px; /* 去除组内按钮边框缝隙 */
}
:deep(.el-button-group > .el-button:first-child) {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.batch-action-btn {
  background-image: linear-gradient(180deg, #77B5FE, #5AA5FE);
  border-color: #5AA5FE;
}
.batch-action-btn.is-disabled,
.batch-dropdown[aria-disabled="true"] .batch-action-btn {
  opacity: 0.6;
}

.dialog-footer-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-left-buttons, .footer-right-buttons {
  display: flex;
  gap: 10px;
}

.config-form-scrollbar {
  padding: 5px 25px 5px 15px;
  margin: 0 -25px 0 -15px;
}

.config-dialog :deep(.el-form-item) {
  margin-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 8px;
  display: flex;
  flex-wrap: wrap;
}

.config-dialog :deep(.el-form-item:last-child) {
  border-bottom: none;
}

.form-item-wrapper {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
}

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

.form-item-label span {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.4;
}

.form-item-label small {
  margin-left: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.3;
}

	.form-item-control {
	  flex: 0 1 55%;
	  display: flex;
	  justify-content: flex-start;
	  align-items: center;
	  gap: 10px;
	}
	
	.map-upload-control {
	  flex-direction: column;
	  align-items: flex-start;
	  gap: 6px;
	}
	
	.map-upload-row {
	  display: flex;
	  align-items: center;
	  gap: 10px;
	  flex-wrap: wrap;
	}
	
	.map-upload-hint {
	  color: var(--el-text-color-secondary);
	  font-size: 12px;
	  line-height: 1.3;
	}

.config-dialog :deep(.input-short) {
  width: 120px;
}

.config-dialog :deep(.input-medium) {
  width: 220px;
}

.config-dialog :deep(.input-long) {
  width: 100%;
  max-width: 350px;
}

.config-dialog :deep(.full-width-item) {
  flex-direction: column;
  align-items: flex-start;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.config-dialog :deep(.full-width-item .el-form-item__label) {
  justify-content: flex-start;
  margin-bottom: 8px;
  width: 100%;
}

.config-dialog :deep(.full-width-item .el-form-item__content) {
  width: 100%;
  margin-left: 0 !important;
}


.version-control {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version-control .el-select {
  width: 220px;
}

.version-checkboxes {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.config-dialog :deep(.version-checkboxes .el-checkbox) {
  height: 18px;
}

.el-form-item__info {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  margin-top: 4px;
}

.draggable-list-wrapper {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 10px;
}

.draggable-tag-list {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  gap: 8px;
}

.draggable-tag-item {
  cursor: grab;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 10px;
  height: 23px;
  font-size: 13px;
}

.draggable-tag-item:active {
  cursor: grabbing;
}

.ghost {
  opacity: 0.5;
  background: var(--el-color-primary-light-7);
}

.empty-try-text {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin: 10px 0;
}

.initial-start-prompt, .downloading-prompt, .waiting-prompt {
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  min-height: 200px;
  justify-content: center;
}

.waiting-prompt {
  gap: 15px;
  color: var(--el-text-color-regular);
}

.prompt-actions {
  margin-top: 20px;
}

.waiting-prompt small {
  color: var(--el-text-color-secondary);
}

/* --- 插件管理样式 --- */
.plugin-toolbar {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
  align-items: center;
}

.plugin-id {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.server-list-container :deep(.disabled-plugin-row) {
  color: #a8abb2;
  background-color: #fafafa;
}

.server-list-container :deep(.disabled-plugin-row:hover > td) {
  background-color: #f5f5f5 !important;
}

.server-list-container :deep(.disabled-plugin-row .el-tag) {
  color: var(--el-text-color-secondary);
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
  color: var(--el-text-color-secondary);
  line-height: 1.3;
}

/* 列表页额外细节优化 */
.server-name-link {
  color: var(--brand-primary);
  cursor: pointer;
  text-decoration: none;
  transition: color var(--t-fast);
}
.server-name-link:hover {
  color: var(--el-color-primary-light-3);
  text-decoration: underline;
}

.password-toggle-icon {
  margin-left: 6px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: color var(--t-fast), transform var(--t-fast);
}
.password-toggle-icon:hover {
  color: var(--brand-primary);
  transform: scale(1.05);
}

.version-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 确保圆形主按钮内图标可见（新版本刷新按钮） */
.version-cell .el-button.is-circle .el-icon { display: inline-flex; align-items: center; justify-content: center; }
.version-cell .el-button.el-button--primary.is-circle:not(.is-plain) .el-icon { color: #fff; }
.version-cell .el-button.el-button--primary.is-circle.is-plain .el-icon { color: var(--brand-primary); }

/* 状态标签：避免换行与双标签并存导致行高跳动 */
.status-tag { white-space: nowrap; }

/* 启动中使用品牌蓝色（深色标签） */
.pending-tag {
  background-color: var(--el-color-primary) !important;
  border-color: var(--el-color-primary) !important;
  color: #fff !important;
}
</style>
