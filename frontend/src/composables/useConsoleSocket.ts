import { ref } from 'vue'
import { io, type Socket } from 'socket.io-client'

const MAX_LOG_LINES = 2000

export function useConsoleSocket(serverId: string, user: { id: number | null; username: string }) {
  const logs = ref<string[]>([])
  const isConnected = ref(false)
  const serverName = ref('加载中...')
  const serverStatus = ref<string>('loading')

  let socket: Socket | null = null

  const trimLogs = () => {
    const extra = logs.value.length - MAX_LOG_LINES
    if (extra > 0) logs.value.splice(0, extra)
  }

  const appendLog = (line: string) => {
    logs.value.push(line)
    trimLogs()
  }

  const connect = () => {
    socket = io({ path: '/ws/socket.io' })

    socket.on('connect', () => {
      isConnected.value = true
      socket!.emit('join_console_room', {
        server_id: parseInt(serverId, 10),
        user: { id: user.id, username: user.username },
      })
      appendLog('--- [系统] 已连接到服务器控制台，开始接收实时日志 ---')
    })

    socket.on('console_log_batch', (data) => {
      if (data && Array.isArray(data.logs) && data.logs.length > 0) {
        logs.value.push(...data.logs)
        trimLogs()
      }
    })

    socket.on('server_status_update', (serverDetails) => {
      if (serverDetails && serverDetails.id == serverId) {
        serverStatus.value = serverDetails.status
        serverName.value = serverDetails.name
      }
    })

    socket.on('server_delete', (serverDetails) => {
      if (serverDetails && serverDetails.id == serverId) {
        appendLog('--- [系统] 服务器已被删除，请退出该页面 ---')
      }
    })

    socket.on('disconnect', () => {
      isConnected.value = false
      appendLog('--- [系统] 已从服务器断开连接 ---')
    })

    socket.on('connect_error', (error) => {
      appendLog(`--- [系统] 连接错误: ${error.message} ---`)
    })
  }

  const sendCommand = (lines: string[]) => {
    if (!socket || !isConnected.value) return
    lines.forEach(line => {
      socket!.emit('console_command', {
        server_id: parseInt(serverId, 10),
        command: line,
      })
    })
  }

  const disconnect = () => {
    if (!socket) return
    if (isConnected.value) {
      socket.emit('leave_console_room', { server_id: parseInt(serverId, 10) })
    }
    socket.off('connect')
    socket.off('console_log_batch')
    socket.off('server_status_update')
    socket.off('server_delete')
    socket.off('disconnect')
    socket.off('connect_error')
    socket.disconnect()
    socket = null
  }

  return { logs, isConnected, serverName, serverStatus, appendLog, connect, disconnect, sendCommand }
}
