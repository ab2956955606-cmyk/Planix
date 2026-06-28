<p align="center">
  <a href="#-中文版">🇨🇳 中文版</a> &nbsp;·&nbsp; <a href="#-english">🇬🇧 English</a>
</p>

---

<h1 align="center">📝 我的笔记 — MyNotes</h1>

<p align="center">
  <img src="https://img.shields.io/badge/status-active-brightgreen" />
  <img src="https://img.shields.io/badge/frontend-pure-007aff" />
  <img src="https://img.shields.io/badge/license-MIT-blue" />
</p>

---

<h2 align="center">🇨🇳 中文版</h2>

<p align="center">
  一款纯前端、无需后端的个人日常规划工具，<br>
  以日期为中心管理每日待办，通过月历概览全局。
</p>

<p align="center">
  <strong>⌨️ <kbd>Ctrl</kbd>+<kbd>L</kbd> / <kbd>⌘</kbd>+<kbd>L</kbd> 一键中英文切换</strong>
</p>

---

### 🚀 快速开始

1. 下载或克隆本仓库
2. 用浏览器直接打开 `index.html`
3. 开始记录！

> 无需 `npm install`、无需构建工具、无需后端服务器。

---

### ✨ 功能

#### 📅 日历
- 点击 **「日历 ▾」** 展开或折叠月视图
- 左右箭头 `‹` `›` 切换月份
- 日期颜色标记：
  - **蓝色** `#007aff` — 该天有规划但未全部完成
  - **绿色** `#34c759` — 该天所有规划已完成
- 当天带蓝色实心圆高亮
- 点击日期：日历保持展开，下方显示该天的规划

#### 📋 规划与完成情况
- **添加规划**：在底部输入时间和事项，按 `+` 或 `Enter` 提交
- **序号**：每个规划项左侧自动编号 ① ② ③…
- **勾选**：点击圆形勾选框标记完成，序号和文字变绿+删除线
- **完成情况**：每项规划下方可填写完成详情，自动保存
- **删除**：鼠标悬停时出现 ✕ 按钮

#### 🕐 时间选择器
- 小时与分钟分列，中间 `:` 分隔
- 选中值蓝色高亮放大，滚动无限循环
- 点击「完成」确认选择

#### 📝 月备注
- 日历右侧的备注区，每个月份独立存储
- 输入自动保存，切换月份自动加载

#### 🌐 中英文切换
- 点击右上角 **「中文 / EN」** 切换
- 或使用键盘快捷键 <kbd>Ctrl</kbd>+<kbd>L</kbd> / <kbd>⌘</kbd>+<kbd>L</kbd>
- 语言偏好自动保存到 `localStorage`

#### 🎛️ 其他
- **「今天」** 按钮一键跳回当前日期
- 所有数据存储在浏览器本地，关闭页面不丢失

---

### 🎨 设计

| 要素 | 实现 |
|------|------|
| 字体 | `-apple-system` / `SF Pro Display` / `PingFang SC` |
| 背景色 | `#f2f2f6` — iOS 系统灰 |
| 卡片 | `backdrop-filter: blur(16px)` — 毛玻璃效果 |
| 强调色 | `#007aff` — Apple Blue |
| 圆角 | `20px` / `14px` / `10px` 层次化圆角体系 |
| 阴影 | `0 4px 24px rgba(0,0,0,0.04)` 极轻阴影 |
| 动效 | 过渡动画 200–350ms `ease` / `cubic-bezier` |

---

### 💾 数据存储

所有数据存储在浏览器 `localStorage`：

| Key | 内容 |
|-----|------|
| `my_notes_data` | 所有日期的规划数据（JSON） |
| `my_notes_lang` | 语言偏好（`zh` / `en`） |
| `note_{year}_{month}` | 各月备注 |

> ⚠️ 数据不会跨设备同步。清除浏览器数据会导致笔记丢失。

---

### 🗂️ 项目结构

```
note/
├── index.html            ← 入口页面
├── README.md             ← 本文件
│
├── css/
│   ├── base.css          ← 全局重置、字体、容器布局
│   ├── nav.css           ← 顶部导航栏 + 语言切换
│   ├── calendar.css      ← 日历卡片、网格、颜色标记
│   ├── panel.css         ← 规划面板、列表项、添加区域
│   └── time-picker.css   ← 时间选择器组件样式
│
└── js/
    ├── app.js            ← 应用入口：模块初始化协调
    ├── state.js          ← 全局状态变量
    ├── helpers.js        ← 工具函数
    ├── storage.js        ← 数据持久化层
    ├── lang.js           ← 多语言包 + 中英文切换
    ├── notes.js          ← 月备注功能
    ├── calendar.js       ← 日历渲染与导航
    ├── plans.js          ← 规划增删改查 + 完成情况
    └── timepicker.js     ← 时间选择器组件
```

---

### 🌐 浏览器支持

| Safari 15+ | Chrome 90+ | Edge 90+ |
|:----------:|:----------:|:--------:|
| ✅ 最佳 | ✅ | ✅ | 

---

### 📄 许可

MIT License — 随意使用、修改、分享。

---

<h2 align="center">🇬🇧 English</h2>

<p align="center">
  A pure frontend, no-backend daily planner.<br>
  Manage your todos by date and get an overview through the monthly calendar.
</p>

<p align="center">
  <strong>⌨️ Press <kbd>Ctrl</kbd>+<kbd>L</kbd> / <kbd>⌘</kbd>+<kbd>L</kbd> to toggle language</strong>
</p>

---

### 🚀 Quick Start

1. Download or clone this repo
2. Open `index.html` directly in your browser
3. Start planning!

> No `npm install`, no build tools, no backend server required.

---

### ✨ Features

#### 📅 Calendar
- Click **"Calendar ▾"** to expand or collapse the month view
- Arrow buttons `‹` `›` to switch months
- Date color indicators:
  - **Blue** `#007aff` — day has uncompleted plans
  - **Green** `#34c759` — all plans completed
- Today is highlighted with a filled blue circle
- Click a date: calendar stays open, shows that day's plans below

#### 📋 Plans & Completion
- **Add Plan**: Enter time and task at the bottom, submit with `+` or `Enter`
- **Numbering**: Each plan auto-numbered ① ② ③…
- **Check off**: Click the circle to mark complete; number and text turn green + strikethrough
- **Completion notes**: Write details under each plan, auto-saved
- **Delete**: ✕ button appears on hover

#### 🕐 Time Picker
- Hours and minutes in separate columns with `:` separator
- Selected value highlighted in blue with scale animation, infinite scroll
- Click "Done" to confirm

#### 📝 Monthly Notes
- Notes area beside the calendar, stored independently per month
- Auto-saves on input, auto-loads when switching months

#### 🌐 Language Toggle
- Click **"中文 / EN"** in the top-right corner
- Or use the keyboard shortcut <kbd>Ctrl</kbd>+<kbd>L</kbd> / <kbd>⌘</kbd>+<kbd>L</kbd>
- Language preference saved to `localStorage`

#### 🎛️ Other
- **"Today"** button to jump back to the current date
- All data stored in browser local storage, persists across sessions

---

### 🎨 Design

| Element | Implementation |
|---------|----------------|
| Font | `-apple-system` / `SF Pro Display` / `PingFang SC` |
| Background | `#f2f2f6` — iOS System Gray |
| Cards | `backdrop-filter: blur(16px)` — Frosted glass |
| Accent | `#007aff` — Apple Blue |
| Radius | `20px` / `14px` / `10px` layered radius system |
| Shadow | `0 4px 24px rgba(0,0,0,0.04)` ultra-light |
| Motion | 200–350ms `ease` / `cubic-bezier` transitions |

---

### 💾 Data Storage

All data is stored in browser `localStorage`:

| Key | Content |
|-----|---------|
| `my_notes_data` | All plan data (JSON) |
| `my_notes_lang` | Language preference (`zh` / `en`) |
| `note_{year}_{month}` | Monthly notes |

> ⚠️ Data is not synced across devices. Clearing browser data will delete your notes.

---

### 🗂️ Project Structure

```
note/
├── index.html            ← Entry page
├── README.md             ← This file
│
├── css/
│   ├── base.css          ← Global reset, fonts, container layout
│   ├── nav.css           ← Top navigation + language toggle
│   ├── calendar.css      ← Calendar card, grid, color markers
│   ├── panel.css         ← Plans panel, list items, add area
│   └── time-picker.css   ← Time picker component styles
│
└── js/
    ├── app.js            ← App entry: module initialization
    ├── state.js          ← Global state variables
    ├── helpers.js        ← Utility functions
    ├── storage.js        ← Data persistence layer
    ├── lang.js           ← Language pack + toggle
    ├── notes.js          ← Monthly notes
    ├── calendar.js       ← Calendar rendering & navigation
    ├── plans.js          ← Plans CRUD + completion
    └── timepicker.js     ← Time picker component
```

---

### 🌐 Browser Support

| Safari 15+ | Chrome 90+ | Edge 90+ | 
|:----------:|:----------:|:--------:|
| ✅ Best | ✅ | ✅ | 

---

### 📄 License

MIT License — feel free to use, modify, and share.

---


