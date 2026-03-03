# Ollama 安装与配置指南

## 📦 Ollama 简介

Ollama 是一个开源的本地大模型运行框架，支持一键部署和运行多种开源大模型。对于本地知识库项目，我们使用 Ollama 来运行 DeepSeek-V2-Lite 模型。

---

## 🚀 安装步骤

### 1. 下载 Ollama
访问官方下载页面：**[https://ollama.com/download/windows](https://ollama.com/download/windows)**

下载 Windows 安装包（.exe 文件），双击运行安装。

### 2. 安装后验证
安装完成后，打开命令提示符或 PowerShell，运行：
```bash
ollama --version
```

应该显示类似 `ollama version 0.1.xx` 的版本信息。

### 3. 启动 Ollama 服务
```bash
ollama serve
```

服务默认运行在 `http://localhost:11434`

### 4. 下载 DeepSeek-V2-Lite 模型
```bash
# 下载 16B 参数的 4-bit 量化版本（推荐）
ollama pull deepseek-v2-lite:16b-q4_K_M

# 或下载 7B 参数的轻量版本
ollama pull deepseek-v2-lite:7b-q4_K_M
```

### 5. 验证模型
```bash
# 测试模型响应
ollama run deepseek-v2-lite "你好，介绍一下你自己"
```

---

## ⚙️ 配置说明

### 模型参数
我们的项目配置中使用了以下参数：
- **模型**: `deepseek-v2-lite:16b-q4_K_M`
- **温度**: 0.1（较低，确保回答一致性）
- **最大 token**: 1024
- **流式输出**: 启用

### 配置文件位置
项目中的相关配置位于：
- `config/models.yaml` - 模型参数配置
- `src/core/llm_manager.py` - LLM 管理器实现

---

## 🔧 常见问题解决

### 1. 下载速度慢
```bash
# 使用国内镜像（如果可用）
set OLLAMA_HOST=http://mirror.example.com:11434
ollama pull deepseek-v2-lite:16b-q4_K_M
```

### 2. 显存不足
如果 RTX 4070 SUPER 12GB 显存不足：
```bash
# 使用更小的量化版本
ollama pull deepseek-v2-lite:16b-q3_K_M
# 或
ollama pull deepseek-v2-lite:7b-q4_K_M
```

### 3. 服务无法启动
检查端口占用：
```bash
netstat -ano | findstr :11434
```

如果端口被占用，可以修改服务端口：
```bash
set OLLAMA_HOST=127.0.0.1:11435
ollama serve
```

### 4. 模型列表查看
```bash
# 查看已下载的模型
ollama list

# 删除不需要的模型
ollama rm 模型名称
```

---

## 🎯 与项目集成

### 项目中的集成代码
本地知识库项目通过 `src/core/llm_manager.py` 中的 `Ollama` 类集成：

```python
from langchain_community.llms import Ollama

self.local_llm = Ollama(
    base_url="http://localhost:11434",
    model="deepseek-v2-lite:16b-q4_K_M",
    temperature=0.1,
    num_predict=1024,
    streaming=True,
)
```

### 测试集成
运行项目测试程序验证集成：
```bash
cd D:\code\LLM\local-knowledge-base
python src/main.py
```

如果一切正常，会显示本地模型初始化成功的信息。

---

## 📊 性能预估

基于你的硬件配置：
- **CPU**: i5-13600KF
- **内存**: 32GB RAM
- **显卡**: RTX 4070 SUPER 12GB

| 模型版本 | 显存占用 | 推理速度 | 适合场景 |
|----------|----------|----------|----------|
| deepseek-v2-lite:16b-q4_K_M | 8-10GB | 中等 | 知识库问答（推荐） |
| deepseek-v2-lite:7b-q4_K_M | 4-6GB | 快速 | 快速响应需求 |
| Qwen3-8B (对比) | 8GB+ | 较慢 | 参考对比 |

---

## 🔄 备选方案：LLaMA-Factory

如果 Ollama 性能不满足需求，可以使用现有的 LLaMA-Factory：

### 位置
`D:\code\LLM\LLaMA-Factory`（已存在）

### 使用步骤
1. 安装依赖：`pip install -r requirements.txt`
2. 下载 DeepSeek-V2-Lite 模型
3. 配置 LLaMA-Factory API 服务
4. 修改项目集成代码

### 优缺点
- **优点**：更灵活的量化选项，更好的性能优化
- **缺点**：配置更复杂，需要更多设置

---

## 📞 技术支持

### 官方资源
- Ollama 文档：https://ollama.com/library/deepseek-v2-lite
- DeepSeek 模型：https://huggingface.co/deepseek-ai/DeepSeek-V2-Lite
- 项目问题：查看 `开发进度.md` 中的问题解决部分

### 故障排查命令
```bash
# 检查服务状态
curl http://localhost:11434/api/tags

# 测试模型响应（通过API）
curl http://localhost:11434/api/generate -d '{
  "model": "deepseek-v2-lite:16b-q4_K_M",
  "prompt": "你好",
  "stream": false
}'
```

---

## ✅ 完成检查清单

- [ ] 下载并安装 Ollama Windows 版
- [ ] 验证 `ollama --version` 命令
- [ ] 启动服务 `ollama serve`
- [ ] 下载模型 `ollama pull deepseek-v2-lite:16b-q4_K_M`
- [ ] 测试模型 `ollama run deepseek-v2-lite "你好"`
- [ ] 运行项目测试 `python src/main.py`
- [ ] 启动前端应用 `streamlit run src/frontend/app.py`

---

**下一步**：完成 Ollama 安装后，返回项目继续测试前端界面和完整系统功能。