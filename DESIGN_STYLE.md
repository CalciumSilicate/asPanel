# AS Panel 设计语言审美模板

> 用途：作为 UI 提示词参考，复刻此风格时粘贴此文档相关段落即可。

---

## 一、整体风格关键词

**玻璃态极光科技风（Glassmorphism × Aurora × Neomorphic Glow）**

- 半透明磨砂玻璃面板，背景动态光球氛围光
- 品牌蓝 × 粉调渐变，深/浅双主题无缝切换
- 弹簧物理动效（spring curve）贯穿全局
- 骨架屏 shimmer → 内容模糊弹入的两阶段加载动画

---

## 二、色彩系统

### 品牌色

| 变量 | 值 | 用途 |
|---|---|---|
| `--brand-primary` | `#77B5FE` | 主蓝，按钮 / 激活态 / 辉光 |
| `--brand-accent` | `#EFB7BA` | 粉，装饰渐变 / 滚动条 |
| `--brand-soft` | `#E5C0C8` | 柔和粉，背景光球 |
| `--brand-sky` | `#A6C8F0` | 浅蓝，右上角光晕 |

### 浅色主题表面

```
背景：#FAFAFB
卡片：#FFFFFF
次级面：#F7F8FA
描边：#E9EDF3
主文字：#1F2937
次文字：#6B7280
```

### 深色主题表面

```
背景：#080e1a
卡片：#0f1729
次级面：#0a1020
描边：#1e2d42
主文字：#e2e8f0
次文字：#94a3b8
```

### 统计卡片色组（亮色 / 暗色）

```
服务器：#e7f6f6 / rgba(64,201,198,0.12)   图标色 #40c9c6
CPU：   #eaf3fe / rgba(54,163,247,0.12)   图标色 #36a3f7
内存：  #fef5f5 / rgba(244,81,108,0.12)   图标色 #f4516c
磁盘：  #f3eefc / rgba(149,117,205,0.12)  图标色 #9575cd
```

---

## 三、玻璃卡片（Glass Card）配方

### 浅色

```css
background: rgba(255, 255, 255, 0.62);
backdrop-filter: saturate(160%) blur(18px);
border: 1px solid rgba(119, 181, 254, 0.18);
border-radius: 20px;
box-shadow:
  0 4px 24px rgba(119, 181, 254, 0.10),
  0 1px 0 rgba(255,255,255,0.9) inset;
```

### 深色

```css
background: rgba(15, 23, 42, 0.55);
backdrop-filter: saturate(160%) blur(18px);
border: 1px solid rgba(119, 181, 254, 0.12);
border-radius: 20px;
box-shadow:
  0 4px 32px rgba(0,0,0,0.45),
  0 0 0 1px rgba(119,181,254,0.08) inset;
```

### 顶部彩虹 shimmer 装饰线（`.shimmer-line`）

```css
/* 卡片内顶部第一行：绝对定位 1px 高渐变线 */
position: absolute; top: 0; left: 0; right: 0; height: 1px;
background: linear-gradient(
  90deg,
  transparent 0%,
  rgba(119,181,254,0.5) 30%,
  rgba(239,183,186,0.45) 65%,
  transparent 100%
);
```

---

## 四、顶栏（App Header）

```css
background: rgba(255,255,255,0.75);  /* 深色: rgba(10,16,28,0.80) */
backdrop-filter: saturate(180%) blur(12px);
border-bottom: 1px solid var(--color-border);
height: 64px;
/* 底部彩线：同 shimmer-line 配方，横跨全宽 */
```

---

## 五、侧边栏（Sidebar）

```css
/* 亮色 */
background: rgba(255,255,255,0.42);
backdrop-filter: saturate(160%) blur(16px);
box-shadow: 1px 0 0 rgba(119,181,254,0.18), 4px 0 20px rgba(119,181,254,0.06);

/* 深色 */
background: rgba(15,23,42,0.55);
box-shadow: 1px 0 0 rgba(119,181,254,0.12), 4px 0 24px rgba(0,0,0,0.35);

/* 右侧动态辉光分割线（8s 呼吸动画，蓝→粉渐变） */
```

菜单激活态：

```css
color: #77B5FE;
background: linear-gradient(90deg, rgba(119,181,254,0.18), rgba(119,181,254,0.06));
box-shadow: 0 0 0 1px rgba(119,181,254,0.25), inset 3px 0 0 #77B5FE, 0 4px 16px rgba(119,181,254,0.20);
border-radius: 10px;
/* 图标：drop-shadow 脉冲辉光，3s infinite */
```

---

## 六、动效系统

### Easing 曲线

| 名称 | 值 | 场景 |
|---|---|---|
| 弹簧（spring） | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 卡片入场 / 按钮 hover / 菜单项 |
| 标准缓出 | `cubic-bezier(0.22, 0.61, 0.36, 1)` | 侧边栏宽度过渡 |
| 快速 | `0.18s ease` | hover 背景色 / 描边 |

### 页面路由切换

```css
/* 入场：模糊焦入 + 上移 + 缩放 */
enter: opacity 0→1, translateY(10px)→0, scale(0.99)→1, blur(4px)→0  /  0.22s
/* 离场：模糊焦出 + 上飘 */
leave: opacity 1→0, translateY(0)→-6px, scale(1)→1.005, blur(0)→3px  /  0.18s
```

### 内容分块入场（db-rise）

```css
/* 各块错开 160ms，弹簧 0.72s */
@keyframes db-rise {
  from { opacity:0; transform:translateY(36px) scale(0.95); filter:blur(10px); }
  60%  { filter:blur(0); }
  to   { opacity:1; transform:translateY(0) scale(1); }
}
animation: db-rise 0.72s cubic-bezier(0.34,1.56,0.64,1) both;
animation-delay: 0ms / 160ms / 320ms;  /* 每块递增 */
```

### 骨架屏离场

```css
transition: opacity 0.42s ease, transform 0.42s ease, filter 0.42s ease;
leave-to: opacity:0; transform:translateY(-14px) scale(0.98); filter:blur(6px);
```

### Shimmer 扫光

```css
/* 亮色 */
background: linear-gradient(90deg,
  rgba(128,128,128,0.08) 25%,
  rgba(128,128,128,0.18) 50%,
  rgba(128,128,128,0.08) 75%);
background-size: 800px 100%;
animation: shimmer-move 1.5s linear infinite;

/* 深色 */
rgba(255,255,255,0.04) → rgba(255,255,255,0.10) → rgba(255,255,255,0.04)
```

---

## 七、对话框（Dialog）结构模板

```
┌─ dlg-head ──────────────────────────────────┐
│  [dlg-icon: 彩色图标圆角方块]                │
│  [dlg-title-group: 标题 / 副标题两行]        │
│  [dlg-close-btn: 右上角 × 按钮]             │
└──────────────────────────────────────────────┘
   ↓ el-form / 正文内容
┌─ dlg-footer ────────────────────────────────┐
│  [dlg-btn-ghost]  取消    [dlg-btn-primary] 确认  │
└──────────────────────────────────────────────┘
```

图标色块配方（`dlg-icon`）：

```css
width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center;
/* create:  */ background:rgba(119,181,254,0.12); color:#77B5FE;
/* import:  */ background:rgba(64,201,198,0.12);  color:#40c9c6;
/* danger:  */ background:rgba(244,81,108,0.12);  color:#f4516c;
/* rename:  */ background:rgba(149,117,205,0.12); color:#9575cd;
/* cmd:     */ background:rgba(239,183,186,0.12); color:#EFB7BA;
```

按钮配方：

```css
/* Ghost */
border:1px solid rgba(119,181,254,0.25); border-radius:10px; color:var(--color-text-secondary);
background:rgba(128,128,128,0.06); height:36px; padding:0 16px;

/* Primary */
background:linear-gradient(135deg, #77B5FE, #a78bfa);
border:none; border-radius:10px; color:#fff; height:36px;
box-shadow: 0 4px 16px rgba(119,181,254,0.40);
/* hover: translateY(-1px) scale(1.02), 加强阴影 */
/* active: scale(0.97), 减弱阴影 */

/* Danger */
background:linear-gradient(135deg, #f4516c, #e05252);
box-shadow: 0 4px 14px rgba(244,81,108,0.35);
```

对话框本体（浅色 / 深色）：

```css
/* 浅色 */
background: rgba(255,255,255,0.88);
backdrop-filter: saturate(180%) blur(20px);
border: 1px solid rgba(119,181,254,0.20);
border-radius: 20px;
box-shadow: 0 20px 60px rgba(119,181,254,0.18), 0 4px 16px rgba(0,0,0,0.06);

/* 深色 */
background: rgba(8,14,26,0.92);
border: 1px solid rgba(119,181,254,0.14);
box-shadow: 0 28px 80px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.04);
/* 头部：渐变蓝→紫→粉 linear-gradient(135deg, ...) */
```

---

## 八、背景氛围光球（Orbs）

4 个绝对定位 `<span>` 光球，`pointer-events:none`，`z-index:-1`：

```
orb-1（左上）: 500px, rgba(119,181,254,0.18), blur(120px), 20s float
orb-2（右上）: 420px, rgba(239,183,186,0.15), blur(100px), 25s float 反向
orb-3（左下）: 380px, rgba(166,200,240,0.12), blur(90px),  30s float
orb-4（右中）: 320px, rgba(229,192,200,0.10), blur(80px),  22s float
```

动画：缓慢漂移 `translateX/Y ±20~40px`，`ease-in-out infinite alternate`

---

## 九、原生表格风格（`.native-table`）

```css
width:100%; border-collapse:collapse; table-layout:fixed;
thead: 背景 rgba(119,181,254,0.05~0.08)，字体 11px uppercase letter-spacing 0.05em，text-secondary色
tbody tr: 悬浮时 rgba(119,181,254,0.04~0.06)，left border 3px solid transparent → brand-primary
border-bottom: 1px solid var(--color-border) 行分割线
```

---

## 十、字体

```
UI 字体：'Lexend', -apple-system, 'Segoe UI', 'Noto Sans', sans-serif
代码字体：'Maple Mono', ui-monospace, monospace
font-smoothing: antialiased + optimizeLegibility
```

---

## 十一、圆角 & 阴影速查

```
小圆角：8px    （输入框、标签 Tag=999px）
中圆角：12px   （图标块、菜单项）
大圆角：16~20px（卡片、对话框）

shadow-sm: 0 2px 8px rgba(119,181,254,0.08)
shadow-md: 0 12px 32px rgba(119,181,254,0.12)
（深色 sm: 0 2px 8px rgba(0,0,0,0.35) / md: 0 12px 40px rgba(0,0,0,0.55)）
```

---

## 十二、一句话总结（作 prompt 核心词）

> **Glassmorphism admin dashboard · brand blue `#77B5FE` × blush pink `#EFB7BA` · frosted glass cards with iridescent shimmer top-line · spring-bounce micro-animations · aurora orb backgrounds · dual light/dark theme · Lexend UI font · Element Plus component library · Vue 3**

---

## 十三、暗色模式扩展（Night Aurora）

> 目标：不是简单“把背景变黑”，而是构建一套更克制、更通透、更有纵深的夜间控制台视觉系统。

### 暗色气质关键词

- 深海蓝黑基底，不用纯黑，避免界面发闷和细节吞没
- 面板像悬浮在夜空中的玻璃舱，边缘有冷色内发光
- 蓝色承担结构与交互反馈，粉色只做点缀，不喧宾夺主
- 高亮靠层次和雾感，不靠高饱和大面积铺色
- 内容区优先可读性，装饰光效只出现在边缘、背景与 hover 态

### 推荐暗色 Token

```css
:root.dark {
  --color-bg-app: #06101f;
  --color-bg-elevated: #0a1426;
  --color-bg-panel: rgba(10, 18, 32, 0.78);
  --color-bg-panel-strong: rgba(13, 23, 40, 0.92);
  --color-bg-soft: rgba(119, 181, 254, 0.06);
  --color-border: rgba(148, 163, 184, 0.16);
  --color-border-strong: rgba(119, 181, 254, 0.22);
  --color-text: #e8eef8;
  --color-text-secondary: #9aa9bf;
  --color-text-tertiary: #6f8099;
  --color-glow-blue: rgba(119, 181, 254, 0.28);
  --color-glow-pink: rgba(239, 183, 186, 0.20);
  --color-success: #40c9c6;
  --color-warning: #f6c177;
  --color-danger: #f4516c;
}
```

### 暗色背景层次

```css
background:
  radial-gradient(circle at 12% 18%, rgba(119,181,254,0.16), transparent 28%),
  radial-gradient(circle at 88% 14%, rgba(239,183,186,0.12), transparent 24%),
  radial-gradient(circle at 52% 120%, rgba(166,200,240,0.10), transparent 30%),
  linear-gradient(180deg, #08101d 0%, #060c18 42%, #040814 100%);
color: var(--color-text);
```

建议：

- 页面主背景用渐变，不要单色 `#000`
- 内容容器再叠一层极淡的蓝雾 `rgba(119,181,254,0.03~0.05)`
- 最深层背景与卡片至少拉开 6~10% 的明度差

### 暗色卡片增强版

```css
background: linear-gradient(
  180deg,
  rgba(15, 24, 40, 0.82) 0%,
  rgba(10, 18, 32, 0.78) 100%
);
backdrop-filter: saturate(165%) blur(20px);
-webkit-backdrop-filter: saturate(165%) blur(20px);
border: 1px solid rgba(119, 181, 254, 0.14);
border-radius: 20px;
box-shadow:
  0 18px 48px rgba(0, 0, 0, 0.42),
  0 0 0 1px rgba(119,181,254,0.06) inset,
  0 1px 0 rgba(255,255,255,0.03) inset;
position: relative;
overflow: hidden;
```

卡片细节建议：

- 顶部保留 `shimmer-line`，但透明度降到亮色模式的 70~80%
- 卡片 hover 时只轻微提亮边框和阴影，不要整体变亮太多
- 关键卡片可额外加 1 层 `::before` 内部渐变雾光，位置偏左上

### Header / Sidebar 暗色专项

```css
/* Header */
background: rgba(6, 12, 24, 0.72);
backdrop-filter: saturate(180%) blur(14px);
border-bottom: 1px solid rgba(119,181,254,0.12);
box-shadow: 0 10px 30px rgba(0,0,0,0.18);

/* Sidebar */
background: linear-gradient(180deg, rgba(8,14,28,0.78), rgba(7,12,24,0.88));
backdrop-filter: saturate(160%) blur(18px);
border-right: 1px solid rgba(119,181,254,0.10);
box-shadow: inset -1px 0 0 rgba(255,255,255,0.03), 10px 0 30px rgba(0,0,0,0.18);
```

导航态建议：

- 默认态文字使用 `#8fa1ba`，hover 升到 `#dbe8ff`
- 激活态背景改为蓝雾渐变，不要太实：`rgba(119,181,254,0.18) → rgba(119,181,254,0.05)`
- 激活态左侧指示条可以保留，但宽度建议 `2px`，更精致
- 图标辉光只在当前项或重要入口出现，避免整列都在发光

### 表单与输入控件（暗色）

```css
background: rgba(255,255,255,0.03);
border: 1px solid rgba(148,163,184,0.14);
color: #e8eef8;
box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);

/* focus */
border-color: rgba(119,181,254,0.42);
box-shadow:
  0 0 0 3px rgba(119,181,254,0.12),
  inset 0 1px 0 rgba(255,255,255,0.04);
background: rgba(119,181,254,0.05);
```

规则：

- 输入框背景不要纯透明，否则会和复杂背景打架
- placeholder 文字建议使用 `rgba(154,169,191,0.72)`
- 错误态优先通过描边 + 柔光体现，不要整块红底

### 按钮系统（暗色）

```css
/* Primary */
background: linear-gradient(135deg, #77B5FE 0%, #8bc5ff 42%, #d7a6c8 100%);
color: #08101d;
box-shadow:
  0 10px 24px rgba(119,181,254,0.30),
  0 2px 8px rgba(239,183,186,0.16);

/* Secondary */
background: rgba(255,255,255,0.04);
border: 1px solid rgba(119,181,254,0.16);
color: #dce7f7;

/* Ghost */
background: transparent;
border: 1px solid rgba(148,163,184,0.16);
color: #9fb0c8;
```

交互建议：

- Primary hover 提亮渐变、上浮 `translateY(-1px)` 即可
- Secondary hover 强化边框与底色，不要出现大面积高亮底
- 危险按钮保持红色，但饱和度略收，避免破坏整体高级感

### 数据面板 / 图表建议

```css
图表底板：rgba(255,255,255,0.02)
网格线：rgba(148,163,184,0.10)
主折线：#7dc1ff
辅助折线：#efb7ba
面积渐变：rgba(119,181,254,0.20) → transparent
tooltip：rgba(8,14,26,0.92) + 1px blue border + 18px blur
```

规则：

- 图表线条比亮色模式略亮一点，确保在深底上清晰可见
- 坐标轴与网格线要足够淡，让视觉重心留给数据
- 同屏图表不超过 2 个高饱和强调色

### 暗色模式动效微调

- 暗色模式的入场动画比亮色略慢 `20~40ms`，更沉稳
- 模糊值可以比亮色稍高，营造空气感，但总时长不宜拖沓
- 发光动画使用低频呼吸，避免高频闪烁造成疲劳
- hover 动效优先位移和描边变化，少用大面积亮度跳变

### 可读性与对比度规则

- 正文文字与背景对比至少维持在接近 `WCAG AA` 的舒适区
- 次级文字不要低于 `#8fa1ba` 一档，否则仪表盘信息容易发灰
- 1px 描边在暗色里极重要，是区分层级的关键，不要省略
- 粉色只用作强调和柔化氛围，主操作反馈仍以蓝色为核心

### 暗色模式 Prompt 模板

> **Dark glassmorphism admin dashboard · deep ocean night background · frosted navy panels with subtle blue inner glow · brand blue `#77B5FE` as primary interaction color and blush pink `#EFB7BA` as soft accent · layered aurora orbs and mist gradients · elegant low-contrast borders · spring-based hover and route transitions · premium, calm, futuristic, readable night UI**

---

## 十四、现有页面组件落地规范（基于当前实现）

> 适用参考：`frontend/src/views/server-list/ServerTableView.vue`、`frontend/src/views/ModsManager.vue`、`frontend/src/views/plugin-config/components/ConfigServerPicker.vue`

这一组页面已经把「玻璃态极光科技风」落成了更具体的交互范式，可直接视为后台列表类页面的组件规范补充。

### 1. 列表页容器层级

- 页面主容器优先使用纵向 `flex` 布局，区块间距控制在 `14px` 左右，内容区高度通过 `calc(100vh - header - offset)` 锁定，避免仪表盘滚动层级混乱。
- 无数据选中态或空态容器使用独立玻璃卡片承载，宽度不宜过宽，推荐 `max-width: 520px`，让注意力集中在下一步操作。
- 已选中详情态使用完整高度的 `glass card` 包裹表格与说明区，容器必须 `overflow: hidden`，保证顶部 shimmer 装饰线和 sticky header 不破边。
- 浅色容器建议使用 `rgba(255,255,255,0.58~0.62)`，深色容器建议使用 `rgba(15,23,42,0.65)` 左右，并保留 `blur(20px)` 与 1px 品牌色描边。

### 2. 原生表格增强规范

#### 表头

- 表头使用 `position: sticky; top: 0; z-index: 10;`，形成悬浮分层感。
- 亮色表头背景使用接近 `rgba(248,250,255,0.95~0.96)` 的半透明白雾；深色表头使用 `rgba(11,17,32,0.95)` 或 `rgba(15,23,42,0.96)`。
- 表头文字统一采用 `11px`、`700`、`0.06em` 字距、`uppercase` 的信息密度风格，透明度控制在 `0.72` 左右，保持“后台原生表格”气质。
- 可排序表头在 hover 时仅高亮文字与箭头，不要出现大面积背景填充；箭头默认隐藏，hover 半显，激活时使用品牌蓝。

#### 行与单元格

- 行分隔线保持极轻，蓝系表格用 `rgba(119,181,254,0.07)`，粉紫系表格用 `rgba(167,139,250,0.07)`。
- hover 态只加轻雾底色：蓝系 `rgba(119,181,254,0.05)`，粉紫系 `rgba(167,139,250,0.05)`，避免过于传统的数据表高亮。
- 单元格纵向内边距建议 `12~13px`，横向 `12px`，让玻璃面板内的内容更透气。
- 空状态区域保留大留白，推荐 `48px` 上下 padding，并继续使用 `el-empty`，不要塞入额外说明块破坏节奏。

#### 入场动效

- 表格行入场不是整体 fade，而是逐行错峰 `row-rise` / `db-rise` 风格：`translateY(10px→0)` + spring 曲线。
- 行级延迟建议按索引乘以 `30ms~40ms`，并设置上限，避免超长列表动画拖沓。

### 3. 状态、类型与数据标签

#### 服务器列表状态体系

- 服务器名称前使用 7px 彩色状态点，颜色直接映射服务端类型：`vanilla/beta18` 蓝、`fabric` 青、`forge` 橙、`velocity` 紫、未知灰。
- 状态标签统一用胶囊 pill，内边距约 `3px 10px`，字重 `700`，状态色仅体现在边框 / 文字 / 轻底色。
- `running` 与 `pending` 状态搭配 5px 圆点呼吸动画；静态状态保留低透明实点，避免所有状态都闪烁。
- `row-running` 可增加 3px 左侧 inset 高亮条，但透明度要克制，只提示“活跃”，不抢主视线。

#### 类型与数值标签

- 类型 chip 继续使用圆角 `999px` 的小胶囊，并按类型给出独立浅底色与描边，不建议回退到统一灰标签。
- 端口、版本、空间这类系统信息要有“控制台数据感”：推荐等宽或接近等宽的字体风格、偏小字号、紧凑留白。
- 端口标签可以单独做成微型码牌：品牌蓝文字 + 轻蓝底 + 1px 描边 + `6px` 圆角。
- 模组列表中的下载量、关注量等统计字段，适合继续使用 `stat-chip` 形式，而不是裸文本数字。

### 4. 操作区按钮规范

- 行内高频操作采用 `action-group` 胶囊容器分组，背景为极淡品牌色雾层，外加 1px 描边，整体圆角 `10px`。
- 单个图标按钮尺寸可收敛在 `26px × 26px`，圆角 `7px`，默认透明背景，仅在 hover 时放大到约 `scale(1.08~1.12)`。
- 启动、停止、重启、配置、更多等操作通过 hover 色区分语义，不在默认态就大量上色。
- 文本按钮版本用于模组管理这类需要明确动作含义的场景：高度约 `28px`，水平 padding `10px`，保留轻量玻璃边框。
- 危险动作保持红色系，但建议只在 hover 或 danger 按钮上表达，不整行铺满警示色。
- 禁用态透明度可降到 `0.28~0.35`，并同时去掉位移动效，保持明确但不刺眼。

### 5. 选择器与安装器面板规范

#### 顶部信息条

- Picker 顶部使用固定区域承载图标、标题、安装统计与搜索框，底部用 1px 品牌色描边分隔。
- 小图标块推荐 `28px` 方形 + `8px` 圆角，使用品牌渐变填充，形成组件识别锚点。
- 标题采用 `14px / 700`，统计信息降到 `11px` 次级文字，保证层级清晰。

#### 搜索框

- 搜索框外壳采用半透明玻璃输入风格：亮色 `rgba(255,255,255,0.55)`，深色 `rgba(15,23,42,0.55)`。
- focus 时不要大范围发光，只需要边框提升到 `rgba(119,181,254,0.60)`，外加 `0 0 0 3px rgba(119,181,254,0.10)` 柔焦环。
- 输入框圆角控制在 `10px`，避免过圆导致和列表项、按钮语言不一致。

#### 列表项

- Picker 列表项本质是“可点击卡片行”，hover 使用轻蓝雾背景并轻微 `translateX(2px)`，营造前进感。
- 激活项延续 hover 方案，但背景略增强；不支持项通过 `opacity` 降低并禁用交互，不需要额外深灰遮罩。
- 头像块推荐 `28px`，使用高识别度纯色或渐变色，并以首字母占位，形成快速扫描锚点。
- 已安装 / 不支持 / 可安装三种状态分别对应成功胶囊、灰色胶囊、渐变安装按钮，避免混用同一视觉组件。

### 6. 骨架屏与切换动画规范

- 骨架屏与真实内容共用同一 grid 区域叠放，便于做“shimmer 离场 → 内容弹入”的双阶段过渡。
- 骨架行推荐由 `avatar + line + chip` 组成，形状应尽量贴近真实布局，而不是通用矩形占位。
- shimmer 保持横向扫光，亮色用中性灰透明带，暗色改为低亮白雾带，持续时间约 `1.5s linear infinite`。
- 骨架离场时结合 `opacity + translateY(-8px) + blur(4px)`；真实内容入场时使用 `translateX(-12px)` 或 `translateY(10px)` 配合 spring 曲线。

### 7. Mod 管理页专项规范

- 模组管理页在“未选择服务器”与“已选择服务器”之间，用同一套玻璃容器语言切换，只改变布局密度，不改变视觉体系。
- 详情态卡片顶部可使用加厚版 `shimmer-line`，例如 `3px` 高的蓝紫渐变流光，作为模块级识别元素。
- Overview 区域适合作为表格前的信息条，内边距可控制在 `12px 16px`，底部加一条很淡的分隔线即可。
- 模组版本行中，“当前版本 tag + 可升级按钮”是推荐组合；版本过多的兼容标签应折叠为 `前两项 + +N tooltip`，不要把整列撑爆。
- 分页控件如果自绘，建议使用小型方圆按钮 + tabular 数字，保持与表格的精密感一致。

### 8. 推荐可复用 Token 补充

```css
/* Server table / picker / mods manager derived tokens */
--glass-panel-soft: rgba(255, 255, 255, 0.58);
--glass-panel-dark: rgba(15, 23, 42, 0.65);
--glass-border-blue: rgba(119, 181, 254, 0.12);
--glass-border-purple: rgba(167, 139, 250, 0.18);
--table-header-light: rgba(248, 250, 255, 0.96);
--table-header-dark: rgba(15, 23, 42, 0.96);
--row-hover-blue: rgba(119, 181, 254, 0.05);
--row-hover-purple: rgba(167, 139, 250, 0.05);
--row-divider-blue: rgba(119, 181, 254, 0.07);
--row-divider-purple: rgba(167, 139, 250, 0.07);
--focus-ring-blue: 0 0 0 3px rgba(119, 181, 254, 0.10);
--btn-disabled-opacity: 0.32;
```

### 9. 一句话追加总结

> **Frosted native data table · sticky translucent header · semantic status pills and type chips · grouped row actions · compact glass picker with shimmer skeleton · purple-blue accent for resource management views · spring-staggered row entrance**
