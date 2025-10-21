<template>
  <el-form label-position="top">
    <el-form-item label="请选择服务器类型">
      <el-select
        :model-value="modelValue"
        @update:model-value="emit('update:modelValue', $event)"
        placeholder="选择类型"
        style="width: 100%;"
      >
        <el-option v-for="item in serverTypes" :key="item.value" :label="item.label" :value="item.value" :disabled="item.disabled"/>
      </el-select>
    </el-form-item>
    <el-alert title="请注意" type="warning" :closable="false" show-icon style="margin-top: 10px;">
      服务器类型选择后将无法更改，它决定了服务器核心文件的基础结构。
    </el-alert>
  </el-form>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(['update:modelValue']);

// 静态数据：服务器类型
const serverTypes = [
  {label: 'Vanilla (官方版)', value: 'vanilla'},
  {label: 'Vanilla Legacy / Beta 1.8 (旧版官方)', value: 'beta18'},
  {label: 'Velocity (新一代群组服)', value: 'velocity'},
  {label: 'Bukkit (暂不支持配置)', value: 'bukkit', disabled: true},
  {label: 'Forge', value: 'forge'},
];
</script>
