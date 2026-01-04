<template>
  <el-form :model="config" label-position="top">
    <!-- 游戏版本 -->
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>游戏版本</span><small>更改会重新下载核心</small></div>
        <div class="form-item-control version-control">
          <el-select v-model="config.game_version" placeholder="从 Mojang API 加载版本..." filterable :loading="isFetchingVersions" clearable>
            <el-option v-for="version in filteredMojangVersions" :key="version.id" :label="version.id" :value="version.url"/>
          </el-select>
          <div class="version-checkboxes">
            <el-checkbox v-model="showSnapshots" size="small">显示快照版</el-checkbox>
            <el-checkbox v-model="showExperiments" size="small">显示实验版</el-checkbox>
          </div>
        </div>
      </div>
    </el-form-item>

    <!-- JVM 配置 -->
    <el-divider>JVM 配置</el-divider>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>最小内存</span><small>Min Memory</small></div>
        <div class="form-item-control"><el-input class="input-short" v-model="config.jvm.min_memory" placeholder="1G"></el-input></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
        <div class="form-item-control"><el-input class="input-short" v-model="config.jvm.max_memory" placeholder="4G"></el-input></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>其他JVM参数</span><small>Extra Args</small></div>
        <div class="form-item-control"><el-input class="input-long" v-model="config.jvm.extra_args" placeholder="如：-XX:+UseG1GC"></el-input></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>JAR文件名称</span><small>Jar File</small></div>
        <div class="form-item-control"><el-input class="input-medium" v-model="config.jar_name"></el-input></div>
      </div>
    </el-form-item>

    <!-- server.properties 配置 -->
    <el-divider>server.properties 配置</el-divider>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>种子</span><small>level-seed</small></div>
        <div class="form-item-control"><el-input class="input-long" v-model="config.server_properties.seed" placeholder="如：123123"></el-input></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>正版验证</span><small>online-mode</small></div>
        <div class="form-item-control"><el-switch v-model="config.server_properties['online-mode']"/></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>游戏模式</span><small>gamemode</small></div>
        <div class="form-item-control">
          <el-select class="input-medium" v-model="config.server_properties.gamemode">
            <el-option v-for="mode in gamemodeOptions" :key="mode.value" :label="mode.label" :value="mode.value"/>
          </el-select>
        </div>
      </div>
    </el-form-item>
    <!-- ... 省略其他 server.properties 表单项 ... -->
    <!-- 为保持简洁，此处省略了难度、极限模式、端口、MOTD等大量重复的表单项，实际项目中请将它们完整复制到这里 -->
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>服务器端口</span><small>server-port</small></div>
        <div class="form-item-control">
          <el-button :icon="Cpu" text @click="testPort(config.server_properties['server-port'])">测试</el-button>
          <el-input-number class="input-short" v-model="config.server_properties['server-port']" :min="1024" :max="65535" controls-position="right"/>
        </div>
      </div>
    </el-form-item>

    <!-- RCON 配置 -->
    <el-divider>RCON 配置</el-divider>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>开启RCON</span><small>enable-rcon</small></div>
        <div class="form-item-control"><el-switch v-model="config.server_properties['enable-rcon']"/></div>
      </div>
    </el-form-item>
    <el-form-item v-if="config.server_properties['enable-rcon']">
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>RCON端口</span><small>rcon.port</small></div>
        <div class="form-item-control">
          <el-button :icon="Cpu" text @click="testPort(config.server_properties['rcon.port'])">测试</el-button>
          <el-input-number class="input-short" v-model="config.server_properties['rcon.port']" :min="1024" :max="65535" controls-position="right"/>
        </div>
      </div>
    </el-form-item>
    <!-- ... 省略RCON密码表单项 ... -->
  </el-form>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { Cpu } from '@element-plus/icons-vue';
import apiClient, { isRequestCanceled } from '@/api';
import { ElMessage } from 'element-plus';

const props = defineProps({
  modelValue: { type: Object, required: true },
  testPort: { type: Function, required: true },
});
const emit = defineEmits(['update:modelValue']);

// 使用 computed 实现 v-model 的双向绑定
const config = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

// 版本相关状态
const mojangVersions = ref([]);
const isFetchingVersions = ref(false);
const showSnapshots = ref(false);
const showExperiments = ref(false);

const filteredMojangVersions = computed(() => {
  return mojangVersions.value.filter(v => {
    if (v.type === 'release') return true;
    if (showSnapshots.value && v.type === 'snapshot') return true;
    if (showExperiments.value && v.type === 'old_beta') return true;
    return false;
  });
});

const fetchMojangVersions = async () => {
  if (mojangVersions.value.length > 0) return;
  isFetchingVersions.value = true;
  try {
    const {data} = await apiClient.get('/api/minecraft/versions');
    mojangVersions.value = data.versions;
  } catch (error) {
    if (!isRequestCanceled(error)) ElMessage.error('获取 Minecraft 版本列表失败');
  } finally {
    isFetchingVersions.value = false;
  }
};

onMounted(fetchMojangVersions);

// 静态选项数据
const gamemodeOptions = [
  {label: '生存 (Survival)', value: 'survival'},
  {label: '创造 (Creative)', value: 'creative'},
  {label: '冒险 (Adventure)', value: 'adventure'},
  {label: '观察者 (Spectator)', value: 'spectator'},
];
const difficultyOptions = [
  {label: '和平 (Peaceful)', value: 'peaceful'},
  {label: '简单 (Easy)', value: 'easy'},
  {label: '普通 (Normal)', value: 'normal'},
  {label: '困难 (Hard)', value: 'hard'},
];
</script>
