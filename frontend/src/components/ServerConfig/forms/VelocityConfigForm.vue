<template>
  <el-form :model="config" label-position="top">
    <!-- 版本选择 -->
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label">
          <span>{{ isInitialSetup ? 'Velocity 版本' : '重新设置 Velocity 版本' }}</span>
          <small>{{ isInitialSetup ? '将从 PaperMC API 下载' : '将从 PaperMC API 下载（留空则为不变动）' }}</small>
        </div>
        <div class="form-item-control">
          <el-select v-model="config.game_version" placeholder="加载版本..." filterable :loading="isFetchingVersions" style="width: 220px;">
            <el-option v-for="version in velocityVersions" :key="version" :label="version" :value="version"/>
          </el-select>
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
    <!-- ... 省略其他 JVM 表单项 ... -->
     <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>最大内存</span><small>Max Memory</small></div>
        <div class="form-item-control"><el-input class="input-short" v-model="config.jvm.max_memory" placeholder="4G"></el-input></div>
      </div>
    </el-form-item>
    <el-form-item>
      <div class="form-item-wrapper">
        <div class="form-item-label"><span>JAR文件名称</span><small>Jar File</small></div>
        <div class="form-item-control"><el-input class="input-medium" v-model="config.jar_name"></el-input></div>
      </div>
    </el-form-item>

    <!-- velocity.toml 配置 -->
    <template v-if="!isInitialSetup">
      <el-divider>velocity.toml 配置</el-divider>
      <!-- ... 省略 velocity.toml 表单项 ... -->
      <el-form-item>
        <div class="form-item-wrapper">
          <div class="form-item-label"><span>监听地址</span><small>bind</small></div>
          <div class="form-item-control input-long">
            <el-input v-model="config.velocity_toml.bind" placeholder="0.0.0.0:25565">
              <template #append><el-button @click="testPort(config.velocity_toml.bind.split(':')[1])">测试端口</el-button></template>
            </el-input>
          </div>
        </div>
      </el-form-item>

      <!-- 子服务器配置 -->
      <el-divider>子服务器配置</el-divider>
      <el-form-item label="选择要代理的子服务器">
        <el-transfer
            v-model="velocitySelectedServerIds"
            :data="availableSubServers"
            :titles="['可用服务器', '已选服务器']"
            :props="{ key: 'id', label: 'name' }"
            @change="handleSubServerChange"
            filterable
            target-order="push"
            style="width: 100%;"
        />
      </el-form-item>
      <el-form-item label="设置初始登录服务器顺序 (可拖拽排序)">
        <div class="draggable-list-wrapper">
          <draggable v-model="velocityTryOrderServers" item-key="id" @end="updateTryOrder" class="draggable-list" ghost-class="ghost">
            <template #item="{ element }">
              <div class="draggable-item"><el-icon><Rank/></el-icon><span>{{ element.name }}</span></div>
            </template>
          </draggable>
          <p v-if="velocityTryOrderServers.length === 0" class="empty-try-text">请从上方选择子服务器以设置登录顺序。</p>
        </div>
      </el-form-item>
    </template>
  </el-form>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { Rank } from '@element-plus/icons-vue';
import draggable from 'vuedraggable';
import apiClient, { isRequestCanceled } from '@/api';
import { ElMessage } from 'element-plus';

const props = defineProps({
  modelValue: { type: Object, required: true },
  isInitialSetup: { type: Boolean, default: false },
  allServers: { type: Array, required: true },
  currentServerId: { type: Number, required: true },
  testPort: { type: Function, required: true },
});
const emit = defineEmits(['update:modelValue']);

const config = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

// 版本
const velocityVersions = ref([]);
const isFetchingVersions = ref(false);

const fetchVelocityVersions = async () => {
  if (velocityVersions.value.length > 0) return;
  isFetchingVersions.value = true;
  try {
    const {data} = await apiClient.get('/api/velocity/versions');
    velocityVersions.value = data.versions.reverse();
  } catch (error) {
    if (!isRequestCanceled(error)) ElMessage.error('获取 Velocity 版本列表失败');
  } finally {
    isFetchingVersions.value = false;
  }
};

// 子服务器管理
const velocitySelectedServerIds = ref([]);
const velocityTryOrderServers = ref([]);

const availableSubServers = computed(() => {
  return props.allServers.filter(s =>
    s.server_type !== 'velocity' && s.id !== props.currentServerId
  );
});

const initializeSubServers = () => {
  if (props.isInitialSetup) return;
  const currentServers = config.value.velocity_toml?.servers || {};
  const currentTry = config.value.velocity_toml?.try || [];
  const serverNameIdMap = new Map(props.allServers.map(s => [s.name, s.id]));
  const serverIdMap = new Map(props.allServers.map(s => [s.id, s]));

  velocitySelectedServerIds.value = Object.keys(currentServers).map(name => serverNameIdMap.get(name)).filter(Boolean);
  velocityTryOrderServers.value = currentTry.map(name => serverIdMap.get(serverNameIdMap.get(name))).filter(Boolean);
};

const handleSubServerChange = (selectedIds) => {
  const newServers = {};
  const selectedServerObjects = [];
  selectedIds.forEach(id => {
    const server = props.allServers.find(s => s.id === id);
    if (server) {
      newServers[server.name] = `127.0.0.1:${server.port}`;
      selectedServerObjects.push(server);
    }
  });
  config.value.velocity_toml.servers = newServers;
  velocityTryOrderServers.value = velocityTryOrderServers.value.filter(s => selectedIds.includes(s.id));
  selectedServerObjects.forEach(s => {
    if (!velocityTryOrderServers.value.some(ts => ts.id === s.id)) {
      velocityTryOrderServers.value.push(s);
    }
  });
  updateTryOrder();
};

const updateTryOrder = () => {
  config.value.velocity_toml.try = velocityTryOrderServers.value.map(s => s.name);
};

onMounted(() => {
  fetchVelocityVersions();
  initializeSubServers();
});

watch(() => props.modelValue, initializeSubServers, { deep: true });
</script>
