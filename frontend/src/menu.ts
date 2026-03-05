import {
  DataAnalysis, ChatDotRound, Tickets, Link, Management, Cpu, Shop, Coin,
  Grid, SetUp, Connection, Umbrella, Refresh, VideoPlay, LocationInformation,
  User, List, RefreshRight, Comment, DocumentCopy, MapLocation, Operation,
  Files, Promotion, Printer, VideoCamera, TrendCharts, Setting, UserFilled,
} from '@element-plus/icons-vue'
import type { LegacyRole } from '@/store/user'

export interface MenuLeaf {
  type: 'item'
  path: string
  label: string
  icon: unknown
  disabled?: boolean
  requiredRole?: LegacyRole
  requiresPlatformAdmin?: boolean
  requiresOwner?: boolean
}

export interface MenuGroup {
  type: 'group'
  key: string
  label: string
  icon: unknown
  requiredRole?: LegacyRole
  children: MenuLeaf[]
}

export type MenuEntry = MenuLeaf | MenuGroup

export const SIDEBAR_MENU: MenuEntry[] = [
  { type: 'item', path: '/dashboard',     label: '仪表盘',     icon: DataAnalysis,  requiredRole: 'GUEST' },
  { type: 'item', path: '/chat',          label: '聊天室',     icon: ChatDotRound,  requiredRole: 'USER'  },
  { type: 'item', path: '/servers',       label: '服务器列表', icon: Tickets,       requiredRole: 'USER'  },
  { type: 'item', path: '/server-groups', label: '服务器组列表', icon: Link,        requiresPlatformAdmin: true },
  {
    type: 'group', key: 'plugin-management', label: '插件管理', icon: Management, requiredRole: 'HELPER',
    children: [
      { type: 'item', path: '/server-plugins',      label: '服务器插件',   icon: Cpu,  requiredRole: 'HELPER' },
      { type: 'item', path: '/mcdr-plugin-explorer', label: '联网插件库',  icon: Shop, requiredRole: 'HELPER' },
      { type: 'item', path: '/db-plugin-manager',   label: '数据库插件库', icon: Coin, requiresPlatformAdmin: true },
    ],
  },
  { type: 'item', path: '/tools/mods-manager', label: 'Mods管理', icon: Grid, requiredRole: 'ADMIN' },
  {
    type: 'group', key: 'server-config', label: '插件配置', icon: SetUp, requiredRole: 'HELPER',
    children: [
      { type: 'item', path: '/server-config/via-version-config',         label: 'Via Version',         icon: Connection,        requiredRole: 'ADMIN'  },
      { type: 'item', path: '/server-config/velocity-proxy-config',      label: 'Velocity Proxy',      icon: Link,              requiredRole: 'ADMIN'  },
      { type: 'item', path: '/server-config/prime-backup-config',        label: 'Prime Backup',        icon: Umbrella,          requiredRole: 'HELPER' },
      { type: 'item', path: '/server-config/auto-plugin-reloader-config',label: 'Auto Plugin Reloader',icon: Refresh,           requiredRole: 'HELPER' },
      { type: 'item', path: '/server-config/bili-live-helper-config',    label: 'Bili Live Helper',    icon: VideoPlay,         requiredRole: 'HELPER' },
      { type: 'item', path: '/server-config/where-is-config',            label: 'Where Is',            icon: LocationInformation,requiredRole: 'HELPER'},
      { type: 'item', path: '/server-config/bot-loader',                 label: 'Bot Loader',          icon: User,              requiredRole: 'ADMIN',  disabled: true },
      { type: 'item', path: '/server-config/command-set',                label: 'Command Set',         icon: List,              requiredRole: 'ADMIN',  disabled: true },
      { type: 'item', path: '/server-config/crash-restart-config',       label: 'Crash Restart',       icon: RefreshRight,      requiredRole: 'HELPER' },
      { type: 'item', path: '/server-config/join-motd-config',           label: 'joinMOTD',            icon: Comment,           requiredRole: 'ADMIN'  },
      { type: 'item', path: '/server-config/quick-backup-multi-config',  label: 'Quick Backup Multi',  icon: DocumentCopy,      requiredRole: 'HELPER' },
    ],
  },
  { type: 'item', path: '/tools/world-map', label: '世界地图', icon: MapLocation, requiredRole: 'USER' },
  {
    type: 'group', key: 'tools', label: '工具', icon: Operation, requiredRole: 'HELPER',
    children: [
      { type: 'item', path: '/tools/prime-backup',  label: 'Prime Backup', icon: Umbrella,    requiredRole: 'USER'  },
      { type: 'item', path: '/tools/archives',      label: '存档管理',     icon: Files,       requiredRole: 'HELPER'},
      { type: 'item', path: '/tools/superflat',     label: '超平坦世界',   icon: Grid,        requiredRole: 'USER'  },
      { type: 'item', path: '/tools/qq-bot',        label: 'QQ机器人',     icon: Promotion,   requiredRole: 'ADMIN', disabled: true },
      { type: 'item', path: '/tools/litematica',    label: 'Litematica',   icon: Printer,     requiredRole: 'USER'  },
      { type: 'item', path: '/tools/pcrc',          label: 'PCRC',         icon: VideoCamera, requiredRole: 'USER',  disabled: true },
    ],
  },
  { type: 'item', path: '/statistics', label: '数据统计',  icon: TrendCharts, requiredRole: 'USER'  },
  { type: 'item', path: '/players',    label: '玩家管理',  icon: User,        requiresPlatformAdmin: true },
  { type: 'item', path: '/users',      label: '用户管理',  icon: User,        requiresOwner: true },
  { type: 'item', path: '/settings',   label: '设置',      icon: Setting,     requiresOwner: true },
  { type: 'item', path: '/audit-log',  label: '审计日志',  icon: Tickets,     requiresPlatformAdmin: true },
  { type: 'item', path: '/profile',    label: '个人中心',  icon: UserFilled },
]
