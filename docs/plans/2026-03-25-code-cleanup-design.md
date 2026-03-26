# 本地知识库系统代码清理设计

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 清理代码结构，修复技术债务，为继续执行IMPROVEMENT_PLAN.md准备干净代码库

**Architecture:** 保留现有RAG系统架构，修复代码质量问题，添加缺失配置，清理无用文件

**Tech Stack:** Python 3.10+, LangChain, ChromaDB, FastAPI, Streamlit

---

## 项目背景分析

基于对代码库的探索，发现以下问题：

### 1. 代码质量问题（来自IMPROVEMENT_PLAN.md）
- `src/frontend/app.py:345,380` - 裸露的`except:`语句（应替换为具体异常类型）
- `src/core/llm_manager.py:142,198,212` - `# type: ignore`注释（应使用正确类型注解）

### 2. 包结构不完整
- 5个包中只有`src/agents/`有`__init__.py`文件
- 缺失`__init__.py`的包：`src/`, `src/core/`, `src/api/`, `src/frontend/`, `src/utils/`

### 3. 开发配置缺失
- 无`pyproject.toml` - dev tools使用默认配置
- 无`pytest.ini` / `conftest.py` - pytest无配置
- 无`.editorconfig` - 无统一编辑器配置

### 4. 文件冗余检查
- 需要检查`scripts/`目录中的脚本是否都在使用
- 需要检查根目录中文文档文件是否重复
- **用户说明**：保留mineru相关文件（`mineru_api.py`和`mineru_importer.py`），用户自行处理PDF转Markdown

### 5. 测试结构
- 测试目录结构正确，65个测试通过
- 需要确保测试覆盖率

## 清理方法选择

选择**方法2：全面清理** - 修复技术债务并添加缺失配置，平衡清理力度与开发影响。

## 清理计划设计

### 阶段1：代码质量修复

#### 任务1：修复裸露的except语句
**文件：** `src/frontend/app.py:345,380`
**目标：** 将`except:`替换为`except Exception:`或具体异常类型
**验证：** 运行`lsp_diagnostics`确认无错误

#### 任务2：修复类型忽略注释
**文件：** `src/core/llm_manager.py:142,198,212`
**目标：** 使用正确类型注解替换`# type: ignore`注释
**验证：** 运行`mypy`或类型检查确认无错误

#### 任务3：添加缺失的__init__.py文件
**文件：**
- `src/__init__.py`
- `src/core/__init__.py`
- `src/api/__init__.py`
- `src/frontend/__init__.py`
- `src/utils/__init__.py`
**目标：** 创建空的`__init__.py`文件标记Python包
**验证：** Python导入测试

### 阶段2：开发配置添加

#### 任务4：创建pyproject.toml
**文件：** `pyproject.toml`
**目标：** 配置black、ruff、mypy等开发工具
**内容：** 基于Python项目标准配置

#### 任务5：创建pytest.ini
**文件：** `pytest.ini`
**目标：** 配置pytest测试运行器
**内容：** 设置测试发现、报告格式等

#### 任务6：创建.editorconfig
**文件：** `.editorconfig`
**目标：** 统一编辑器代码风格设置
**内容：** 标准Python EditorConfig

### 阶段3：文件清理（谨慎进行）

#### 任务7：检查scripts目录
**目录：** `scripts/`
**目标：** 检查脚本是否都在使用，标记未使用脚本
**方法：** 分析文件引用，不自动删除

#### 任务8：检查文档文件
**文件：** 根目录中文文档（技术方案.md、技术文档.md、开发进度.md）
**目标：** 检查与docs/目录内容是否重复
**方法：** 对比内容，建议合并或移动

#### 任务9：保留mineru文件（用户要求）
**文件：** `src/core/mineru_api.py`, `src/utils/mineru_importer.py`
**目标：** 明确标记这些文件为用户保留，不进行清理
**说明：** 用户将自行处理PDF转Markdown功能

### 阶段4：验证清理结果

#### 任务10：运行测试验证
**命令：** `pytest tests/ -v`
**目标：** 确保所有65个测试仍然通过
**预期：** 0失败，可能有一些跳过

#### 任务11：运行代码质量检查
**命令：** `ruff check src/`, `black --check src/`
**目标：** 确认代码符合格式规范
**预期：** 无错误或可自动修复的格式问题

#### 任务12：检查导入结构
**目标：** 验证添加__init__.py后导入正常工作
**方法：** 运行`python -c "import src.core.config"`等测试

## 成功标准

1. ✅ 代码质量问题修复完成
2. ✅ 缺失配置文件添加完成
3. ✅ __init__.py文件添加完成
4. ✅ 所有现有测试通过
5. ✅ mineru相关文件明确保留
6. ✅ 代码库为执行IMPROVEMENT_PLAN.md做好准备

## 风险与缓解

- **风险：** 添加__init__.py可能影响现有导入
  - **缓解：** 创建空文件，不影响现有代码
- **风险：** 清理脚本可能误删有用文件
  - **缓解：** 仅检查，不自动删除，标记建议
- **风险：** 配置更改可能影响现有开发流程
  - **缓解：** 使用标准配置，保持向后兼容

## 下一步：执行IMPROVEMENT_PLAN.md

清理完成后，系统将准备好执行`docs/IMPROVEMENT_PLAN.md`中的改进项，特别是P1优先级项目：
- P1-1：添加Query变换模块
- P1-2：语义分块
- P1-3：启用MinerU精排PDF
- P1-4：可观测性基础
- P1-5：PDF页面级分块

---

*设计文档版本: v1.0*
*创建日期: 2026-03-25*
*基于项目状态: 2026-03-24提交*