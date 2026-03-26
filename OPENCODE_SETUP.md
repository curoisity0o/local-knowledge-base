# OpenCode + Superpowers 超能力设置指南

本文档帮助你配置 OpenCode IDE 及其超能力插件。

---

## 1. OpenCode 是什么？

OpenCode 是一个 AI 编程代理框架，类似 Claude Code / Cursor。它支持：
- **多模型支持**：可配置不同的 AI 模型
- **插件系统**：通过插件扩展功能
- **技能系统**：预置的工作流和最佳实践

---

## 2. 当前配置概览

### 配置文件位置
```
~/.config/opencode/
├── opencode.json          # 主配置文件
├── oh-my-opencode.json     # oh-my-opencode 插件配置
└── skills/
    └── superpowers -> ~/.config/opencode/superpowers/skills  # 技能链接
```

### 当前使用的模型
- **默认模型**：`opencode/glm-4.7-free` (免费模型)

---

## 3. 配置文件详解

### 3.1 主配置文件 `opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "oh-my-opencode@latest"
  ]
}
```

**说明**：
- 启用了 `oh-my-opencode` 插件（提供专业 Agent）

### 3.2 插件配置 `oh-my-opencode.json`

```json
{
  "agents": {
    "hephaestus": { "model": "opencode/glm-4.7-free" },
    "oracle": { "model": "opencode/glm-4.7-free" },
    "librarian": { "model": "opencode/glm-4.7-free" },
    "explore": { "model": "opencode/glm-4.7-free" },
    "multimodal-looker": { "model": "opencode/glm-4.7-free" },
    "prometheus": { "model": "opencode/glm-4.7-free" },
    "metis": { "model": "opencode/glm-4.7-free" },
    "momus": { "model": "opencode/glm-4.7-free" },
    "atlas": { "model": "opencode/glm-4.7-free" }
  },
  "categories": {
    "visual-engineering": { "model": "opencode/glm-4.7-free" },
    "ultrabrain": { "model": "opencode/glm-4.7-free" },
    "deep": { "model": "opencode/glm-4.7-free" },
    "artistry": { "model": "opencode/glm-4.7-free" },
    "quick": { "model": "opencode/glm-4.7-free" },
    "unspecified-low": { "model": "opencode/glm-4.7-free" },
    "unspecified-high": { "model": "opencode/glm-4.7-free" },
    "writing": { "model": "opencode/glm-4.7-free" }
  }
}
```

---

## 4. Superpowers 技能系统

### 4.1 已安装的技能

| 技能名称 | 用途 | 触发场景 |
|---------|------|---------|
| `superpowers/brainstorming` | 头脑风暴 | 创建功能、构建组件、添加功能前 |
| `superpowers/dispatching-parallel-agents` | 并行代理分发 | 2+ 独立任务需要并行处理 |
| `superpowers/executing-plans` | 执行计划 | 有待执行的实施计划 |
| `superpowers/finishing-a-development-branch` | 完成开发分支 | 实现完成、测试通过，需要合并 |
| `superpowers/receiving-code-review` | 接收代码审查 | 收到代码审查反馈时 |
| `superpowers/requesting-code-review` | 请求代码审查 | 完成主要功能、合并前 |
| `superpowers/subagent-driven-development` | 子代理驱动开发 | 执行当前会话中的实施计划 |
| `superpowers/systematic-debugging` | 系统调试 | 遇到 bug、测试失败、异常行为 |
| `superpowers/test-driven-development` | TDD 开发 | 实现任何功能或 bugfix 前 |
| `superpowers/using-git-worktrees` | 使用 git worktree | 功能工作需要与当前工作隔离 |
| `superpowers/using-superpowers` | 使用超能力 | 任何对话开始时（自动触发） |
| `superpowers/verification-before-completion` | 完成前验证 | 声称工作完成、修复、测试通过前 |
| `superpowers/writing-plans` | 编写计划 | 有多步骤任务的规格或需求时 |
| `superpowers/writing-skills` | 编写技能 | 创建新技能、编辑现有技能、验证技能 |

### 4.2 技能使用方式

在 OpenCode 中，当你的任务匹配某个技能时，系统会**自动加载**该技能：

```
用户: "帮我实现一个登录功能"
→ 自动触发: superpowers/brainstorming
→ 自动触发: superpowers/writing-plans (如果复杂)
```

**重要**：只要有 1% 的可能技能适用，你就应该调用它。系统会自动决定是否使用。

---

## 5. Agent 类型详解

### 5.1 专用 Agent（通过 `task(subagent_type=...)` 调用）

| Agent | 用途 | 费用 |
|-------|------|------|
| `explore` | 代码库上下文搜索 | 免费 |
| `librarian` | 外部参考文档搜索 | 便宜 |
| `oracle` | 架构/调试咨询 | 昂贵 |
| `metis` | 预规划分析（复杂任务） | 昂贵 |
| `momus` | 计划审查/质量保证 | 昂贵 |

### 5.2 分类 Agent（通过 `task(category=...)` 调用）

| Category | 用途 | 特点 |
|----------|------|------|
| `visual-engineering` | 前端/UI/UX | 视觉设计优先 |
| `ultrabrain` | 硬逻辑任务 | 仅用于真正困难的任务 |
| `deep` | 深度问题解决 | 充分研究后再行动 |
| `artistry` | 创造性方案 | 非常规方法 |
| `quick` | 简单修改 | 单文件修改 |
| `unspecified-low` | 低复杂度任务 | |
| `unspecified-high` | 高复杂度任务 | |
| `writing` | 文档/技术写作 | |

---

## 6. 常用工作流

### 6.1 简单任务流程

```
1. 用户发送请求
2. OpenCode 自动检查是否需要技能
3. 直接执行（如果简单）
4. 验证结果
```

### 6.2 复杂任务流程

```
1. 用户发送请求
2. → 触发 brainstorming 技能
3. → 触发 writing-plans 技能
4. → 创建实施计划（多步骤）
5. → 使用 todo 管理任务
6. → 根据需要触发相关技能
7. → 并行执行或串行执行
8. → 触发 verification-before-completion
9. → 触发 requesting-code-review（如果需要）
```

### 6.3 调试流程

```
1. 发现 bug
2. → 触发 systematic-debugging 技能
3. 诊断问题
4. 尝试修复
5. 验证
6. 如果 3 次失败 → 咨询 oracle
```

---

## 7. 配置示例

### 7.1 切换到更强的模型

编辑 `~/.config/opencode/oh-my-opencode.json`：

```json
{
  "agents": {
    "oracle": { "model": "opencode/claude-sonnet-4" },
    "ultrabrain": { "model": "opencode/claude-sonnet-4" }
  },
  "categories": {
    "ultrabrain": { "model": "opencode/claude-sonnet-4" },
    "deep": { "model": "opencode/claude-sonnet-4" }
  }
}
```

### 7.2 在项目中使用 AGENTS.md

将 `AGENTS.md` 放在项目根目录，OpenCode 会自动读取其中的规则：

```
项目根目录/
├── AGENTS.md           # AI 代理规则（自动读取）
├── src/
├── tests/
└── ...
```

---

## 8. 最佳实践

### 8.1 何时使用技能

| 场景 | 应该使用的技能 |
|------|---------------|
| 开始新功能 | `brainstorming` + `writing-plans` |
| 写测试 | `test-driven-development` |
| 修复 bug | `systematic-debugging` |
| 并行任务 | `dispatching-parallel-agents` |
| 完成工作 | `verification-before-completion` |
| 代码审查 | `requesting-code-review` / `receiving-code-review` |
| 合并分支 | `finishing-a-development-branch` |

### 8.2 何时使用特定 Agent

| 场景 | Agent |
|------|-------|
| 不熟悉代码库的结构 | `explore` |
| 需要查外部文档/示例 | `librarian` |
| 复杂架构问题 | `oracle` |
| 任务范围不清晰 | `metis` |
| 审查计划/代码 | `momus` |

### 8.3 技能调用优先级

1. **先检查技能**：任何行动前，先检查是否有技能适用
2. **进程技能优先**：`brainstorming`、`debugging` → 实现技能
3. **明确才实施**：没有计划不要动手

---

## 9. 故障排除

### 9.1 模型不响应
- 检查网络连接
- 确认 API 密钥配置正确

### 9.2 技能未触发
- 技能是**自动**触发的，不需要手动调用
- 确保任务描述清晰

### 9.3 Agent 费用过高
- 复杂任务才使用 `oracle` / `momus` / `metis`
- 简单任务使用 `explore` / `librarian`

---

## 10. 相关文档

- [AGENTS.md](./AGENTS.md) - 项目专属代理规则
- [oh-my-opencode 文档](https://github.com/code-yeongyu/oh-my-opencode)
- [Superpowers 文档](https://github.com/sparrowjet/superpowers)

---

**祝您使用愉快！** 🚀
