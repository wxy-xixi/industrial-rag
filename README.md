# 工业领域RAG智能问答系统

基于检索增强生成（RAG）技术的工业领域多模态智能问答系统，支持上传工业文档与图片并进行智能问答。

## 技术栈

- **后端**：Python + Flask
- **前端**：HTML + CSS + JavaScript
- **向量检索**：FAISS
- **存储**：SQLite / MySQL（通过环境变量配置）
- **大模型**：通义千问（Qwen）
- **文档解析**：支持 PDF、Word、TXT、工业图片

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

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，至少填写：

    DASHSCOPE_API_KEY=你的通义千问API Key

可选配置：

    DATABASE_URL=sqlite:///backend/industrial_rag.db
    FLASK_DEBUG=false

### 3. 启动后端

    cd backend
    python app.py

### 4. 访问系统

打开浏览器访问 http://localhost:5000

## 功能特点

- 📄 支持多格式文档上传（PDF、Word、TXT、PNG、JPG、WEBP）
- 🔍 基于 FAISS 向量索引的精准问答
- 🖼️ 支持图片摘要入库与图文联合问答
- 💬 类聊天式问答体验
- 🏭 专注工业领域知识问答

## 当前实现说明

- 当前版本支持图片上传后生成语义摘要并写入知识库，也支持提问时临时附加图片进行图文问答。
- 检索逻辑已接入本地 FAISS 索引，上传文档后会写入向量库，删除文档后会自动重建索引。
- 首页由 Flask 直接托管 `frontend/` 静态页面，启动后可直接访问 `http://localhost:5000`。

## 答辩与说明文档

- 答辩讲解稿见 `docs/DEFENSE.md`
- 系统架构说明见 `docs/ARCHITECTURE.md`
- 持久化部署说明见 `docs/DEPLOYMENT.md`
