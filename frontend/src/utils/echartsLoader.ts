let _promise: Promise<any> | null = null

export function loadECharts(): Promise<any> {
  if (typeof window !== 'undefined' && (window as any).echarts) {
    return Promise.resolve((window as any).echarts)
  }
  if (_promise) return _promise
  _promise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js'
    script.async = true
    script.onload = () => resolve((window as any).echarts)
    script.onerror = (e) => reject(e)
    document.head.appendChild(script)
  })
  return _promise
}

