# CLAUDE.md — MyNotes 笔记应用

## 项目概述

一款纯前端、无需后端的个人日常笔记/规划工具。浏览器直接打开 `index.html` 即可使用，所有数据存储在 `localStorage` 中。

## 技术栈

- 原生 HTML + CSS + JavaScript（`<script>` 顺序加载，非 ES Module）
- 无框架、无构建工具、无后端
- 存储：浏览器 `localStorage`

## 设计语言

- Apple Human Interface Guidelines 风格
- 字体：`-apple-system` / `SF Pro Display` / `PingFang SC`
- 背景色：`#f2f2f6`（iOS 系统灰）
- 卡片：`backdrop-filter: blur(16px)` 毛玻璃效果
- 强调色：`#007aff`（Apple Blue）
- 圆角体系：`20px` / `14px` / `10px`
- 阴影：`0 4px 24px rgba(0,0,0,0.04)`
- 动效：200–350ms `ease` / `cubic-bezier`

## 项目结构

```
note/
├── index.html            ← 入口
├── README.md             ← 项目文档
├── CLAUDE.md             ← 本文件
│
├── css/
│   ├── base.css          ← 全局重置、字体、容器
│   ├── nav.css           ← 顶部导航栏
│   ├── calendar.css      ← 日历卡片、网格、标记
│   ├── panel.css         ← 规划面板、列表项、添加区域
│   └── time-picker.css   ← 自定义时间选择器
│
├── js/
│   ├── app.js            ← 应用入口：协调各模块初始化
│   ├── state.js          ← 全局状态变量
│   ├── helpers.js        ← 工具函数
│   ├── storage.js        ← 数据持久化层（localStorage）
│   ├── lang.js           ← 多语言（中/英）
│   ├── notes.js          ← 月备注功能
│   ├── calendar.js       ← 日历渲染与导航
│   ├── plans.js          ← 规划增删改查 + 完成情况
│   └── timepicker.js     ← 时间选择器组件
│
├── .git/
└── .gitignore
```

## 代码约定

- **CSS**：按功能拆分文件（base/nav/calendar/panel/time-picker）
- **JS**：按功能拆分文件，通过 `<script>` 顺序加载（加载顺序见 index.html）
- **全局状态**：集中在 `state.js` 中定义
- **数据持久化**：统一通过 `storage.js` 访问
- **多语言**：用 `data-i18n` / `data-i18n-placeholder` 属性标记，在 `lang.js` 中维护翻译
- **localStorage key**：
  - `my_notes_data` → 所有日期的规划数据（JSON）
  - `note_2026_6` → 各月备注（按年月命名）

## Git

- 默认分支：`main`
- git 用户：`xixi_git`
- 交互辅助工具用 `gh` CLI

## 构建/运行

无需构建，直接在浏览器中打开 `index.html` 即可。建议用 Live Server 或直接文件协议打开。

## 用户偏好

- 交流语言：中文
- 开发者角色：个人开发者，追求简洁美观实用的设计
- 操作系统：Windows 11
- 终端：Git Bash
