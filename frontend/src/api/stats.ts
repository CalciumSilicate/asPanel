import apiClient from '@/api'

export interface SeriesDict {
  [uuid: string]: [number, number][]
}

function buildQuery(params: Record<string, string | string[] | undefined>) {
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v == null) return
    if (Array.isArray(v)) {
      v.forEach((vv) => usp.append(k, vv))
    } else {
      usp.append(k, v)
    }
  })
  return usp.toString()
}

export async function fetchDeltaSeries(args: {
  player_uuid: string[]
  metric: string[]
  granularity: string
  start?: string
  end?: string
  namespace?: string
}): Promise<SeriesDict> {
  const q = buildQuery({
    player_uuid: args.player_uuid,
    metric: args.metric,
    granularity: args.granularity,
    start: args.start,
    end: args.end,
    namespace: args.namespace ?? 'minecraft',
  })
  const res = await apiClient.get(`/api/stats/series/delta?${q}`)
  return res.data || {}
}

export async function fetchTotalSeries(args: {
  player_uuid: string[]
  metric: string[]
  granularity: string
  start?: string
  end?: string
  namespace?: string
}): Promise<SeriesDict> {
  const q = buildQuery({
    player_uuid: args.player_uuid,
    metric: args.metric,
    granularity: args.granularity,
    start: args.start,
    end: args.end,
    namespace: args.namespace ?? 'minecraft',
  })
  const res = await apiClient.get(`/api/stats/series/total?${q}`)
  return res.data || {}
}

