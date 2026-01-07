<template>
  <div class="litematica-page">
    <el-card shadow="never" class="mb-3">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-base font-medium">Litematic Printer</span>
            <el-tag type="success" size="small">投影总数：{{ items.length }}</el-tag>
          </div>
          <div class="flex items-center gap-2">
            <input ref="fileInputRef" type="file" accept=".litematic" multiple style="display:none" @change="handleFileChange" />
            <el-button-group>
              <el-button type="success" @click="triggerSelectFile">上传投影</el-button>
              <el-dropdown @command="handleBatch" trigger="click" class="batch-dropdown">
                <el-button type="primary" class="batch-action-btn" :disabled="multipleSelection.length === 0">
                  批量操作 (已选 {{ multipleSelection.length }} 项)
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="copy">复制命令</el-dropdown-item>
                    <el-dropdown-item command="gen">生成命令</el-dropdown-item>
                    <el-dropdown-item command="delcl">删除命令</el-dropdown-item>
                    <el-dropdown-item command="delltm">删除投影</el-dropdown-item>
                    <el-dropdown-item command="dl_ltm">下载投影</el-dropdown-item>
                    <el-dropdown-item command="dl_cl">下载命令</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button-group>
          </div>
        </div>
      </template>
      <div class="table-card">
        <el-table
          :data="pagedItems"
          stripe
          size="small"
          v-loading="loading"
          empty-text="暂无投影"
          row-key="file_name"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="48" fixed="left"/>
          <el-table-column label="文件名" min-width="240">
            <template #default="{ row }">
              <span class="file-name">{{ row.file_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="200">
            <template #default="{ row }">
              <span>{{ formatTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="复制/生成命令" width="160" fixed="right" align="right">
            <template #default="{ row }">
              <template v-if="!row.cl_generated">
                <el-button size="small" type="primary" :loading="row.loadingGen" @click="generateCL(row)">生成命令</el-button>
              </template>
              <template v-else>
                <el-button size="small" @click="copyCommand(row)">复制命令</el-button>
              </template>
            </template>
          </el-table-column>
          <el-table-column label="" width="140" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click">
                <el-button size="small">
                  更多操作
                  <el-icon class="el-icon--right">
                    <arrow-down/>
                  </el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="renameRow(row)">重命名</el-dropdown-item>
                    <el-dropdown-item
                        :disabled="!!row.loadingDel || !!row.loadingDelCL"
                        @click="row.cl_generated ? deleteCL(row) : deleteRow(row)"
                    >
                      {{ row.cl_generated ? '删除命令' : '删除投影' }}
                    </el-dropdown-item>
                    <el-dropdown-item @click="downloadLtm(row)">下载投影</el-dropdown-item>
                    <el-dropdown-item :disabled="!row.cl_generated" @click="downloadCL(row)">下载命令</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        
      </div>
      <div class="mt-2 flex items-center justify-end pagination-footer">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          :total="items.length"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>
  </div>
  
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import apiClient from '@/api'
import { ArrowDown } from '@element-plus/icons-vue'
import { fetchTasks } from '@/store/tasks'
import { startDownload, startUpload } from '@/store/transfers'

interface LtmRow {
  file_name: string
  created_at?: string | null
  cl_generated: boolean
  cl_file_path?: string | null
  loadingGen?: boolean
  loadingDel?: boolean
  loadingDelCL?: boolean
}

const items = ref<LtmRow[]>([])
const loading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const multipleSelection = ref<LtmRow[]>([])
const page = ref(1)
const pageSize = ref(20)
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return items.value.slice(start, start + pageSize.value)
})
const onSelectionChange = (rows: LtmRow[]) => { multipleSelection.value = rows }
const onPageChange = (p: number) => { page.value = p }
const onPageSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
}

const fetchList = async () => {
  loading.value = true
  try {
    const { data } = await apiClient.get('/api/tools/litematic/list')
    items.value = (data || []).map((x: any) => ({
      file_name: x.file_name,
      created_at: x.created_at,
      cl_generated: !!x.cl_generated,
      cl_file_path: x.cl_file_path || null,
    }))
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载投影列表失败')
  } finally {
    loading.value = false
  }
}

const formatTime = (iso?: string | null) => {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  } catch { return iso }
}

const triggerSelectFile = () => fileInputRef.value?.click()

const handleFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  if (fileInputRef.value) fileInputRef.value.value = ''
  
  for (const f of files) {
    const fd = new FormData()
    fd.append('file', f)
    
    startUpload({
      url: '/api/tools/litematic/upload',
      data: fd,
      title: f.name || '投影上传',
      filename: f.name,
    }).then(({ error }) => {
      if (error) {
        ElMessage.error(`${f.name} 上传失败: ${error}`)
      } else {
        ElMessage.success(`${f.name} 上传成功`)
        fetchTasks().catch(() => {})
        fetchList()
      }
    })
  }
}

const generateCL = async (row: LtmRow) => {
  row.loadingGen = true
  try {
    await apiClient.post(`/api/tools/litematic/generate_cl/${encodeURIComponent(row.file_name)}`)
    ElMessage.success('命令已生成')
    fetchTasks().catch(() => {})
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成失败')
  } finally { row.loadingGen = false }
}

const renameRow = async (row: LtmRow) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的文件名（需包含扩展名 .litematic）', '重命名', {
      inputValue: row.file_name,
      confirmButtonText: '确定', cancelButtonText: '取消'
    })
    const newName = (value || '').trim()
    if (!newName) return
    await apiClient.post(`/api/tools/litematic/rename/${encodeURIComponent(row.file_name)}/${encodeURIComponent(newName)}`)
    ElMessage.success('重命名成功')
    await fetchList()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '重命名失败')
  }
}

const deleteRow = async (row: LtmRow) => {
  try {
    await ElMessageBox.confirm(`确定要删除投影 “${row.file_name}” 吗？`, '删除确认', { type: 'warning' })
    row.loadingDel = true
    await apiClient.delete(`/api/tools/litematic/delete/${encodeURIComponent(row.file_name)}`)
    ElMessage.success('已删除')
    await fetchList()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally { row.loadingDel = false }
}

const downloadLtm = async (row: LtmRow) => {
  try {
    await startDownload({
      url: `/api/tools/litematic/download/${encodeURIComponent(row.file_name)}`,
      title: row.file_name,
      fallbackFilename: row.file_name,
    })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '下载失败')
  }
}

const downloadCL = async (row: LtmRow) => {
  try {
    const outName = `${(row.file_name || '').replace(/\.litematic$/i, '')}.mccl.txt`
    await startDownload({
      url: `/api/tools/litematic/download_cl/${encodeURIComponent(row.file_name)}`,
      title: outName,
      fallbackFilename: outName,
    })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '下载失败')
  }
}

const deleteCL = async (row: LtmRow) => {
  try {
    await ElMessageBox.confirm(`确定要删除 “${row.file_name}” 的命令清单吗？`, '删除确认', { type: 'warning' })
    row.loadingDelCL = true
    await apiClient.delete(`/api/tools/litematic/delete_cl/${encodeURIComponent(row.file_name)}`)
    ElMessage.success('已删除命令清单')
    await fetchList()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally { row.loadingDelCL = false }
}

const copyToClipboard = async (text: string, okMsg = '已复制') => {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      ElMessage.success(okMsg)
      return
    }
  } catch {}
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly','')
    textarea.style.position = 'absolute'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    if (ok) ElMessage.success(okMsg); else throw new Error('execCommand 失败')
  } catch (err) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const copyCommand = (row: LtmRow) => {
  const target = row.cl_file_path || `${(row.file_name || '').replace(/\.litematic$/i, '')}.mccl.txt`
  const content = `!!execute ~ ~ ~ ${target}`
  copyToClipboard(content, '命令已复制')
}

onMounted(fetchList)

// 批量操作
const doBatchGenerateCL = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  loading.value = true
  try {
    const tasks = targets.map(r => apiClient.post(`/api/tools/litematic/generate_cl/${encodeURIComponent(r.file_name)}`))
    const res = await Promise.allSettled(tasks)
    const ok = res.filter(r => r.status === 'fulfilled').length
    const fail = res.length - ok
    if (ok) ElMessage.success(`已生成 ${ok} 个${fail ? `，失败 ${fail} 个` : ''}`)
  } finally {
    loading.value = false
    await fetchList()
  }
}
const doBatchDeleteCL = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  try {
    await ElMessageBox.confirm(`确定删除所选 ${targets.length} 个命令清单吗？`, '确认', { type: 'warning' })
  } catch { return }
  loading.value = true
  try {
    const tasks = targets.map(r => apiClient.delete(`/api/tools/litematic/delete_cl/${encodeURIComponent(r.file_name)}`))
    const res = await Promise.allSettled(tasks)
    const ok = res.filter(r => r.status === 'fulfilled').length
    const fail = res.length - ok
    if (ok) ElMessage.success(`已删除 ${ok} 个命令清单${fail ? `，失败 ${fail} 个` : ''}`)
  } finally {
    loading.value = false
    await fetchList()
  }
}
const doBatchDeleteLtm = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  try {
    await ElMessageBox.confirm(`确定删除所选 ${targets.length} 个投影吗？`, '确认', { type: 'warning' })
  } catch { return }
  loading.value = true
  try {
    const tasks = targets.map(r => apiClient.delete(`/api/tools/litematic/delete/${encodeURIComponent(r.file_name)}`))
    const res = await Promise.allSettled(tasks)
    const ok = res.filter(r => r.status === 'fulfilled').length
    const fail = res.length - ok
    if (ok) ElMessage.success(`已删除 ${ok} 个投影${fail ? `，失败 ${fail} 个` : ''}`)
  } finally {
    loading.value = false
    await fetchList()
  }
}
const doBatchDownloadLtm = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  for (const r of targets) {
    try {
      await startDownload({
        url: `/api/tools/litematic/download/${encodeURIComponent(r.file_name)}`,
        title: r.file_name,
        fallbackFilename: r.file_name,
      })
    } catch {}
  }
}
const doBatchDownloadCL = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  for (const r of targets) {
    try {
      const outName = `${(r.file_name || '').replace(/\.litematic$/i, '')}.mccl.txt`
      await startDownload({
        url: `/api/tools/litematic/download_cl/${encodeURIComponent(r.file_name)}`,
        title: outName,
        fallbackFilename: outName,
      })
    } catch {}
  }
}
const doBatchCopy = async () => {
  const targets = multipleSelection.value
  if (!targets.length) return ElMessage.warning('请先选择投影')
  const lines = targets.map(r => `!!execute ~ ~ ~ ${(r.cl_file_path || `${(r.file_name || '').replace(/\.litematic$/i, '')}.mccl.txt`)}`)
  await copyToClipboard(lines.join('\n'), '命令已复制')
}

const handleBatch = async (cmd: string) => {
  switch (cmd) {
    case 'copy':
      await doBatchCopy();
      break;
    case 'gen':
      await doBatchGenerateCL();
      break;
    case 'delcl':
      await doBatchDeleteCL();
      break;
    case 'delltm':
      await doBatchDeleteLtm();
      break;
    case 'dl_ltm':
      await doBatchDownloadLtm();
      break;
    case 'dl_cl':
      await doBatchDownloadCL();
      break;
  }
}
</script>

<style scoped>
.litematica-page { padding: 12px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.gap-2 { gap: 8px; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 500; }
.mb-3 { margin-bottom: 12px; }
.mt-2 { margin-top: 8px; }
.table-card { border-radius: 8px; overflow: hidden; }
.file-name { font-weight: 500; }
</style>
