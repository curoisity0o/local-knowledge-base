# 知识库文档管理功能优化计划

## TL;DR

> **Quick Summary**: 增强本地知识库系统的文档管理能力，添加文档列表、删除、统计和批量操作功能，同步清理向量存储中的相关数据。
> 
> **Deliverables**: 
> - 后端API端点：文档列表、删除、统计
> - 向量存储删除功能扩展
> - 前端文档管理界面增强
> - 一致性检查和错误处理
> 
> **Estimated Effort**: Medium (4-6小时)
> **Parallel Execution**: YES - 3 waves (backend, frontend, integration)
> **Critical Path**: API端点 → 向量存储扩展 → 前端集成 → 测试

---

## Context

### Original Request
用户需要优化知识库的文档管理功能，能够查看、管理和删除已上传的文档，同时清理向量存储中的相关数据。

### Interview Summary
**Key Discussions**:
- 当前系统已有文档上传和处理功能
- 缺少文档列表查看和删除功能
- 需要同步清理向量存储中的文档数据
- 需要添加文档统计和状态显示

**Research Findings**:
- ChromaDB支持 `collection.delete(where={"source": "file_path"})` 按源文件删除向量
- 当前SimpleVectorStore类缺少删除功能
- 现有API有/upload和/process端点，缺少/list和/delete
- 前端有基础上传功能，缺少管理界面

### Metis Review
**Identified Gaps** (addressed):
1. 需要确认ChromaDB删除API的兼容性 - 已确认支持
2. 需要添加错误处理和回滚机制 - 已在计划中考虑
3. 需要前端确认对话框和批量操作 - 已在计划中考虑

---

## Work Objectives

### Core Objective
为本地知识库系统添加完整的文档管理功能，包括文档列表查看、删除、统计和批量操作。

### Concrete Deliverables
1. 后端API端点：
   - GET `/api/v1/documents/list` - 获取文档列表
   - DELETE `/api/v1/documents/{filename}` - 删除文档及向量
   - GET `/api/v1/documents/stats` - 获取文档统计
   
2. 向量存储扩展：
   - SimpleVectorStore.delete_by_source(source_path) 方法
   - 文档-向量一致性检查方法
   
3. 前端界面增强：
   - 文档列表表格显示
   - 删除按钮和确认对话框
   - 统计信息面板
   - 批量选择和操作

### Definition of Done
- [ ] 所有API端点测试通过
- [ ] 前端界面功能完整
- [ ] 文档删除时同步清理向量存储
- [ ] 错误处理完善，无数据不一致风险

### Must Have
- 文档列表查看功能
- 文档删除功能（文件+向量）
- 一致性保证（文件删除必须清理向量）
- 前端用户确认对话框

### Must NOT Have (Guardrails)
- 自动批量删除（需用户确认）
- 不完整的向量清理（删除必须彻底）
- 破坏性操作无确认
- 忽略错误处理和数据一致性

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: Tests-after (添加新测试)
- **Framework**: pytest
- **If TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **API Testing**: Use Bash (curl) — Send requests, assert status + response fields
- **UI Testing**: Use Playwright (playwright skill) — Navigate, click, assert DOM
- **Integration Testing**: Use Bash (python scripts) — Test end-to-end workflows

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.

```
Wave 1 (Start Immediately — backend foundation):
├── Task 1: 扩展向量存储类添加删除方法 [quick]
├── Task 2: 添加后端API端点模型定义 [quick]
├── Task 3: 实现文档列表API端点 [quick]
├── Task 4: 实现文档删除API端点 [deep]
├── Task 5: 实现文档统计API端点 [quick]
├── Task 6: 添加后端单元测试 [quick]
└── Task 7: 更新API文档端点说明 [writing]

Wave 2 (After Wave 1 — frontend implementation):
├── Task 8: 分析前端app.py结构 [quick]
├── Task 9: 创建文档管理组件函数 [visual-engineering]
├── Task 10: 实现文档列表表格显示 [visual-engineering]
├── Task 11: 实现删除按钮和确认对话框 [visual-engineering]
├── Task 12: 实现文档统计面板 [visual-engineering]
├── Task 13: 集成API调用和状态管理 [unspecified-high]
└── Task 14: 添加前端错误处理 [unspecified-high]

Wave 3 (After Wave 2 — integration & testing):
├── Task 15: 端到端集成测试 [deep]
├── Task 16: 一致性验证测试 [deep]
├── Task 17: 错误场景测试 [unspecified-high]
├── Task 18: 性能测试 (批量操作) [deep]
└── Task 19: 文档更新和发布说明 [writing]

Wave FINAL (After ALL tasks — independent review, 3 parallel):
├── Task F1: 代码质量审查 (unspecified-high)
├── Task F2: 安全性审查 (unspecified-high)
└── Task F3: 用户验收测试模拟 (unspecified-high)

Critical Path: Task 1 → Task 4 → Task 10 → Task 13 → Task 15 → F1-F3
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 7 (Waves 1 & 2)
```

### Dependency Matrix (abbreviated)

- **1-7**: — — 8-14, 1
- **8**: 1-7 — 9-14, 2
- **15**: 8-14 — 16-19, 3
- **16**: 15 — 17, 3
- **19**: 15-18 — F1-F3, FINAL

> This is abbreviated for reference. YOUR generated plan must include the FULL matrix for ALL tasks.

### Agent Dispatch Summary

- **1**: **7** — T1-T5 → `quick`, T6 → `quick`, T7 → `writing`
- **2**: **7** — T8 → `quick`, T9-T12 → `visual-engineering`, T13-T14 → `unspecified-high`
- **3**: **5** — T15 → `deep`, T16 → `deep`, T17 → `unspecified-high`, T18 → `deep`, T19 → `writing`
- **FINAL**: **3** — F1-F3 → `unspecified-high`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**

- [ ] 1. 扩展向量存储类添加删除方法

  **What to do**:
  - 在 `src/core/vector_store.py` 中添加 `delete_by_source(source_path)` 方法
  - 实现使用 ChromaDB `collection.delete(where={"source": source_path})` 删除向量
  - 添加 `get_documents_by_source(source_path)` 方法用于验证
  - 添加单元测试：测试删除功能，验证向量被正确移除

  **Must NOT do**:
  - 修改现有API端点的签名
  - 改变现有的向量存储初始化逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 核心功能扩展，相对简单直接
  - **Skills**: [`git-master`]
    - `git-master`: 需要正确的版本控制和提交策略

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-7) | Sequential
  - **Blocks**: Task 4 (文档删除API端点)
  - **Blocked By**: None (可以立即开始)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `src/core/vector_store.py:113-128` - `add_documents` 方法实现模式
  - `src/core/vector_store.py:130-146` - `similarity_search` 方法结构

  **API/Type References** (contracts to implement against):
  - ChromaDB官方文档：`collection.delete(where={"source": "path"})`

  **Test References** (testing patterns to follow):
  - `tests/agents/test_tools.py` - pytest测试结构和断言模式

  **External References** (libraries and frameworks):
  - ChromaDB文档：https://docs.trychroma.com/reference/Collection#delete

  **WHY Each Reference Matters**:
  - `add_documents` 方法展示了如何正确访问 `self.vector_store` 和错误处理
  - ChromaDB文档提供了确切的删除API调用方式
  - 现有测试文件展示了项目的测试约定

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 测试文件创建: `tests/core/test_vector_store_extended.py`
  - [ ] `pytest tests/core/test_vector_store_extended.py::test_delete_by_source` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 测试向量删除功能
    Tool: Bash (python script)
    Preconditions: 1. 向量存储已初始化 2. 至少有一个测试文档向量
    Steps:
      1. 调用 add_documents 添加测试文档
      2. 调用 get_documents_by_source 验证文档存在
      3. 调用 delete_by_source 删除文档
      4. 再次调用 get_documents_by_source 验证文档已被删除
    Expected Result: 删除后验证返回空列表
    Failure Indicators: 删除后文档仍然存在
    Evidence: .sisyphus/evidence/task-1-vector-delete-test.txt

  Scenario: 测试删除不存在的文档
    Tool: Bash (python script)
    Preconditions: 向量存储已初始化
    Steps:
      1. 调用 delete_by_source 删除不存在的文件路径
      2. 验证不会抛出异常
    Expected Result: 方法正常返回，无错误
    Evidence: .sisyphus/evidence/task-1-delete-nonexistent.txt
  ```

  **Evidence to Capture**:
  - [ ] 测试输出文件包含具体断言结果
  - [ ] 错误场景处理验证

  **Commit**: YES
  - Message: `feat(vector-store): add delete_by_source method`
  - Files: `src/core/vector_store.py`, `tests/core/test_vector_store_extended.py`
  - Pre-commit: `pytest tests/core/test_vector_store_extended.py`

- [ ] 2. 添加后端API端点模型定义

  **What to do**:
  - 在 `src/api/main.py` 中添加新的Pydantic模型：
    - `DocumentInfo`: 文档基本信息
    - `DocumentListResponse`: 文档列表响应
    - `DocumentDeleteResponse`: 删除响应
    - `DocumentStatsResponse`: 统计响应
  - 确保模型包含所有必要字段（文件名、路径、大小、修改时间、格式、chunks数、向量状态）
  - 添加模型导入和文档注释

  **Must NOT do**:
  - 修改现有模型定义
  - 改变现有API端点响应结构

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 数据模型定义，简单直接
  - **Skills**: []
    - 无需特殊技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-7)
  - **Blocks**: Task 3, 4, 5 (API端点实现需要这些模型)
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `src/api/main.py:81-94` - `QueryRequest` 和 `QueryResponse` 模型定义
  - `src/api/main.py:96-106` - `DocumentProcessResponse` 模型结构

  **API/Type References**:
  - `pydantic.BaseModel` 官方文档：字段类型和验证器

  **WHY Each Reference Matters**:
  - 现有模型展示了项目的命名约定和字段设计
  - Pydantic文档确保正确的类型定义

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 模型定义语法正确，无类型错误
  - [ ] `mypy src/api/main.py` → 无错误

  **QA Scenarios**:

  ```
  Scenario: 验证模型序列化/反序列化
    Tool: Bash (python script)
    Preconditions: API文件存在
    Steps:
      1. 导入新定义的模型类
      2. 创建实例并序列化为JSON
      3. 从JSON反序列化回模型
      4. 验证字段值正确性
    Expected Result: 序列化/反序列化成功，字段值一致
    Evidence: .sisyphus/evidence/task-2-model-validation.txt

  Scenario: 验证必需字段
    Tool: Bash (python script)
    Preconditions: 模型类已定义
    Steps:
      1. 尝试创建缺少必需字段的模型实例
      2. 验证Pydantic抛出验证错误
    Expected Result: 正确的验证错误信息
    Evidence: .sisyphus/evidence/task-2-validation-errors.txt
  ```

  **Evidence to Capture**:
  - [ ] 序列化/反序列化测试结果
  - [ ] 验证错误测试结果

  **Commit**: YES
  - Message: `feat(api): add document management models`
  - Files: `src/api/main.py`
  - Pre-commit: `mypy src/api/main.py`

- [ ] 3. 实现文档列表API端点

  **What to do**:
  - 在 `src/api/main.py` 中添加 `GET /api/v1/documents/list` 端点
  - 扫描 `data/raw_docs/` 目录获取文件列表
  - 查询向量存储获取每个文件的向量状态和chunks数
  - 返回 `DocumentListResponse` 格式的响应
  - 添加错误处理（目录不存在，向量存储不可用等）

  **Must NOT do**:
  - 修改现有文件上传逻辑
  - 改变现有端点URL结构

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: API端点实现，模式固定
  - **Skills**: [`git-master`]
    - `git-master`: 需要正确的提交和版本控制

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4-7)
  - **Blocks**: Task 13 (前端集成)
  - **Blocked By**: Task 2 (需要模型定义)

  **References**:

  **Pattern References**:
  - `src/api/main.py:354-380` - `upload_document` 端点实现模式
  - `src/api/main.py:382-422` - `process_documents` 端点结构
  - `src/api/main.py:239-352` - `query_knowledge_base` 错误处理

  **File Operations References**:
  - `src/core/document_processor.py:120-134` - 目录扫描和文件处理
  - Python `os.path` 和 `pathlib` 模块文档

  **WHY Each Reference Matters**:
  - 现有端点展示了FastAPI装饰器用法和错误处理
  - 文档处理器展示了如何遍历文档目录
  - 需要遵循项目的错误处理模式

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 端点测试: `pytest tests/api/test_document_list.py` → PASS
  - [ ] curl测试: `curl http://localhost:8000/api/v1/documents/list` 返回正确JSON

  **QA Scenarios**:

  ```
  Scenario: 测试文档列表端点
    Tool: Bash (curl)
    Preconditions: 1. API服务运行中 2. 有测试文档在 data/raw_docs/
    Steps:
      1. 发送 GET 请求到 /api/v1/documents/list
      2. 验证状态码为200
      3. 解析JSON响应
      4. 验证响应包含 documents 数组
      5. 验证每个文档有正确的字段
    Expected Result: 成功返回文档列表，格式正确
    Evidence: .sisyphus/evidence/task-3-document-list-response.json

  Scenario: 测试空目录情况
    Tool: Bash (python script)
    Preconditions: 清空测试目录
    Steps:
      1. 临时重命名 data/raw_docs/ 目录
      2. 创建空目录
      3. 调用文档列表端点
      4. 恢复原目录
    Expected Result: 返回空数组，非错误
    Evidence: .sisyphus/evidence/task-3-empty-directory.txt

  Scenario: 测试向量状态检测
    Tool: Bash (python script + curl)
    Preconditions: 部分文档已处理为向量
    Steps:
      1. 调用文档列表端点
      2. 验证已处理文档的 vector_status 为 "indexed"
      3. 验证未处理文档的 vector_status 为 "not_indexed"
    Expected Result: 正确识别向量状态
    Evidence: .sisyphus/evidence/task-3-vector-status.txt
  ```

  **Evidence to Capture**:
  - [ ] API响应JSON文件
  - [ ] 空目录测试结果
  - [ ] 向量状态验证

  **Commit**: YES
  - Message: `feat(api): add document list endpoint`
  - Files: `src/api/main.py`, `tests/api/test_document_list.py`
  - Pre-commit: `pytest tests/api/test_document_list.py`

- [ ] 4. 实现文档删除API端点

  **What to do**:
  - 在 `src/api/main.py` 中添加 `DELETE /api/v1/documents/{filename}` 端点
  - 实现两步删除：1) 删除文件 2) 清理向量存储
  - 使用Task 1实现的 `delete_by_source` 方法
  - 添加原子性保证：如果向量删除失败，尝试恢复文件
  - 返回 `DocumentDeleteResponse` 包含删除结果详情
  - 添加严格的错误处理和日志记录

  **Must NOT do**:
  - 不完整的删除（只删文件不删向量）
  - 无确认的直接删除
  - 忽略错误处理和数据一致性

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要原子操作和错误恢复，复杂性较高
  - **Skills**: [`git-master`, `superpowers/systematic-debugging`]
    - `git-master`: 关键功能需要谨慎的版本控制
    - `systematic-debugging`: 需要处理复杂的错误场景

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-7)
  - **Blocks**: Task 11 (前端删除按钮), Task 15 (集成测试)
  - **Blocked By**: Task 1 (需要向量删除方法), Task 2 (需要模型定义)

  **References**:

  **Pattern References**:
  - `src/api/main.py:354-380` - 文件操作和错误处理模式
  - `src/api/main.py:239-352` - 复杂业务逻辑实现

  **Atomic Operation References**:
  - Python异常处理和回滚模式
  - 事务性文件操作最佳实践

  **WHY Each Reference Matters**:
  - 现有端点展示了如何正确处理文件操作
  - 需要实现类似数据库事务的原子性
  - 错误处理必须完善以防止数据不一致

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 端点测试: `pytest tests/api/test_document_delete.py` → PASS
  - [ ] 原子性测试: 验证失败场景下的回滚
  - [ ] curl测试: `curl -X DELETE http://localhost:8000/api/v1/documents/test.txt`

  **QA Scenarios**:

  ```
  Scenario: 测试成功删除文档
    Tool: Bash (curl + python script)
    Preconditions: 1. 测试文档存在 2. 文档已在向量存储中
    Steps:
      1. 查询文档列表确认文档存在
      2. 发送DELETE请求删除文档
      3. 验证响应状态为200
      4. 验证响应中 file_deleted 和 vectors_deleted 都为True
      5. 再次查询文档列表确认文档不存在
      6. 验证向量存储中相关向量已被清理
    Expected Result: 文档和向量都被成功删除
    Evidence: .sisyphus/evidence/task-4-successful-delete.json

  Scenario: 测试向量删除失败回滚
    Tool: Bash (python script)
    Preconditions: 模拟向量存储故障
    Steps:
      1. 准备测试文档
      2. 模拟向量存储.delete_by_source抛出异常
      3. 调用删除端点
      4. 验证文件未被删除（回滚成功）
      5. 验证响应包含错误信息
    Expected Result: 原子性保证，文件保留
    Evidence: .sisyphus/evidence/task-4-rollback-test.txt

  Scenario: 测试删除不存在的文档
    Tool: Bash (curl)
    Preconditions: 文档不存在
    Steps:
      1. 发送DELETE请求删除不存在的文档
      2. 验证返回404状态码
      3. 验证错误信息明确
    Expected Result: 正确的404响应
    Evidence: .sisyphus/evidence/task-4-not-found.json
  ```

  **Evidence to Capture**:
  - [ ] 成功删除的完整流程验证
  - [ ] 失败回滚测试结果
  - [ ] 错误处理测试

  **Commit**: YES
  - Message: `feat(api): add document delete endpoint with atomic operations`
  - Files: `src/api/main.py`, `tests/api/test_document_delete.py`
  - Pre-commit: `pytest tests/api/test_document_delete.py`

- [ ] 5. 实现文档统计API端点

  **What to do**:
  - 在 `src/api/main.py` 中添加 `GET /api/v1/documents/stats` 端点
  - 统计信息包括：文档总数、已处理文档数、未处理文档数、总大小、平均chunks数
  - 从向量存储获取文档向量统计信息
  - 返回 `DocumentStatsResponse` 格式的响应
  - 添加缓存机制（可选，避免频繁扫描）

  **Must NOT do**:
  - 修改现有统计逻辑（如果存在）
  - 添加过复杂的聚合计算

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的数据聚合端点
  - **Skills**: [`git-master`]
    - `git-master`: 版本控制

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6-7)
  - **Blocks**: Task 12 (前端统计面板)
  - **Blocked By**: Task 2 (需要模型定义)

  **References**:

  **Pattern References**:
  - `src/api/main.py:354-380` - 端点实现模式
  - `src/api/main.py:239-352` - 错误处理

  **Statistical References**:
  - Python `os.path.getsize()` 文件大小统计
  - 向量存储统计方法（如果存在）

  **WHY Each Reference Matters**:
  - 现有端点展示了FastAPI响应模式
  - 需要遵循项目的错误处理约定

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 端点测试: `pytest tests/api/test_document_stats.py` → PASS
  - [ ] curl测试: `curl http://localhost:8000/api/v1/documents/stats`

  **QA Scenarios**:

  ```
  Scenario: 测试文档统计端点
    Tool: Bash (curl)
    Preconditions: 1. API服务运行中 2. 有多个文档（部分已处理）
    Steps:
      1. 发送 GET 请求到 /api/v1/documents/stats
      2. 验证状态码为200
      3. 解析JSON响应
      4. 验证响应包含 total_documents, processed_count, total_size 等字段
      5. 验证数值正确性
    Expected Result: 返回正确的统计信息
    Evidence: .sisyphus/evidence/task-5-stats-response.json

  Scenario: 测试空目录统计
    Tool: Bash (python script)
    Preconditions: 清空测试目录
    Steps:
      1. 临时清空 data/raw_docs/ 目录
      2. 调用统计端点
      3. 恢复原目录
    Expected Result: 返回 total_documents: 0, processed_count: 0
    Evidence: .sisyphus/evidence/task-5-empty-stats.txt
  ```

  **Evidence to Capture**:
  - [ ] 统计响应JSON
  - [ ] 空目录测试结果

  **Commit**: YES
  - Message: `feat(api): add document statistics endpoint`
  - Files: `src/api/main.py`, `tests/api/test_document_stats.py`
  - Pre-commit: `pytest tests/api/test_document_stats.py`

- [ ] 6. 添加后端单元测试

  **What to do**:
  - 为所有新API端点创建测试文件：
    - `tests/api/test_document_list.py`
    - `tests/api/test_document_delete.py`
    - `tests/api/test_document_stats.py`
  - 测试正常流程和错误场景
  - 使用 pytest fixtures 设置测试数据
  - 确保测试覆盖率达到80%以上
  - 添加集成测试验证文件+向量一致性

  **Must NOT do**:
  - 破坏现有测试
  - 忽略错误场景测试

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 测试编写，模式固定
  - **Skills**: [`superpowers/test-driven-development`]
    - `test-driven-development`: 确保测试质量和覆盖率

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5, 7)
  - **Blocks**: Task 15 (端到端测试)
  - **Blocked By**: Tasks 3, 4, 5 (需要API端点完成)

  **References**:

  **Pattern References**:
  - `tests/agents/test_tools.py` - pytest测试结构
  - `tests/api/test_query.py` - API端点测试模式

  **Testing References**:
  - pytest官方文档：fixtures, parametrize, async测试
  - FastAPI TestClient用法

  **WHY Each Reference Matters**:
  - 现有测试文件展示了项目的测试约定
  - 需要正确使用TestClient进行API测试

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 所有测试通过: `pytest tests/api/test_document_*.py` → PASS
  - [ ] 覆盖率报告: `pytest --cov=src/api --cov-report=term-missing`

  **QA Scenarios**:

  ```
  Scenario: 运行所有文档管理测试
    Tool: Bash (pytest)
    Preconditions: 所有测试文件就绪
    Steps:
      1. 运行 `pytest tests/api/test_document_list.py -v`
      2. 运行 `pytest tests/api/test_document_delete.py -v`
      3. 运行 `pytest tests/api/test_document_stats.py -v`
      4. 验证所有测试通过
    Expected Result: 全部测试通过，无失败
    Evidence: .sisyphus/evidence/task-6-all-tests-pass.txt

  Scenario: 测试覆盖率验证
    Tool: Bash (pytest)
    Preconditions: 测试文件就绪
    Steps:
      1. 运行 `pytest --cov=src/api/main.py --cov-report=term-missing`
      2. 检查覆盖率报告
      3. 验证新端点覆盖率 >80%
    Expected Result: 达到覆盖率要求
    Evidence: .sisyphus/evidence/task-6-coverage-report.txt
  ```

  **Evidence to Capture**:
  - [ ] 测试通过输出
  - [ ] 覆盖率报告

  **Commit**: YES
  - Message: `test(api): add document management unit tests`
  - Files: `tests/api/test_document_list.py`, `tests/api/test_document_delete.py`, `tests/api/test_document_stats.py`
  - Pre-commit: `pytest tests/api/test_document_*.py`

- [ ] 7. 更新API文档端点说明

  **What to do**:
  - 在 `src/api/main.py` 中添加新端点的OpenAPI文档字符串
  - 更新项目的API文档（如果有）
  - 确保文档包含请求/响应示例、错误码说明
  - 添加端点使用的注意事项（如原子性保证）
  - 更新README中的API端点列表

  **Must NOT do**:
  - 编写冗长不必要的文档
  - 忽略重要注意事项

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写任务
  - **Skills**: []
    - 无需特殊技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-6)
  - **Blocks**: None
  - **Blocked By**: Tasks 3, 4, 5 (需要端点实现完成)

  **References**:

  **Pattern References**:
  - `src/api/main.py:354-380` - `upload_document` 端点的文档字符串
  - `src/api/main.py:382-422` - `process_documents` 端点的文档

  **Documentation References**:
  - FastAPI OpenAPI文档规范
  - Markdown格式约定

  **WHY Each Reference Matters**:
  - 现有端点的文档展示了项目的文档标准
  - 需要保持一致的文档风格

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 文档字符串语法正确
  - [ ] OpenAPI文档可访问

  **QA Scenarios**:

  ```
  Scenario: 验证API文档可访问
    Tool: Bash (curl)
    Preconditions: API服务运行中
    Steps:
      1. 访问 `http://localhost:8000/docs`
      2. 验证新端点显示在文档中
      3. 点击端点查看详细文档
      4. 验证请求/响应示例正确
    Expected Result: 文档正确显示，无错误
    Evidence: .sisyphus/evidence/task-7-api-docs-screenshot.png (使用Playwright截图)

  Scenario: 验证OpenAPI JSON
    Tool: Bash (curl)
    Preconditions: API服务运行中
    Steps:
      1. 访问 `http://localhost:8000/openapi.json`
      2. 解析JSON响应
      3. 验证新端点在paths中存在
      4. 验证端点文档字段完整
    Expected Result: OpenAPI规范包含新端点
    Evidence: .sisyphus/evidence/task-7-openapi-json.json
  ```

  **Evidence to Capture**:
  - [ ] API文档界面截图
  - [ ] OpenAPI JSON验证

  **Commit**: YES
  - Message: `docs(api): update documentation for document management endpoints`
  - Files: `src/api/main.py`, `README.md`
  - Pre-commit: `python -c "import src.api.main; print('Docs check passed')"`

- [ ] 8. 分析前端app.py结构

  **What to do**:
  - 阅读 `src/frontend/app.py` 理解现有UI结构
  - 识别文档管理功能的最佳插入位置
  - 分析现有组件模式（上传、处理、查询等）
  - 确定新组件的布局和样式方案
  - 记录发现的结构和模式供后续任务使用

  **Must NOT do**:
  - 修改现有前端代码
  - 添加不必要的样式改动

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 代码分析和文档记录
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: 前端结构分析和UI设计

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 9-14)
  - **Blocks**: Task 9 (组件函数创建)
  - **Blocked By**: None (可以立即开始)

  **References**:

  **Pattern References**:
  - `src/frontend/app.py` - 完整的Streamlit应用结构
  - 现有组件：上传区域、处理按钮、查询界面

  **UI/UX References**:
  - Streamlit组件库文档
  - 项目现有的UI设计模式

  **WHY Each Reference Matters**:
  - 需要理解现有布局以保持一致性
  - 现有组件展示了项目的UI约定

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 分析文档创建: `.sisyphus/evidence/task-8-frontend-analysis.md`
  - [ ] 布局方案确定

  **QA Scenarios**:

  ```
  Scenario: 验证前端结构理解
    Tool: Bash (python script)
    Preconditions: 前端文件存在
    Steps:
      1. 读取 `src/frontend/app.py`
      2. 提取主要组件和布局信息
      3. 生成结构分析报告
      4. 验证报告包含关键信息
    Expected Result: 成功生成前端结构分析
    Evidence: .sisyphus/evidence/task-8-frontend-analysis.md

  Scenario: 验证组件识别
    Tool: Bash (python script)
    Preconditions: 前端文件存在
    Steps:
      1. 识别现有文档相关组件（上传、处理）
      2. 确定文档管理功能的最佳位置
      3. 记录建议的布局方案
    Expected Result: 明确的组件插入位置建议
    Evidence: .sisyphus/evidence/task-8-layout-suggestion.md
  ```

  **Evidence to Capture**:
  - [ ] 前端结构分析文档
  - [ ] 布局建议文档

  **Commit**: NO (分析任务，不产生代码变更)

- [ ] 9. 创建文档管理组件函数

  **What to do**:
  - 在 `src/frontend/app.py` 中创建新的文档管理组件函数：
    - `render_document_list_table(documents)` - 显示文档表格
    - `render_delete_confirmation_dialog(filename)` - 删除确认对话框
    - `render_document_stats_panel(stats)` - 统计面板
    - `render_batch_operations()` - 批量操作控件
  - 遵循现有函数命名和结构约定
  - 添加必要的参数和返回值说明

  **Must NOT do**:
  - 实现具体UI渲染（留待后续任务）
  - 添加业务逻辑（API调用等）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端组件设计，需要UI/UX考虑
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: 组件设计和UI最佳实践

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8, 10-14)
  - **Blocks**: Task 10 (表格显示), Task 11 (删除按钮), Task 12 (统计面板)
  - **Blocked By**: Task 8 (需要前端结构分析)

  **References**:

  **Pattern References**:
  - `src/frontend/app.py` 中的现有函数：`render_upload_section()`, `render_query_section()`
  - 函数签名和文档字符串模式

  **Component References**:
  - Streamlit组件API：`st.dataframe`, `st.columns`, `st.button`
  - 对话框模式：`st.dialog`, `st.warning`, 确认流程

  **WHY Each Reference Matters**:
  - 需要保持一致的函数结构和命名
  - Streamlit文档确保正确使用组件

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 函数定义语法正确
  - [ ] 无运行时错误

  **QA Scenarios**:

  ```
  Scenario: 验证组件函数创建
    Tool: Bash (python script)
    Preconditions: 前端文件存在
    Steps:
      1. 导入 `src/frontend/app.py`
      2. 验证新函数存在且可调用
      3. 检查函数签名和文档字符串
      4. 验证无语法错误
    Expected Result: 函数创建成功，无语法错误
    Evidence: .sisyphus/evidence/task-9-function-creation.txt

  Scenario: 测试函数基本调用
    Tool: Bash (python script)
    Preconditions: 函数已创建
    Steps:
      1. 使用模拟数据调用各函数
      2. 验证函数返回预期值（如None或占位符）
      3. 验证无异常抛出
    Expected Result: 函数可调用，无错误
    Evidence: .sisyphus/evidence/task-9-function-call-test.txt
  ```

  **Evidence to Capture**:
  - [ ] 函数存在验证
  - [ ] 函数调用测试

  **Commit**: YES
  - Message: `feat(frontend): add document management component functions`
  - Files: `src/frontend/app.py`
  - Pre-commit: `python -c "import src.frontend.app; print('Frontend import check passed')"`

- [ ] 10. 实现文档列表表格显示

  **What to do**:
  - 实现 `render_document_list_table(documents)` 函数
  - 使用 Streamlit `st.dataframe` 显示文档列表
  - 列包括：文件名、大小、格式、修改时间、向量状态、操作按钮
  - 添加排序和筛选功能（按名称、大小、状态）
  - 实现分页（如果文档数量多）
  - 添加"刷新列表"按钮

  **Must NOT do**:
  - 实现删除功能（留待Task 11）
  - 添加过多复杂交互

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 数据表格UI实现，需要良好的视觉设计
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: 表格UI设计和用户体验
    - `playwright`: 前端自动化测试验证

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-9, 11-14)
  - **Blocks**: Task 13 (API集成)
  - **Blocked By**: Task 9 (需要组件函数)

  **References**:

  **Pattern References**:
  - `src/frontend/app.py` 中的现有UI组件
  - Streamlit `st.dataframe` 示例

  **UI References**:
  - Streamlit数据表格文档：列格式化、排序、样式
  - 分页组件模式

  **WHY Each Reference Matters**:
  - 需要与现有UI风格一致
  - Streamlit文档确保正确使用表格组件

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 表格显示功能完整
  - [ ] 无UI错误

  **QA Scenarios**:

  ```
  Scenario: 验证表格显示
    Tool: Playwright
    Preconditions: 1. Streamlit应用运行中 2. 有测试文档数据
    Steps:
      1. 导航到文档管理界面
      2. 验证表格显示
      3. 验证列标题正确
      4. 验证文档数据正确显示
      5. 截图验证UI
    Expected Result: 表格正确显示文档数据
    Evidence: .sisyphus/evidence/task-10-table-display.png

  Scenario: 测试表格排序
    Tool: Playwright
    Preconditions: 表格显示正常
    Steps:
      1. 点击文件名列标题排序
      2. 验证排序生效
      3. 点击大小列标题排序
      4. 验证排序生效
    Expected Result: 排序功能正常工作
    Evidence: .sisyphus/evidence/task-10-table-sorting.png

  Scenario: 测试空状态显示
    Tool: Playwright
    Preconditions: 无文档数据
    Steps:
      1. 清空文档目录
      2. 刷新界面
      3. 验证表格显示空状态信息
    Expected Result: 优雅的空状态处理
    Evidence: .sisyphus/evidence/task-10-empty-state.png
  ```

  **Evidence to Capture**:
  - [ ] 表格显示截图
  - [ ] 排序功能截图
  - [ ] 空状态截图

  **Commit**: YES
  - Message: `feat(frontend): implement document list table display`
  - Files: `src/frontend/app.py`
  - Pre-commit: `streamlit run src/frontend/app.py & sleep 5 && pkill -f streamlit`

- [ ] 11. 实现删除按钮和确认对话框

  **What to do**:
  - 在文档列表表格中添加"删除"按钮列
  - 实现 `render_delete_confirmation_dialog(filename)` 函数
  - 点击删除按钮弹出确认对话框，显示文件名和警告信息
  - 对话框选项："确认删除"和"取消"
  - 添加删除进度提示（处理中、成功、失败）
  - 实现删除后的列表自动刷新

  **Must NOT do**:
  - 无确认的直接删除
  - 忽略删除失败的错误处理

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 交互式对话框和确认流程，需要良好的用户体验设计
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: 对话框设计和用户流程
    - `playwright`: 自动化测试验证交互

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-10, 12-14)
  - **Blocks**: Task 15 (集成测试)
  - **Blocked By**: Task 9 (需要组件函数), Task 4 (需要删除API)

  **References**:

  **Pattern References**:
  - 现有Streamlit对话框模式（如果有）
  - 确认流程最佳实践

  **UI References**:
  - Streamlit对话框组件：`st.dialog`, `st.warning`, `st.error`
  - 按钮状态管理和禁用模式

  **WHY Each Reference Matters**:
  - 需要一致的对话框风格
  - 确认流程必须清晰且防止误操作

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 删除确认流程完整
  - [ ] 错误处理完善

  **QA Scenarios**:

  ```
  Scenario: 测试删除确认对话框
    Tool: Playwright
    Preconditions: 1. 应用运行中 2. 有测试文档
    Steps:
      1. 点击文档列表中的删除按钮
      2. 验证确认对话框弹出
      3. 验证对话框显示正确的文件名
      4. 点击取消按钮
      5. 验证文档未被删除
    Expected Result: 确认对话框正常工作，取消功能有效
    Evidence: .sisyphus/evidence/task-11-dialog-cancel.png

  Scenario: 测试确认删除流程
    Tool: Playwright
    Preconditions: 1. 应用运行中 2. 有测试文档
    Steps:
      1. 点击删除按钮
      2. 在对话框中点击确认删除
      3. 验证删除进度提示显示
      4. 验证删除成功提示显示
      5. 验证文档从列表中消失
    Expected Result: 删除流程完整，UI反馈正确
    Evidence: .sisyphus/evidence/task-11-delete-success.png

  Scenario: 测试删除失败处理
    Tool: Playwright
    Preconditions: 模拟删除API失败
    Steps:
      1. 触发删除操作
      2. 模拟API返回错误
      3. 验证错误提示显示
      4. 验证文档仍在列表中
    Expected Result: 优雅的错误处理，用户得到明确反馈
    Evidence: .sisyphus/evidence/task-11-delete-error.png
  ```

  **Evidence to Capture**:
  - [ ] 对话框截图
  - [ ] 删除成功流程截图
  - [ ] 删除错误处理截图

  **Commit**: YES
  - Message: `feat(frontend): implement delete confirmation dialog`
  - Files: `src/frontend/app.py`
  - Pre-commit: `streamlit run src/frontend/app.py & sleep 5 && pkill -f streamlit`

- [ ] 12. 实现文档统计面板

  **What to do**:
  - 实现 `render_document_stats_panel(stats)` 函数
  - 显示关键统计信息：文档总数、已处理数、总大小、平均chunks数
  - 使用Streamlit指标卡片（`st.metric`）或进度条可视化
  - 添加"刷新统计"按钮
  - 实现自动刷新（可选，如每30秒）
  - 添加趋势指示器（与上次统计比较）

  **Must NOT do**:
  - 过度复杂的可视化
  - 实时更新频率过高

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 数据可视化面板设计，需要良好的信息展示
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: 数据可视化和面板设计
    - `playwright`: 自动化测试验证

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-11, 13-14)
  - **Blocks**: Task 15 (集成测试)
  - **Blocked By**: Task 9 (需要组件函数), Task 5 (需要统计API)

  **References**:

  **Pattern References**:
  - 现有Streamlit指标显示模式
  - 数据面板设计最佳实践

  **UI References**:
  - Streamlit `st.metric` 组件文档
  - 进度条和可视化组件

  **WHY Each Reference Matters**:
  - 需要一致的视觉风格
  - 统计信息需要清晰易读

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 统计面板显示完整
  - [ ] 数据刷新功能正常

  **QA Scenarios**:

  ```
  Scenario: 验证统计面板显示
    Tool: Playwright
    Preconditions: 1. 应用运行中 2. 有文档数据
    Steps:
      1. 导航到文档管理界面
      2. 验证统计面板显示
      3. 验证统计数值正确
      4. 截图验证UI
    Expected Result: 统计面板正确显示数据
    Evidence: .sisyphus/evidence/task-12-stats-panel.png

  Scenario: 测试刷新功能
    Tool: Playwright
    Preconditions: 统计面板显示正常
    Steps:
      1. 记录当前统计数值
      2. 添加新文档
      3. 点击刷新按钮
      4. 验证统计数值更新
    Expected Result: 刷新功能正常工作
    Evidence: .sisyphus/evidence/task-12-refresh-test.png

  Scenario: 测试空状态统计
    Tool: Playwright
    Preconditions: 无文档数据
    Steps:
      1. 清空文档目录
      2. 刷新界面
      3. 验证统计面板显示零值
    Expected Result: 空状态统计显示正确
    Evidence: .sisyphus/evidence/task-12-empty-stats.png
  ```

  **Evidence to Capture**:
  - [ ] 统计面板截图
  - [ ] 刷新功能截图
  - [ ] 空状态截图

  **Commit**: YES
  - Message: `feat(frontend): implement document statistics panel`
  - Files: `src/frontend/app.py`
  - Pre-commit: `streamlit run src/frontend/app.py & sleep 5 && pkill -f streamlit`

- [ ] 13. 集成API调用和状态管理

  **What to do**:
  - 在组件函数中添加API调用逻辑：
    - 文档列表API调用 (`GET /api/v1/documents/list`)
    - 文档删除API调用 (`DELETE /api/v1/documents/{filename}`)
    - 文档统计API调用 (`GET /api/v1/documents/stats`)
  - 实现状态管理：加载状态、错误状态、成功状态
  - 添加请求重试机制（失败时重试1次）
  - 实现缓存策略（列表和统计缓存60秒）
  - 添加请求超时处理（10秒）

  **Must NOT do**:
  - 硬编码API地址（使用配置或相对路径）
  - 忽略网络错误处理

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: API集成和状态管理，需要复杂逻辑处理
  - **Skills**: [`frontend-ui-ux`, `superpowers/systematic-debugging`]
    - `frontend-ui-ux`: 状态管理和用户反馈设计
    - `systematic-debugging`: 复杂错误场景处理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-12, 14)
  - **Blocks**: Task 15 (集成测试)
  - **Blocked By**: Tasks 3, 4, 5 (需要API端点), Tasks 9-12 (需要UI组件)

  **References**:

  **Pattern References**:
  - 现有前端API调用模式（查询、上传等）
  - 状态管理最佳实践

  **API References**:
  - Python `requests` 或 `httpx` 库用法
  - 异步请求处理模式

  **WHY Each Reference Matters**:
  - 需要与现有API调用模式一致
  - 状态管理必须健壮可靠

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] API调用成功
  - [ ] 状态管理完善

  **QA Scenarios**:

  ```
  Scenario: 测试文档列表API集成
    Tool: Playwright + Bash
    Preconditions: 1. 应用运行中 2. API服务运行中
    Steps:
      1. 打开文档管理界面
      2. 监控网络请求
      3. 验证文档列表API被调用
      4. 验证数据正确显示在表格中
    Expected Result: API集成成功，数据正确显示
    Evidence: .sisyphus/evidence/task-13-list-api-integration.png

  Scenario: 测试API错误处理
    Tool: Playwright + Bash
    Preconditions: 模拟API服务宕机
    Steps:
      1. 停止API服务
      2. 打开文档管理界面
      3. 验证错误提示显示
      4. 验证UI降级处理（如显示缓存数据或空状态）
    Expected Result: 优雅的错误处理，用户得到明确反馈
    Evidence: .sisyphus/evidence/task-13-api-error-handling.png

  Scenario: 测试缓存机制
    Tool: Playwright + Bash
    Preconditions: 应用运行正常
    Steps:
      1. 打开界面，记录API调用次数
      2. 快速刷新界面多次
      3. 验证API调用次数合理（有缓存）
      4. 等待缓存过期后刷新
      5. 验证API再次被调用
    Expected Result: 缓存机制正常工作
    Evidence: .sisyphus/evidence/task-13-cache-test.txt
  ```

  **Evidence to Capture**:
  - [ ] API集成成功截图
  - [ ] 错误处理截图
  - [ ] 缓存测试日志

  **Commit**: YES
  - Message: `feat(frontend): integrate document management APIs with state management`
  - Files: `src/frontend/app.py`
  - Pre-commit: `streamlit run src/frontend/app.py & sleep 5 && pkill -f streamlit`

- [ ] 14. 添加前端错误处理

  **What to do**:
  - 为所有API调用添加统一的错误处理层
  - 实现错误分类：网络错误、API错误、数据错误、超时
  - 添加用户友好的错误提示信息（非技术术语）
  - 实现错误恢复机制：重试、降级、回退
  - 添加错误日志记录（前端控制台）
  - 实现全局错误边界（防止整个应用崩溃）

  **Must NOT do**:
  - 显示原始技术错误给用户
  - 忽略错误导致不一致状态

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 复杂的错误处理系统，需要全面考虑
  - **Skills**: [`superpowers/systematic-debugging`, `frontend-ui-ux`]
    - `systematic-debugging`: 错误分类和处理策略
    - `frontend-ui-ux`: 用户友好的错误展示

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-13)
  - **Blocks**: Task 15 (集成测试)
  - **Blocked By**: Task 13 (需要API集成)

  **References**:

  **Pattern References**:
  - 现有前端错误处理模式
  - 错误边界和恢复最佳实践

  **Error Handling References**:
  - Streamlit错误显示组件：`st.error`, `st.warning`
  - 错误分类和处理策略

  **WHY Each Reference Matters**:
  - 需要与现有错误处理一致
  - 用户友好的错误信息至关重要

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 错误处理覆盖所有场景
  - [ ] 应用不会因错误而崩溃

  **QA Scenarios**:

  ```
  Scenario: 测试网络错误处理
    Tool: Playwright + Bash
    Preconditions: 断开网络连接
    Steps:
      1. 打开文档管理界面
      2. 验证网络错误提示显示
      3. 验证UI仍然可用（降级模式）
      4. 恢复网络连接
      5. 验证自动恢复或提供重试按钮
    Expected Result: 优雅的网络错误处理
    Evidence: .sisyphus/evidence/task-14-network-error.png

  Scenario: 测试API返回错误
    Tool: Playwright + Bash
    Preconditions: 模拟API返回500错误
    Steps:
      1. 触发文档列表请求
      2. 验证API错误提示显示
      3. 验证错误信息用户友好
      4. 验证重试机制可用
    Expected Result: API错误正确处理
    Evidence: .sisyphus/evidence/task-14-api-error.png

  Scenario: 测试数据格式错误
    Tool: Playwright + Bash
    Preconditions: 模拟API返回错误格式数据
    Steps:
      1. 触发API请求
      2. 验证数据解析错误处理
      3. 验证降级数据显示
    Expected Result: 数据错误正确处理
    Evidence: .sisyphus/evidence/task-14-data-error.png
  ```

  **Evidence to Capture**:
  - [ ] 各种错误场景截图
  - [ ] 错误恢复验证

  **Commit**: YES
  - Message: `feat(frontend): add comprehensive error handling`
  - Files: `src/frontend/app.py`
  - Pre-commit: `streamlit run src/frontend/app.py & sleep 5 && pkill -f streamlit`

- [ ] 15. 端到端集成测试

  **What to do**:
  - 创建端到端测试脚本 `scripts/test_document_management_workflow.py`
  - 测试完整工作流：启动服务 → 上传文档 → 处理文档 → 查看列表 → 删除文档 → 验证清理
  - 验证文件系统和向量存储的一致性
  - 测试并发场景：同时上传和删除
  - 添加测试数据清理（测试后恢复环境）
  - 生成测试报告和性能指标

  **Must NOT do**:
  - 破坏生产数据
  - 忽略测试环境隔离

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 复杂的端到端测试，需要系统级理解
  - **Skills**: [`superpowers/systematic-debugging`, `superpowers/test-driven-development`]
    - `systematic-debugging`: 测试失败分析和调试
    - `test-driven-development`: 测试设计和实现

  **Parallelization**:
  - **Can Run In Parallel**: NO (需要所有前置任务完成)
  - **Parallel Group**: Wave 3 (with Tasks 16-19)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 1-14 (需要所有功能实现)

  **References**:

  **Pattern References**:
  - 现有端到端测试模式（如果有）
  - 工作流测试最佳实践

  **Testing References**:
  - Python测试框架：`pytest`, `unittest`
  - 服务启动和停止管理

  **WHY Each Reference Matters**:
  - 需要与现有测试框架集成
  - 工作流测试必须全面覆盖

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 端到端测试通过: `python scripts/test_document_management_workflow.py`
  - [ ] 测试报告生成

  **QA Scenarios**:

  ```
  Scenario: 运行端到端工作流测试
    Tool: Bash (python script)
    Preconditions: 测试环境就绪
    Steps:
      1. 运行端到端测试脚本
      2. 验证所有测试步骤通过
      3. 检查测试报告输出
      4. 验证环境清理完成
    Expected Result: 端到端测试通过，环境干净
    Evidence: .sisyphus/evidence/task-15-e2e-test-report.txt

  Scenario: 测试失败分析
    Tool: Bash (python script)
    Preconditions: 模拟测试失败场景
    Steps:
      1. 注入一个故障（如向量存储不可用）
      2. 运行端到端测试
      3. 验证测试正确捕获失败
      4. 验证错误信息明确
    Expected Result: 测试失败被正确识别和报告
    Evidence: .sisyphus/evidence/task-15-failure-analysis.txt
  ```

  **Evidence to Capture**:
  - [ ] 端到端测试报告
  - [ ] 失败分析报告

  **Commit**: YES
  - Message: `test: add end-to-end document management workflow tests`
  - Files: `scripts/test_document_management_workflow.py`
  - Pre-commit: `python scripts/test_document_management_workflow.py`

- [ ] 16. 一致性验证测试

  **What to do**:
  - 创建一致性验证脚本 `scripts/verify_document_vector_consistency.py`
  - 验证文件系统和向量存储之间的一致性：
    - 每个文件在向量存储中有对应向量
    - 删除文件后向量也被删除
    - 无孤儿向量（向量对应不存在的文件）
  - 添加修复工具（可选，标记不一致并报告）
  - 集成到健康检查端点（可选）

  **Must NOT do**:
  - 自动修复不一致而不报告
  - 忽略边缘情况

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 数据一致性验证，需要深入理解系统
  - **Skills**: [`superpowers/systematic-debugging`]
    - `systematic-debugging`: 不一致问题分析和解决

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 15, 17-19)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 1, 3, 4 (需要向量存储和API)

  **References**:

  **Pattern References**:
  - 现有数据验证模式（如果有）
  - 一致性检查算法

  **Data References**:
  - 文件系统遍历：`os.walk`, `pathlib`
  - 向量存储查询模式

  **WHY Each Reference Matters**:
  - 需要高效的文件系统遍历
  - 向量存储查询必须正确

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 一致性验证脚本通过测试
  - [ ] 检测到故意引入的不一致

  **QA Scenarios**:

  ```
  Scenario: 运行一致性验证
    Tool: Bash (python script)
    Preconditions: 系统有文档数据
    Steps:
      1. 运行一致性验证脚本
      2. 验证无不一致报告
      3. 故意创建不一致（如删除文件不删向量）
      4. 再次运行验证脚本
      5. 验证检测到不一致
    Expected Result: 一致性验证正确工作
    Evidence: .sisyphus/evidence/task-16-consistency-verification.txt

  Scenario: 测试大规模数据一致性
    Tool: Bash (python script)
    Preconditions: 创建大量测试文档
    Steps:
      1. 创建100个测试文档并处理
      2. 运行一致性验证
      3. 验证性能可接受（<30秒）
      4. 验证结果准确
    Expected Result: 大规模数据一致性验证可行
    Evidence: .sisyphus/evidence/task-16-scale-test.txt
  ```

  **Evidence to Capture**:
  - [ ] 一致性验证报告
  - [ ] 大规模测试报告

  **Commit**: YES
  - Message: `test: add document-vector consistency verification`
  - Files: `scripts/verify_document_vector_consistency.py`
  - Pre-commit: `python scripts/verify_document_vector_consistency.py`

- [ ] 17. 错误场景测试

  **What to do**:
  - 创建错误场景测试套件 `tests/error_scenarios/test_document_management_errors.py`
  - 测试各种错误情况：
    - 文件系统权限错误
    - 向量存储连接失败
    - 网络超时
    - 无效文件名/路径
    - 并发冲突（同时删除同一文件）
  - 验证系统优雅处理错误（不崩溃，有明确错误信息）
  - 验证错误恢复机制

  **Must NOT do**:
  - 忽略罕见错误场景
  - 不测试恢复机制

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 全面的错误场景覆盖，需要创造性测试设计
  - **Skills**: [`superpowers/systematic-debugging`]
    - `systematic-debugging`: 错误场景设计和分析

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 15-16, 18-19)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 1-14 (需要功能实现)

  **References**:

  **Pattern References**:
  - 现有错误测试模式
  - 故障注入技术

  **Testing References**:
  - pytest故障注入插件
  - 模拟库：`unittest.mock`

  **WHY Each Reference Matters**:
  - 需要与现有测试框架集成
  - 故障注入必须安全可控

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 错误场景测试通过
  - [ ] 错误处理覆盖率>90%

  **QA Scenarios**:

  ```
  Scenario: 运行错误场景测试套件
    Tool: Bash (pytest)
    Preconditions: 测试文件就绪
    Steps:
      1. 运行错误场景测试：`pytest tests/error_scenarios/test_document_management_errors.py -v`
      2. 验证所有测试通过
      3. 检查错误处理日志
    Expected Result: 错误场景测试全部通过
    Evidence: .sisyphus/evidence/task-17-error-scenarios.txt

  Scenario: 测试并发冲突处理
    Tool: Bash (python script)
    Preconditions: 系统运行中
    Steps:
      1. 同时发起多个删除同一文件的请求
      2. 验证系统正确处理冲突（如返回适当错误或序列化处理）
      3. 验证数据一致性不受破坏
    Expected Result: 并发冲突正确处理
    Evidence: .sisyphus/evidence/task-17-concurrency-test.txt
  ```

  **Evidence to Capture**:
  - [ ] 错误场景测试输出
  - [ ] 并发测试报告

  **Commit**: YES
  - Message: `test: add error scenario tests for document management`
  - Files: `tests/error_scenarios/test_document_management_errors.py`
  - Pre-commit: `pytest tests/error_scenarios/test_document_management_errors.py`

- [ ] 18. 性能测试 (批量操作)

  **What to do**:
  - 创建性能测试脚本 `scripts/benchmark_document_management.py`
  - 测试关键操作的性能：
    - 文档列表API响应时间（不同文档数量）
    - 文档删除API响应时间（单个和批量）
    - 前端表格渲染性能（大量文档）
    - 一致性验证性能（大规模数据）
  - 收集性能指标：响应时间、内存使用、CPU使用
  - 建立性能基线（供未来回归测试）
  - 识别性能瓶颈并提出优化建议

  **Must NOT do**:
  - 影响生产环境
  - 忽略资源使用监控

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 性能测试和分析，需要系统级理解
  - **Skills**: [`superpowers/systematic-debugging`]
    - `systematic-debugging`: 性能问题分析和优化

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 15-17, 19)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 1-14 (需要功能实现)

  **References**:

  **Pattern References**:
  - 现有性能测试模式（如果有）
  - 性能测试最佳实践

  **Performance References**:
  - Python性能测试工具：`timeit`, `memory_profiler`
  - 性能监控指标收集

  **WHY Each Reference Matters**:
  - 需要准确的性能测量
  - 性能基线对未来回归测试重要

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 性能测试完成并生成报告
  - [ ] 关键操作满足性能要求

  **QA Scenarios**:

  ```
  Scenario: 运行性能测试套件
    Tool: Bash (python script)
    Preconditions: 测试环境就绪
    Steps:
      1. 运行性能测试脚本
      2. 收集性能指标
      3. 生成性能报告
      4. 验证关键操作性能达标
    Expected Result: 性能测试完成，报告生成
    Evidence: .sisyphus/evidence/task-18-performance-report.txt

  Scenario: 测试大规模文档列表性能
    Tool: Bash (python script)
    Preconditions: 创建1000个测试文档
    Steps:
      1. 调用文档列表API
      2. 测量响应时间
      3. 验证响应时间<2秒（可调整）
      4. 验证内存使用合理
    Expected Result: 大规模文档列表性能可接受
    Evidence: .sisyphus/evidence/task-18-scale-performance.txt
  ```

  **Evidence to Capture**:
  - [ ] 性能测试报告
  - [ ] 大规模性能测试结果

  **Commit**: YES
  - Message: `perf: add document management performance benchmarks`
  - Files: `scripts/benchmark_document_management.py`
  - Pre-commit: `python scripts/benchmark_document_management.py --quick`

- [ ] 19. 文档更新和发布说明

  **What to do**:
  - 更新项目文档：
    - README.md：添加文档管理功能说明
    - API文档：更新端点列表和示例
    - 用户指南：添加文档管理使用说明
  - 创建发布说明：`CHANGELOG.md` 或 release notes
  - 更新配置说明（如果有新配置）
  - 添加故障排除指南（常见问题）
  - 验证所有文档链接有效

  **Must NOT do**:
  - 复制代码注释到用户文档
  - 忽略文档可读性

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写和整理
  - **Skills**: []
    - 无需特殊技能

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 15-18)
  - **Blocks**: Final Verification
  - **Blocked By**: Tasks 1-18 (需要功能实现完成)

  **References**:

  **Pattern References**:
  - 现有项目文档风格
  - 发布说明格式

  **Documentation References**:
  - Markdown语法和最佳实践
  - 技术文档编写指南

  **WHY Each Reference Matters**:
  - 需要保持文档风格一致
  - 用户文档必须清晰易懂

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] 文档更新完成
  - [ ] 无拼写/语法错误

  **QA Scenarios**:

  ```
  Scenario: 验证文档更新
    Tool: Bash (检查文件)
    Preconditions: 文档文件存在
    Steps:
      1. 检查README.md包含新功能说明
      2. 检查API文档更新
      3. 检查用户指南更新
      4. 验证无死链接
    Expected Result: 文档完整更新
    Evidence: .sisyphus/evidence/task-19-documentation-check.txt

  Scenario: 验证发布说明
    Tool: Bash (检查文件)
    Preconditions: CHANGELOG.md存在
    Steps:
      1. 检查发布说明包含新功能
      2. 验证版本号正确
      3. 验证说明清晰完整
    Expected Result: 发布说明正确
    Evidence: .sisyphus/evidence/task-19-changelog-check.txt
  ```

  **Evidence to Capture**:
  - [ ] 文档检查报告
  - [ ] 发布说明验证

  **Commit**: YES
  - Message: `docs: update documentation for document management feature`
  - Files: `README.md`, `docs/`, `CHANGELOG.md`
  - Pre-commit: `markdownlint README.md docs/*.md 2>/dev/null || true`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 3 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **代码质量审查** — `unspecified-high`
  读取所有修改的文件。运行 `black --check`, `isort --check`, `mypy src/`。检查代码风格一致性：命名约定、函数长度、注释质量、重复代码。验证无 `# TODO` 或 `# FIXME` 遗留。检查AI slop：过度抽象、无用的泛型、过度的错误处理。确保错误处理一致且适当。检查安全漏洞：硬编码密钥、路径遍历风险。输出：`代码风格 [通过/失败] | 类型检查 [通过/失败] | 安全问题 [0/N] | 遗留TODO [0/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **安全性审查** — `unspecified-high`
  检查所有API端点：认证/授权（如果有）、输入验证、路径遍历防护、错误信息泄露。检查文件操作：安全路径处理、权限检查。检查向量存储操作：查询注入防护。检查前端：XSS防护、数据暴露。运行安全扫描工具（如 `bandit`）。输出：`API安全 [通过/失败] | 文件安全 [通过/失败] | 前端安全 [通过/失败] | 工具扫描 [通过/失败] | VERDICT`

- [ ] F3. **用户验收测试模拟** — `unspecified-high` (+ `playwright` skill)
  模拟真实用户场景：启动所有服务（API + 前端）。执行完整工作流：上传文档 → 处理 → 查看列表 → 删除文档 → 验证统计。测试边界情况：大文件、特殊字符文件名、并发操作。验证UI响应性和可用性。收集性能指标：页面加载时间、API响应时间。输出：`工作流 [N/N通过] | 边界测试 [N/N] | 性能指标 [达标/未达标] | VERDICT`

---

## Commit Strategy

- **Wave 1完成后**: 提交所有后端变更
  - `git commit -m "feat(backend): add document management APIs"`
  - 包含: `src/api/main.py`, `src/core/vector_store.py`, `tests/api/`, `tests/core/`
  - 预提交检查: `pytest tests/api/test_document_*.py tests/core/test_vector_store_extended.py`

- **Wave 2完成后**: 提交前端变更
  - `git commit -m "feat(frontend): add document management UI"`
  - 包含: `src/frontend/app.py`
  - 预提交检查: `streamlit run src/frontend/app.py & sleep 3 && pkill -f streamlit`

- **Wave 3完成后**: 提交测试和文档
  - `git commit -m "test(docs): add integration tests and documentation"`
  - 包含: 集成测试、文档更新、性能测试
  - 预提交检查: `pytest tests/integration/`

- **Final Verification完成后**: 标签发布
  - `git tag -a v1.1.0 -m "Document management feature release"`
  - 推送标签: `git push origin v1.1.0`

---

## Success Criteria

### Verification Commands
```bash
# 1. 后端API测试
pytest tests/api/test_document_list.py tests/api/test_document_delete.py tests/api/test_document_stats.py -v
# 预期: 所有测试通过

# 2. 前端启动测试
streamlit run src/frontend/app.py --server.headless true --server.runOnSave false &
sleep 5
curl -s http://localhost:8501 | grep -q "本地知识库系统"
# 预期: 成功检测到Streamlit应用

# 3. 端到端工作流测试
python scripts/test_document_management_workflow.py
# 预期: 工作流测试通过

# 4. 一致性验证
python scripts/verify_document_vector_consistency.py
# 预期: 无不一致发现
```

### Final Checklist
- [ ] 所有"Must Have"功能实现：
  - [ ] 文档列表查看功能
  - [ ] 文档删除功能（文件+向量）
  - [ ] 一致性保证（文件删除必须清理向量）
  - [ ] 前端用户确认对话框
- [ ] 所有"Must NOT Have"避免：
  - [ ] 无自动批量删除（需用户确认）
  - [ ] 无不完整的向量清理
  - [ ] 无破坏性操作无确认
  - [ ] 无忽略错误处理和数据一致性
- [ ] 所有测试通过（单元、集成、端到端）
- [ ] 代码质量审查通过（无严重问题）
- [ ] 安全性审查通过（无高危漏洞）
- [ ] 用户验收测试模拟通过（工作流完整）

