# CLAUDE.md - MyNotes AI

## 项目定位

MyNotes AI 是一个 AI 学习规划与复盘系统，目标是作为 AI 应用开发/AI 全栈实习作品。项目采用 React + TypeScript + Vite 前端，FastAPI 后端，包含日程管理、AI 计划生成、动态复盘、RAG 资料问答、偏好记忆、Agent 工具定义和规划质量评估。

入口文件是 `MyNotes.html`。完整应用必须通过 Vite dev server 或 build 后产物运行；直接用 file 协议打开时只显示启动说明。

## 技术栈

- 前端：React 18、TypeScript、Vite
- UI：自定义 CSS，Apple HIG 风格，lucide-react 图标
- 后端：Python FastAPI
- 数据：前端 localStorage，后端 SQLite
- AI：mock fallback，后续可接 DeepSeek/OpenAI 兼容接口
- 工程化：ESLint、GitHub Actions、Docker

## 开发命令

```bash
npm install
npm run dev
npm run build
```

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

## 代码约定

- 前端新功能优先拆到 `src/components`、`src/lib` 或 `src/utils`。
- Vite 构建入口配置为 `MyNotes.html`，不要再恢复旧版入口。
- 后端服务逻辑放在 `backend/app/services`。
- API schema 统一维护在 `backend/app/schemas.py`。
- AI 功能必须保留 mock fallback，保证没有 API key 也能演示。
- README 面向作品集展示，必须同步更新核心能力、启动方式和简历亮点。
