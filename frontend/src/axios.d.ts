import 'axios'

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    skipGroupContext?: boolean
    cancelOnRouteChange?: boolean
    __routeCancelController?: AbortController
  }
}
