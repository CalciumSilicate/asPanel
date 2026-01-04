<template>
  <el-dialog
      :model-value="visible"
      title="更换头像"
      width="520px"
      @update:model-value="$emit('update:visible', $event)"
      @closed="reset"
  >
    <div class="avatar-uploader-container">
      <!-- 上传区域 -->
      <div class="upload-area" v-if="!imageUrl">
        <el-upload
            class="avatar-upload"
            drag
            action="#"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept="image/png, image/jpeg, image/gif, image/webp"
        >
          <el-icon class="upload-icon"><Upload /></el-icon>
          <div class="upload-text">
            <p>拖拽图片到此处，或点击选择</p>
            <p class="upload-hint">支持 PNG、JPG、GIF、WebP 格式</p>
          </div>
        </el-upload>
      </div>

      <!-- 裁剪区域 -->
      <div class="cropper-area" v-else>
        <div class="cropper-wrapper">
          <VueCropper
            ref="cropperRef"
            :img="imageUrl"
            :output-size="1"
            output-type="png"
            :info="false"
            :can-scale="true"
            :auto-crop="true"
            :auto-crop-width="256"
            :auto-crop-height="256"
            :fixed="true"
            :fixed-number="[1, 1]"
            :center-box="true"
            :high="true"
            mode="contain"
            :max-img-size="2000"
          />
        </div>
        <div class="cropper-actions">
          <el-button-group>
            <el-button @click="rotateLeft" :icon="RefreshLeft" />
            <el-button @click="rotateRight" :icon="RefreshRight" />
            <el-button @click="zoomIn" :icon="ZoomIn" />
            <el-button @click="zoomOut" :icon="ZoomOut" />
          </el-button-group>
          <el-button @click="clearImage">重新选择</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button
            type="primary"
            @click="uploadImage"
            :loading="isUploading"
            :disabled="!imageUrl"
        >
          上传头像
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Upload, RefreshLeft, RefreshRight, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { VueCropper } from 'vue-cropper'
import 'vue-cropper/dist/index.css'
import apiClient from '@/api'

const props = defineProps<{
  visible: boolean
  targetUserId?: number | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': []
}>()

const cropperRef = ref<InstanceType<typeof VueCropper>>()
const imageUrl = ref('')
const isUploading = ref(false)

const handleFileChange = (uploadFile: any) => {
  const file = uploadFile.raw as File
  if (!file) return

  // 验证文件类型
  const validTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!validTypes.includes(file.type)) {
    ElMessage.error('请选择有效的图片文件')
    return
  }

  // 验证文件大小 (最大 5MB)
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 5MB')
    return
  }

  // 读取文件为 base64
  const reader = new FileReader()
  reader.onload = (e) => {
    imageUrl.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
}

const clearImage = () => {
  imageUrl.value = ''
}

// 裁剪器操作
const rotateLeft = () => {
  cropperRef.value?.rotateLeft()
}

const rotateRight = () => {
  cropperRef.value?.rotateRight()
}

const zoomIn = () => {
  cropperRef.value?.changeScale(1)
}

const zoomOut = () => {
  cropperRef.value?.changeScale(-1)
}

const uploadImage = async () => {
  if (!imageUrl.value || !cropperRef.value) return

  isUploading.value = true

  try {
    // 获取裁剪后的图片 blob
    const blob = await new Promise<Blob>((resolve, reject) => {
      cropperRef.value?.getCropBlob((blob: Blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error('裁剪失败'))
        }
      })
    })

    const formData = new FormData()
    formData.append('file', blob, 'avatar.png')

    const url = (props.targetUserId != null)
      ? `/api/users/${props.targetUserId}/avatar`
      : '/api/users/me/avatar'

    await apiClient.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    ElMessage.success('头像上传成功')
    emit('success')
    emit('update:visible', false)
  } catch (error: any) {
    console.error('Avatar upload failed:', error)
    ElMessage.error(error.response?.data?.detail || '上传失败，请稍后再试')
  } finally {
    isUploading.value = false
  }
}

const reset = () => {
  clearImage()
}

watch(() => props.visible, (newVal) => {
  if (!newVal) {
    reset()
  }
})
</script>

<style scoped>
.avatar-uploader-container {
  min-height: 300px;
}

.upload-area {
  display: flex;
  justify-content: center;
}

.avatar-upload {
  width: 100%;
}

.avatar-upload :deep(.el-upload-dragger) {
  width: 100%;
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.upload-icon {
  font-size: 48px;
  color: var(--el-text-color-secondary);
  margin-bottom: 16px;
}

.upload-text {
  text-align: center;
}

.upload-text p {
  margin: 0;
  color: var(--el-text-color-regular);
}

.upload-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 8px !important;
}

.cropper-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.cropper-wrapper {
  width: 100%;
  height: 300px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-fill-color-darker);
}

.cropper-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
