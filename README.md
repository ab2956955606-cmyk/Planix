# Planix

**Planix is an AI planning workspace with AI Agent, RAG, Agent Runtime, `structuredPlan`, P Mode, Tauri, and FastAPI sidecar packaging.**

**Current version:** `v3.0.0`

**Version note:** `v3.0.0` is the portfolio-facing documentation version. It does not mean `package.json`, backend health, Tauri config, Cargo config, or installer build versions were bumped.

Planix 是一个面向学习、求职和长期目标管理的桌面 AI 规划工作台。它可以把用户的宽泛目标转化为结构化、可审查、可细化、可写入日历的任务计划，并结合本地资料库检索、Agent Runtime 执行链、P Mode 命令式对话和 Tauri 桌面打包，形成一个完整的 AI 应用工程项目。

它不是普通的 prompt demo。Planix 的重点是把模型输出接入真实应用流程：先通过 RAG 检索本地上下文，再生成 `structuredPlan`，通过 NDJSON streaming 展示 Agent Runtime 过程，最后由用户确认后安全写入 Calendar。

## Demo / 项目演示

Planix 的核心演示路径是：输入一个宽泛目标，例如“帮我规划本周 AI 应用实习准备”，系统会检索本地资料库，生成结构化计划，展示 Agent Runtime 执行链，并允许用户继续细化任务或确认写入日历。

<!-- TODO: 运行真实应用后补充截图。推荐路径：assets/planix-dashboard-cn.png -->

## Planix 是什么

Planix 是一个桌面端 AI planning workspace，目标是帮助用户把模糊目标拆成可以执行、可以追踪、可以写入日历的计划。

适合场景：

- 学习计划：AI Agent、编程、英语、考试、实习准备。
- 求职计划：简历优化、项目复盘、面试准备、作品集打磨。
- 长期目标管理：阶段目标拆解、任务细化、日历排期。
- 本地资料驱动规划：结合用户保存的笔记、资料和历史计划生成更贴合上下文的建议。

## 核心亮点

- **结构化目标规划**：模型输出不是一段自由文本，而是可校验、可预览、可写入下游流程的 `structuredPlan`。
- **Grounded RAG 本地资料检索**：规划前先检索用户本地资料库，让计划有上下文依据，而不是纯模型发挥。
- **Agent Runtime 可观测执行链**：通过 NDJSON streaming 展示 memory lookup、material search、task proposal、summary 等关键步骤。
- **P Mode 命令式工作流**：提供类似 Codex / Cursor 的命令式对话入口，用于生成、展开、细化、修改和确认计划草稿。
- **安全 Calendar 写入**：Runtime 不自动写入正式数据；计划写入 Calendar 前需要预览、权限判断或用户确认。
- **桌面端工程闭环**：使用 Tauri 桌面壳 + FastAPI sidecar + SQLite 本地数据，让项目从 Web demo 走向可安装桌面应用。

## 为什么不只是 Prompt Demo

很多 AI 应用 demo 只是把用户输入拼成 prompt，然后把模型返回文本显示出来。Planix 的重点不是“调用一次大模型”，而是把 AI 输出接入真实产品流程。

Planix 做了几件更接近真实 AI 应用工程的事情：

1. **结构化输出约束**
   模型输出会被约束为 `structuredPlan`，后端会校验、补全，并从结构化数据派生展示内容和日历任务。

2. **RAG 上下文 grounding**
   系统会先从本地资料库检索相关内容，再生成规划结果，减少纯模型幻觉。

3. **Runtime 可观测性**
   Agent 执行过程通过 NDJSON 事件流输出，前端渲染为 Agent Flow Trace，而不是只显示最终答案。

4. **用户确认后的动作执行**
   计划写入 Calendar 前需要用户预览和确认，避免 AI 自动修改正式数据。

5. **桌面端交付能力**
   项目不仅有前端和后端，还包含 Tauri 桌面壳、PyInstaller / FastAPI sidecar、本地 SQLite 数据和 Windows 安装包展示。

## 系统架构

Planix 采用本地优先的桌面 AI 应用架构：

```text
React + TypeScript 前端界面
        ↓
Tauri Desktop Shell
        ↓
FastAPI Backend Sidecar
        ↓
SQLite / FTS5 / Local Files
        ↓
RAG + Planning Service + Agent Runtime
        ↓
NDJSON Stream → Agent Flow Trace UI
```

核心分层：

- **Frontend Shell**：负责 Dashboard、Calendar、Notes、Goals、Materials、Settings、P Mode 和 Inspector。
- **Planning Service**：负责目标规划、`structuredPlan` 生成、fallback 处理和结果派生。
- **RAG Layer**：基于 SQLite / FTS5 检索用户本地资料。
- **Agent Runtime**：负责 memory lookup、tool routing、task proposal 和 runtime event streaming。
- **Persistence Layer**：使用 SQLite 保存计划、笔记、资料、设置、Runtime 记录和 Command thread。
- **Desktop Packaging**：使用 Tauri 桌面壳和 FastAPI sidecar 打包为 Windows 桌面应用。

## 功能模块

### 目标规划

- 输入一个宽泛目标。
- 生成阶段、里程碑、任务、预计时间、优先级和复盘问题。
- 输出 `structuredPlan`。
- 支持 fallback 和错误诊断。
- 用户确认后可将任务写入 Calendar。

### 本地资料库 / RAG

- 支持保存和上传 TXT / MD 资料。
- 使用 SQLite FTS5 / BM25-style search 检索本地内容。
- 规划和 Runtime 可以引用相关资料。
- 前端展示参考资料来源。

### Agent Runtime

- 将一次用户目标转化为可观察的执行流。
- 支持 NDJSON streaming。
- 前端展示 Agent Flow Trace。
- Runtime 工具以只读检索和预览提案为主。
- 默认不自动写入正式数据。

### P Mode / Command Agent

- 提供命令式 AI 对话入口。
- 支持 Auto Agent Mode、强制 Chat 模式、强制 Workbench 模式。
- 支持计划草稿生成、展开、修改、细化和上下文追问。
- 支持通过权限机制确认后写入 Calendar。
- 执行链以内联卡片展示，避免把页面变成复杂工作台。

### Calendar 执行闭环

- 日历计划可以来自用户手动输入，也可以来自确认后的 AI 计划。
- AI 写入不覆盖用户 completion / result / done。
- 任务细化内容作为计划执行说明保存，不污染完成情况。

### 桌面端

- Tauri 桌面壳。
- FastAPI backend sidecar。
- SQLite 本地数据。
- Windows 安装包展示。
- MSI 保留为备用 / 企业安装格式。

## 技术栈

- **Frontend**：React, TypeScript, Vite
- **Desktop**：Tauri
- **Backend**：Python, FastAPI
- **Storage**：SQLite, local files
- **Retrieval**：SQLite FTS5 / BM25-style search
- **Runtime**：NDJSON streaming, Agent Flow Trace
- **AI Provider**：DeepSeek-compatible OpenAI-style API
- **Packaging**：PyInstaller sidecar, Tauri Windows installer

## 本地运行

### 后端

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

### 前端

```powershell
cd apps\web
npm install
npm run dev
```

### 桌面端

```powershell
.\scripts\dev-desktop.ps1
cd apps\desktop
npm install
npm run dev
```

## 桌面端安装说明

当前 README 使用 `v3.0.0` 作为作品集展示版本。

推荐的 Windows 安装包命名：

```text
Planix-v3.0.0-windows-x64-setup.exe
```

备用 / 企业安装包：

```text
Planix-v3.0.0-windows-x64.msi
```

校验文件：

```text
Planix-v3.0.0-windows-x64-setup.exe.sha256
Planix-v3.0.0-windows-x64.msi.sha256
```

`.sha256` 文件是校验文件，不是安装程序，不能双击安装。

如果真实 Release 资产尚未完全匹配上述命名，则这些名称表示 intended installer naming，真实下载以 GitHub Release 页面为准。

## 验证方式

```powershell
python -m compileall backend
.\.venv\Scripts\python.exe -m pytest backend\tests
cd apps\web
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

Backend health check:

```powershell
curl http://127.0.0.1:8000/api/health
```

> Note: `v3.0.0` is the portfolio-facing documentation version. It does not imply a package, backend, or installer version bump unless a separate release task is performed.

## Roadmap

### 已完成

- Planning Intelligence + `structuredPlan` 结构化规划。
- Grounded RAG 本地资料检索。
- Agent Runtime + NDJSON streaming。
- Agent Flow Trace 可观测执行轨迹。
- P Mode / Command Agent 命令式规划工作流。
- Calendar-ready proposal 预览与确认写入。
- Tauri 桌面端原型。
- FastAPI sidecar 打包链路。

### 进行中

- Windows 安装包体验优化。
- Runtime replay / debug view。
- README 作品集化与真实截图补充。
- 更清晰的动作审批 UX。
- P Mode 细化任务体验优化。

### 下一步

- 多计划工作区。
- 更系统的 planning quality evaluation。
- 更稳定的 Runtime 回放和调试。
- 更多工具集成。
- 更完整的新用户 onboarding 示例数据。

## 面试展示价值

Planix 主要展示以下能力：

- **AI 应用工程**：把模型输出接入真实业务流程，而不是只做 prompt demo。
- **全栈开发**：React 前端、FastAPI 后端、SQLite 存储、桌面端打包。
- **Agent Runtime 设计**：可观察的执行链、工具路由、事件流和安全边界。
- **RAG 系统实践**：本地资料检索、上下文注入、来源展示。
- **产品化能力**：从 Web 应用扩展到可安装桌面应用。
- **安全意识**：API Key 不提交，Runtime 不自动写入正式数据，Calendar 写入需要用户确认。
