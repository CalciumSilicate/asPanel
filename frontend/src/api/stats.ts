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
  server_id?: (string|number)[]
}): Promise<SeriesDict> {
  const q = buildQuery({
    player_uuid: args.player_uuid,
    metric: args.metric,
    granularity: args.granularity,
    start: args.start,
    end: args.end,
    namespace: args.namespace ?? 'minecraft',
    server_id: args.server_id?.map(String),
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
  server_id?: (string|number)[]
}): Promise<SeriesDict> {
  const q = buildQuery({
    player_uuid: args.player_uuid,
    metric: args.metric,
    granularity: args.granularity,
    start: args.start,
    end: args.end,
    namespace: args.namespace ?? 'minecraft',
    server_id: args.server_id?.map(String),
  })
  const res = await apiClient.get(`/api/stats/series/total?${q}`)
  return res.data || {}
}

export async function fetchMetrics(q: string, limit = 50, namespace = 'minecraft'): Promise<string[]> {
  const qs = buildQuery({ q, limit: String(limit), namespace })
  const res = await apiClient.get(`/api/stats/metrics?${qs}`)
  return res.data || []
}

export async function fetchLeaderboardTotal(args: {
  metric: string[]
  at?: string
  server_id?: (string|number)[]
  namespace?: string
  limit?: number
}) {
  const q = buildQuery({
    metric: args.metric,
    at: args.at,
    server_id: args.server_id?.map(String),
    namespace: args.namespace ?? 'minecraft',
    limit: args.limit != null ? String(args.limit) : undefined,
  })
  const res = await apiClient.get(`/api/stats/leaderboard/total?${q}`)
  return res.data || []
}

export async function fetchLeaderboardDelta(args: {
  metric: string[]
  start?: string
  end?: string
  server_id?: (string|number)[]
  namespace?: string
  limit?: number
}) {
  const q = buildQuery({
    metric: args.metric,
    start: args.start,
    end: args.end,
    server_id: args.server_id?.map(String),
    namespace: args.namespace ?? 'minecraft',
    limit: args.limit != null ? String(args.limit) : undefined,
  })
  const res = await apiClient.get(`/api/stats/leaderboard/delta?${q}`)
  return res.data || []
}
