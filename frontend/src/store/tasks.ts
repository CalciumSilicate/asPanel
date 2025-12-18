import { computed, reactive } from 'vue'
import apiClient from '@/api'
import { io, Socket } from 'socket.io-client'

export type TaskStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'

export interface Task {
  id: string
  ids?: string[] | null
  name?: string | null
  status: TaskStatus
  progress: number
  message?: string | null
  error?: string | null
  type?: string | null
  created_at?: number | null
  total?: number | null
  done?: number | null
}

export type TaskEventAction = 'created' | 'updated' | 'finished' | 'deleted'

export interface TaskEvent {
  action: TaskEventAction
  task: Partial<Task> & { id: string }
}

const state = reactive({
  tasks: [] as Task[],
  connected: false,
})

let socket: Socket | null = null
const listeners = new Set<(event: TaskEvent) => void>()

const emitEvent = (event: TaskEvent) => {
  listeners.forEach((fn) => {
    try {
      fn(event)
    } catch (e) {
      console.error('task event handler error:', e)
    }
  })
}

const normalizeTask = (raw: any): Task => {
  return {
    id: String(raw?.id ?? ''),
    ids: Array.isArray(raw?.ids) ? raw.ids.map((x: any) => String(x)) : null,
    name: raw?.name ?? null,
    status: (raw?.status ?? 'PENDING') as TaskStatus,
    progress: Number(raw?.progress ?? 0),
    message: raw?.message ?? null,
    error: raw?.error ?? null,
    type: raw?.type ?? null,
    created_at: raw?.created_at != null ? Number(raw.created_at) : null,
    total: raw?.total != null ? Number(raw.total) : null,
    done: raw?.done != null ? Number(raw.done) : null,
  }
}

const upsertTask = (task: Task) => {
  const idx = state.tasks.findIndex((t) => t.id === task.id)
  if (idx === -1) {
    state.tasks.unshift(task)
  } else {
    state.tasks[idx] = { ...state.tasks[idx], ...task }
  }
  state.tasks.sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0))
}

const removeTask = (taskId: string) => {
  const idx = state.tasks.findIndex((t) => t.id === taskId)
  if (idx !== -1) state.tasks.splice(idx, 1)
}

export const tasks = computed(() => state.tasks)
export const activeTasksCount = computed(
  () => state.tasks.filter((t) => t.status === 'PENDING' || t.status === 'RUNNING').length
)
export const failedTasksCount = computed(() => state.tasks.filter((t) => t.status === 'FAILED').length)
export const successTasksCount = computed(() => state.tasks.filter((t) => t.status === 'SUCCESS').length)

export const fetchTasks = async () => {
  const { data } = await apiClient.get('/api/system/tasks')
  if (Array.isArray(data)) {
    state.tasks = data.map(normalizeTask).sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0))
  } else {
    state.tasks = []
  }
}

export const connectTasksSocket = () => {
  if (socket) return

  socket = io({ path: '/ws/socket.io' })

  socket.on('connect', () => {
    state.connected = true
  })
  socket.on('disconnect', () => {
    state.connected = false
  })
  socket.on('connect_error', (err) => {
    console.error('tasks socket connect_error:', err)
  })

  socket.on('task_update', (payload: any) => {
    const action = String(payload?.action ?? 'updated') as TaskEventAction
    const rawTask = payload?.task ?? {}
    const id = rawTask?.id != null ? String(rawTask.id) : ''
    if (!id) return

    if (action === 'deleted') {
      removeTask(id)
      emitEvent({ action, task: { id } })
      return
    }

    const task = normalizeTask(rawTask)
    upsertTask(task)
    emitEvent({ action, task })
  })
}

export const disconnectTasksSocket = () => {
  if (!socket) return
  socket.disconnect()
  socket = null
  state.connected = false
}

export const onTaskEvent = (fn: (event: TaskEvent) => void) => {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export const clearTasks = async (status: 'FAILED' | 'SUCCESS') => {
  const { data } = await apiClient.post('/api/system/tasks/clear', { status })
  // 后端会通过 task_update(deleted) 推送最终删除；这里返回清理数量用于 UI 提示
  return Number(data?.cleared ?? 0)
}

