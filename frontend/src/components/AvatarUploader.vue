<template>
  <el-dialog
      :model-value="visible"
      title="更换头像"
      width="600px"
      @update:model-value="$emit('update:visible', $event)"
      @closed="reset"
  >
    <div class="cropper-container">
      <!-- 左侧裁剪区域 -->
      <div class="cropper-wrapper">
        <VueCropper
            v-if="options.img"
            ref="cropperRef"
            :img="options.img"
            :output-size="options.size"
            :output-type="options.outputType"
            auto-crop
            auto-crop-width="200px"
            auto-crop-height="200px"
            fixed-box
            center-box
            @realTime="realTimePreview"
        />
        <div v-else class="placeholder">
          请选择一张图片
        </div>
      </div>
      <!-- 右侧预览区域 -->
      <div class="preview-wrapper">
        <p>预览</p>
        <!-- [已修正] 外部div作为固定的圆形遮罩 -->
        <div class="preview-box">
          <!-- [已修正] 内部img应用实时样式，使其在遮罩内部移动和缩放 -->
          <img v-if="previews.url" :src="previews.url" :style="previews.style" alt="Preview">
        </div>
      </div>
    </div>

    <template #footer>
      <!-- [已修正] 调整了 footer 的样式，让按钮靠右对齐 -->
      <div class="dialog-footer">
        <el-upload
            action="#"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept="image/png, image/jpeg, image/gif"
        >
          <el-button>选择图片</el-button>
        </el-upload>
        <el-button
            type="primary"
            @click="uploadCroppedImage"
            :loading="isUploading"
            :disabled="!options.img"
        >
          上传头像
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.cropper-container {
  display: flex;
  height: 300px;
}

.cropper-wrapper {
  flex: 1;
  margin-right: 20px;
  border: 1px dashed #ccc;
  background-color: #f0f2f5;
}

.placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #999;
  font-size: 14px;
}

.preview-wrapper {
  width: 200px;
  text-align: center;
}

.preview-wrapper p {
  color: #606266;
  font-size: 14px;
  margin-bottom: 10px;
}

.preview-box {
  width: 200px;
  height: 200px;
  border-radius: 50%;
  overflow: hidden; /* 这是关键，隐藏img超出部分 */
  border: 1px solid #ccc;
  margin: 0 auto;
  background-color: #f0f2f5;
}

/* [已修正] 让按钮靠右对齐，并增加间距 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}
</style>

<script setup>
import {ref, reactive, watch} from 'vue';
import 'vue-cropper/dist/index.css';
import {VueCropper} from 'vue-cropper';
import {ElMessage} from 'element-plus';
import apiClient from '@/api';

const props = defineProps({
  visible: Boolean,
});
const emit = defineEmits(['update:visible', 'success']);

const cropperRef = ref(null);
const isUploading = ref(false);
const options = reactive({
  img: '', // 裁剪图片的地址
  size: 1, // 裁剪生成图片的质量
  outputType: 'png', // 裁剪生成图片的格式
});

const previews = reactive({
  url: '',
  style: {},
});

const realTimePreview = (data) => {
  previews.url = data.url;
  previews.style = data.img;
};

const handleFileChange = (uploadFile) => {
  const file = uploadFile.raw;
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    options.img = e.target.result;
  };
  reader.readAsDataURL(file);
};

const uploadCroppedImage = () => {
  if (!cropperRef.value) return;
  isUploading.value = true;

  cropperRef.value.getCropBlob(async (data) => {
    const formData = new FormData();
    formData.append('file', data, 'avatar.png');

    try {
      await apiClient.post('/api/users/me/avatar', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      ElMessage.success('头像上传成功！');
      emit('success');
      emit('update:visible', false);
    } catch (error) {
      console.error('Avatar upload failed:', error);
      const detail = error.response?.data?.detail || '上传失败，请稍后再试。';
      ElMessage.error(detail);
    } finally {
      isUploading.value = false;
    }
  });
};

const reset = () => {
  options.img = '';
  previews.url = '';
  previews.style = {};
};

watch(() => props.visible, (newVal) => {
  if (!newVal) {
    reset();
  }
});
</script>
