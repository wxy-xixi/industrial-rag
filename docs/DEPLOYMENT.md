# 持久化部署与换电脑迁移说明

## 1. 目标

如果希望换一台电脑后仍然保留已经上传过的文档、图片、向量索引和问答能力，系统需要满足两件事：

1. 数据库存储不能只依赖本机临时环境。
2. 上传文件和向量索引必须挂载到持久化目录或卷。

当前项目已经补充了 Docker + MySQL + 持久化卷的部署方案。

## 2. 持久化的数据

系统长期数据分为两类：

### 数据库数据

数据库中保存：

- 文档元信息
- 文档分块
- 向量二进制
- 问答历史

在 Docker 部署中，这部分由 `mysql_data` 卷持久化。

### 文件数据

文件目录中保存：

- 上传原始文件
- FAISS 索引文件
- 问答时的临时图片目录

在 Docker 部署中，这部分由 `app_data` 卷持久化。

## 3. 新增的部署文件

项目根目录新增：

- `backend/Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

说明文档：

- `docs/DEPLOYMENT.md`

## 4. 部署前准备

确保目标电脑安装：

1. Docker
2. Docker Compose

同时准备一个 `.env` 文件，至少要有：

```env
DASHSCOPE_API_KEY=你的通义千问API Key
```

## 5. 启动方式

在项目根目录执行：

```bash
docker compose up -d --build
```

启动后：

- Flask 服务监听 `http://localhost:5000`
- MySQL 服务监听 `3306`

## 6. 为什么这套方案适合换电脑

因为部署后你的数据不再散落在“某台电脑的某个 Python 环境里”，而是集中在：

1. MySQL 数据卷
2. 应用数据卷

只要迁移这些卷，或者重新挂载同样的数据目录，新电脑就可以继续使用之前的知识库。

## 7. 两种迁移方式

### 方式一：迁移 Docker 卷

适合你自己换电脑继续部署。

需要保留：

- `mysql_data`
- `app_data`

迁移后在新电脑重新执行：

```bash
docker compose up -d
```

### 方式二：迁移外部数据库和存储目录

如果后面不用 Docker，也可以把：

- MySQL 数据库
- `uploads`
- `vector_store`
- `chat_images`

这几部分迁移到新机器。

然后只要在 `.env` 中重新指定：

```env
DATABASE_URL=mysql+pymysql://用户名:密码@主机:3306/industrial_rag
UPLOAD_FOLDER=/你的持久化目录/uploads
VECTOR_STORE_DIR=/你的持久化目录/vector_store
CHAT_IMAGE_FOLDER=/你的持久化目录/chat_images
```

## 8. 当前配置支持的持久化变量

`.env` 中现在支持这些部署相关配置：

```env
DATABASE_URL=mysql+pymysql://...
UPLOAD_FOLDER=backend/uploads
VECTOR_STORE_DIR=backend/vector_store
CHAT_IMAGE_FOLDER=backend/chat_images
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

## 9. 推荐的毕设交付方式

如果你是为了毕设最终答辩，推荐这样做：

1. 本地开发时继续使用 SQLite，简单方便。
2. 答辩前准备一套 Docker Compose 部署说明。
3. PPT 中说明系统已支持迁移到 MySQL + 持久化卷部署。
4. 如果时间允许，提前在另一台电脑试一次 `docker compose up -d --build`。

这样老师问“换电脑后数据是否还在”时，你可以明确回答：

系统已经支持通过 MySQL 和持久化存储卷保留上传文档与向量索引，不依赖单机本地环境。
