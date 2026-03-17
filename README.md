# 工业领域RAG智能问答系统

基于检索增强生成（RAG）技术的工业领域智能问答系统，支持上传工业文档并进行智能问答。

## 技术栈

- **后端**：Python + Flask + LangChain
- **前端**：HTML + CSS + JavaScript
- **向量数据库**：FAISS
- **大模型**：通义千问（Qwen）
- **文档解析**：支持 PDF、Word、TXT 格式

## 项目结构

    industrial-rag/
    ├── backend/
    │   ├── app.py              # Flask 主应用
    │   ├── rag_engine.py       # RAG 核心引擎
    │   ├── doc_parser.py       # 文档解析模块
    │   ├── models.py           # 模型配置
    │   └── requirements.txt    # Python 依赖
    ├── frontend/
    │   ├── index.html          # 主页面
    │   ├── style.css           # 样式文件
    │   └── app.js              # 前端逻辑
    └── .gitignore

## 快速开始

### 1. 安装依赖

    cd backend
    pip install -r requirements.txt

### 2. 配置API密钥

在 backend/models.py 中配置通义千问 API Key。

### 3. 启动后端

    python app.py

### 4. 访问系统

打开浏览器访问 http://localhost:5000

## 功能特点

- 📄 支持多格式文档上传（PDF、Word、TXT）
- 🔍 基于向量检索的精准问答
- 💬 流式对话体验
- 🏭 专注工业领域知识问答
