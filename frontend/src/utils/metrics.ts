export const clampPercent = (n: number): number =>
  Math.min(100, Math.max(0, Number(n) || 0))

export const formatCpuPercent = (n: number): string =>
  `${clampPercent(n).toFixed(2)}%`

export const formatMemoryMb = (mb: number): string => {
  const n = Number(mb)
  if (!Number.isFinite(n)) return '--'
  return `${Math.round(n).toLocaleString()} MB`
}

export const getUsageStatus = (p: number): '' | 'success' | 'warning' | 'exception' => {
  const n = Number(p) || 0
  if (n >= 90) return 'exception'
  if (n >= 70) return 'warning'
  return 'success'
}
