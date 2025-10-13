<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="80vw"
    top="8vh"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:visible', false)"
    @closed="internalContent = ''"
    destroy-on-close
  >
    <div v-loading="loading" element-loading-text="正在加载文件内容..." class="editor-container">
      <codemirror
        v-model="internalContent"
        placeholder="正在加载文件内容..."
        :style="{ height: '65vh' }"
        :autofocus="true"
        :indent-with-tab="true"
        :tab-size="2"
        :extensions="extensions"
      />
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="isSaving">
          保存文件
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { Codemirror } from 'vue-codemirror';
import { yaml } from '@codemirror/lang-yaml';
import { oneDark } from '@codemirror/theme-one-dark'; // 暗色主题，可选

const props = defineProps({
  visible: Boolean,
  loading: Boolean,
  isSaving: Boolean,
  title: {
    type: String,
    default: '编辑文件'
  },
  initialContent: {
    type: String,
    default: ''
  },
  language: {
    type: String, // 'yaml' or other
    default: 'text'
  }
});

const emit = defineEmits(['update:visible', 'save']);

const internalContent = ref('');

// 根据语言 prop 动态选择代码高亮扩展
const extensions = computed(() => {
  const exts = [oneDark]; // 使用暗色主题
  if (props.language === 'yaml') {
    exts.push(yaml());
  }
  // 可以根据需要添加其他语言的扩展
  return exts;
});

// 当对话框可见且初始内容传入时，更新编辑器内容
watch(() => props.initialContent, (newVal) => {
  if (props.visible) {
    internalContent.value = newVal;
  }
});

const handleSave = () => {
  emit('save', internalContent.value);
};
</script>

<style scoped>
.editor-container {
  min-height: 200px; /* 防止加载时塌陷 */
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}

/* 确保dialog的内容区域没有内边距，让编辑器填满 */
:deep(.el-dialog__body) {
  padding: 0;
}
</style>
