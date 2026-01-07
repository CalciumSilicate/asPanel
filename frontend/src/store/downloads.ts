// frontend/src/store/downloads.ts
// 重新导出 transfers.ts 以保持向后兼容

export {
  downloads,
  downloadArchive,
  clearFinishedDownloads,
  cancelDownload,
  clearDownload,
  startDownload,
  activeDownloadsCount,
  hasActiveTransfers,
  setupBeforeUnloadWarning,
  removeBeforeUnloadWarning,
  finishedTransfersCount as finishedDownloadsCount,
} from './transfers'

export type { DownloadOptions, TransferItem as DownloadItem, TransferStatus as DownloadStatus } from './transfers'

// 旧的 ArchiveDownloadSource 类型兼容
export interface ArchiveDownloadSource {
  id: number | string
  name: string
  type?: string | null
}
