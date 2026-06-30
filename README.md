<p align="center">
  <br>
  <strong>MyNotes</strong>
  <br>
  <span>一款安静、轻盈、纯前端的日常笔记与规划工具</span>
  <br>
  <span>A quiet daily planner for notes, time, and completion.</span>
  <br><br>
  <a href="#中文">中文</a>
  <span>&nbsp;/&nbsp;</span>
  <a href="#english">English</a>
  <br><br>
  <img alt="Pure Frontend" src="https://img.shields.io/badge/Pure%20Frontend-HTML%20CSS%20JS-0a84ff">
  <img alt="No Backend" src="https://img.shields.io/badge/Backend-None-6e6e73">
  <img alt="Storage" src="https://img.shields.io/badge/Storage-localStorage-30d158">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-1d1d1f">
</p>

<p align="center">
  <img src="assets/mynotes-preview.png" alt="MyNotes interface preview" width="860">
</p>

---

## 中文

**MyNotes** 是一款纯前端个人日常笔记与规划工具。它不需要账号、不需要后端、不需要构建流程，只需要打开 `index.html`，就可以在浏览器里记录每天要做的事、完成情况，以及每个月的备注。

它的设计目标很简单：让日常计划变得轻一点。日历负责提供时间感，规划列表负责承载行动，完成记录负责留下回顾的痕迹。所有数据都保存在当前浏览器本地，适合个人、离线、轻量的日常使用。

### ✨ 核心体验

| 模块 | 说明 |
| --- | --- |
| 📅 日历视图 | 按月查看日期，快速识别哪些天有规划、哪些天已经全部完成。 |
| ✅ 每日规划 | 为选中日期添加事项，支持时间、正文、完成勾选和删除。 |
| 🧾 完成情况 | 每条事项下方都可以记录执行结果，适合复盘和追踪。 |
| 📝 月备注 | 每个月拥有独立备注区，用来记录阶段目标、提醒或灵感。 |
| 🌐 双语界面 | 支持中文与 English 切换，语言偏好自动保存。 |
| 🔒 本地存储 | 数据写入 `localStorage`，关闭页面后仍会保留。 |

### 🚀 快速开始

```text
1. 下载或克隆项目
2. 用浏览器打开 index.html
3. 开始记录当天计划
```

项目没有安装步骤。你可以直接通过文件协议打开，也可以使用 VS Code Live Server 预览。

### 🧭 使用说明

**📅 日历**

- 点击顶部“日历”展开或折叠月历。
- 使用左右箭头切换月份。
- 点击任意日期，规划面板会切换到对应日期。
- 点击“今天”可以回到当前日期。
- 日期颜色代表状态：蓝色表示当天有未完成规划，绿色表示当天规划已全部完成，深色实心圆表示今天。

**✅ 规划**

- 在底部选择时间，输入事项内容。
- 点击加号按钮添加事项。
- 在输入框中按 `Enter` 也可以添加事项。
- 使用 `Shift + Enter`、`Ctrl + Enter` 或 `Command + Enter` 可以换行。
- 点击圆形勾选框标记完成。
- 鼠标悬停到事项上，可以显示删除按钮。

**🧾 完成情况**

每个事项下方都有独立的完成情况输入区。内容会自动保存，适合记录“做到了什么”“哪里没完成”“下一步怎么调整”。

**📝 月备注**

日历右侧的备注区按年月保存。切换月份时，应用会自动加载该月份的备注。

**🌐 语言切换**

- 点击右上角“中文 / EN”切换语言。
- 使用 `Ctrl + L` 或 `Command + L` 也可以快速切换。

### 🎨 设计语言

MyNotes 的视觉方向参考 Apple Human Interface Guidelines：克制、清晰、柔和。界面没有复杂装饰，重点放在信息层级、触控尺寸和阅读舒适度上。

| 设计项 | 实现 |
| --- | --- |
| 🔤 字体 | `-apple-system`、`SF Pro Display`、`PingFang SC` |
| 🌫️ 背景 | 浅灰系统底色，降低长时间使用的视觉负担 |
| 🧊 卡片 | 半透明毛玻璃质感，配合轻阴影分层 |
| 🔵 主色 | Apple Blue `#0a84ff` |
| 🟢 完成色 | System Green `#30d158` |
| 🔴 警示色 | System Red `#ff453a` |
| ◇ 图标 | 内嵌 SVG symbol，无外部图标库 |
| ⏱️ 动效 | 轻量过渡，优先保证操作反馈自然 |

### 💾 数据存储

所有数据都保存在当前浏览器的 `localStorage` 中。

| Key | 内容 |
| --- | --- |
| `my_notes_data` | 所有日期的规划数据 |
| `my_notes_lang` | 当前语言偏好 |
| `note_{year}_{month}` | 每个月的备注 |

请注意：数据不会自动同步到其他设备。清除浏览器数据、更换浏览器或更换设备后，原本的数据将不可见。

### 🗂️ 项目结构

```text
note/
├── index.html
├── README.md
├── AGENTS.md
├── css/
│   ├── base.css
│   ├── nav.css
│   ├── calendar.css
│   ├── panel.css
│   └── time-picker.css
└── js/
    ├── app.js
    ├── state.js
    ├── helpers.js
    ├── storage.js
    ├── lang.js
    ├── notes.js
    ├── calendar.js
    ├── plans.js
    └── timepicker.js
```

### 🛠️ 技术说明

MyNotes 使用原生 HTML、CSS 和 JavaScript 编写。脚本通过 `<script>` 标签按顺序加载，不使用 ES Module、框架、包管理器或构建工具。

```html
<script src="js/helpers.js"></script>
<script src="js/state.js"></script>
<script src="js/storage.js"></script>
<script src="js/lang.js"></script>
<script src="js/notes.js"></script>
<script src="js/timepicker.js"></script>
<script src="js/calendar.js"></script>
<script src="js/plans.js"></script>
<script src="js/app.js"></script>
```

### 🌐 浏览器支持

推荐使用最新版 Chrome、Edge 或 Safari。界面使用了 `backdrop-filter`，较旧浏览器可能无法显示完整毛玻璃效果，但核心记录功能不受影响。

---

## English

**MyNotes** is a pure frontend daily planner for personal notes, time-based tasks, and completion records. It has no account system, no backend, and no build process. Open `index.html` in a browser and start planning.

The product idea is intentionally small: make daily planning feel lighter. The calendar gives a sense of time, the plan list captures action, and completion notes preserve the details worth reviewing. Everything is stored locally in the current browser.

### ✨ Experience

| Area | Description |
| --- | --- |
| 📅 Calendar | Browse the month and understand daily progress at a glance. |
| ✅ Daily plans | Add tasks to a selected date with time, content, completion state, and deletion. |
| 🧾 Completion notes | Record the result of each task for reflection and follow-up. |
| 📝 Monthly notes | Keep month-level goals, reminders, or loose thoughts. |
| 🌐 Bilingual UI | Switch between Chinese and English with saved preference. |
| 🔒 Local first | Data is stored in `localStorage` and remains after closing the page. |

### 🚀 Quick Start

```text
1. Download or clone the project
2. Open index.html in your browser
3. Start planning your day
```

There is no installation step. You can open the file directly or preview it with VS Code Live Server.

### 🧭 How To Use

**📅 Calendar**

- Click “Calendar” in the top bar to expand or collapse the month view.
- Use the arrow buttons to switch months.
- Click any date to view and edit its plans.
- Click “Today” to return to the current date.
- Date colors show progress: blue means the day has unfinished plans, green means all plans are completed, and the dark filled circle marks today.

**✅ Plans**

- Pick a time and write a task at the bottom.
- Click the plus button to add it.
- Press `Enter` in the input field to add quickly.
- Use `Shift + Enter`, `Ctrl + Enter`, or `Command + Enter` for a new line.
- Click the circular checkbox to mark a task as completed.
- Hover over a task to reveal the delete button.

**🧾 Completion Notes**

Each task includes a dedicated completion note field. It autosaves while typing, making it useful for short reviews such as what was done, what changed, and what should happen next.

**📝 Monthly Notes**

The note area beside the calendar is stored per month. Switching months automatically loads the corresponding note.

**🌐 Language**

- Click “中文 / EN” in the top-right corner.
- Or use `Ctrl + L` / `Command + L` to switch quickly.

### 🎨 Visual Direction

MyNotes follows a quiet, Apple-inspired interface direction: soft surfaces, clear hierarchy, comfortable spacing, and minimal visual noise.

| Element | Implementation |
| --- | --- |
| 🔤 Font | `-apple-system`, `SF Pro Display`, `PingFang SC` |
| 🌫️ Background | Soft system gray for long-session comfort |
| 🧊 Cards | Translucent frosted surfaces with subtle shadows |
| 🔵 Accent | Apple Blue `#0a84ff` |
| 🟢 Completion | System Green `#30d158` |
| 🔴 Danger | System Red `#ff453a` |
| ◇ Icons | Inline SVG symbols, no external icon dependency |
| ⏱️ Motion | Gentle transitions for natural feedback |

### 💾 Storage

All data is saved in the current browser's `localStorage`.

| Key | Content |
| --- | --- |
| `my_notes_data` | All dated plan data |
| `my_notes_lang` | Current language preference |
| `note_{year}_{month}` | Monthly notes |

Data is not synced across devices. Clearing browser data, switching browsers, or moving to another device will make the local data unavailable.

### 🗂️ Project Structure

```text
note/
├── index.html
├── README.md
├── AGENTS.md
├── css/
│   ├── base.css
│   ├── nav.css
│   ├── calendar.css
│   ├── panel.css
│   └── time-picker.css
└── js/
    ├── app.js
    ├── state.js
    ├── helpers.js
    ├── storage.js
    ├── lang.js
    ├── notes.js
    ├── calendar.js
    ├── plans.js
    └── timepicker.js
```

### 🛠️ Technical Notes

MyNotes is built with plain HTML, CSS, and JavaScript. Scripts are loaded in order with regular `<script>` tags. There are no ES Modules, frameworks, package managers, build tools, or backend services.

```html
<script src="js/helpers.js"></script>
<script src="js/state.js"></script>
<script src="js/storage.js"></script>
<script src="js/lang.js"></script>
<script src="js/notes.js"></script>
<script src="js/timepicker.js"></script>
<script src="js/calendar.js"></script>
<script src="js/plans.js"></script>
<script src="js/app.js"></script>
```

### 🌐 Browser Support

Latest Chrome, Edge, and Safari are recommended. Older browsers may not fully render the `backdrop-filter` glass effect, but the core planning features should remain usable.

---

## 📄 License

MIT License
