# Windows 新电脑部署清单

## 1. 适用场景

这份清单适用于以下情况：

- 你准备在另一台 Windows 电脑上继续开发和演示本项目
- 你已经安装了 Python
- 你希望尽量沿用当前这套本地运行方式，而不是一上来就改成服务器部署

推荐顺序是：

1. 先用 Windows + Python 跑通项目
2. 如果依赖安装出现兼容问题，再切换到 WSL2 或 Docker

## 2. 先下载哪些软件

### 必装

1. Git for Windows  
   下载链接：<https://git-scm.com/download/win>

2. Visual Studio Code  
   下载链接：<https://code.visualstudio.com/Download>

### 推荐安装

3. Docker Desktop  
   用于后续按 `docker-compose.yml` 做部署演示  
   下载链接：<https://docs.docker.com/desktop/setup/install/windows-install/>

4. WSL2  
   如果后面在原生 Windows 环境里遇到 `faiss`、PDF 处理或图像依赖兼容问题，建议切到 WSL2  
   安装说明：<https://learn.microsoft.com/en-us/windows/wsl/install>

### 你已经安装的软件

5. Python  
   官方下载页：<https://www.python.org/downloads/windows/>

## 3. 在旧电脑上要带走什么

如果你不仅想带走代码，还想保留已经上传过的知识库、索引和历史记录，需要一起复制下面这些内容：

1. 项目代码
2. 项目根目录下的 `.env`
3. `backend/uploads`
4. `backend/vector_store`
5. `backend/industrial_rag.db`

说明：

- 只 clone GitHub 仓库：新电脑能运行，但知识库是空的
- 同时复制上面 4 项数据：新电脑可以继续使用旧知识库

## 4. 在新电脑上如何拉取项目

先打开 `PowerShell` 或 `CMD`，进入你准备放项目的目录，执行：

```bash
git clone https://github.com/wxy-xixi/industrial-rag.git
cd industrial-rag
```

然后把旧电脑备份出来的这些内容覆盖到当前项目中：

- `.env`
- `backend/uploads`
- `backend/vector_store`
- `backend/industrial_rag.db`

## 5. 如何用 Windows 本机 Python 启动

### 第一步：进入后端目录

```bash
cd backend
```

### 第二步：创建虚拟环境

```bash
python -m venv venv
```

### 第三步：激活虚拟环境

```bash
venv\Scripts\activate
```

### 第四步：安装依赖

```bash
pip install -r requirements.txt
```

### 第五步：启动项目

```bash
python app.py
```

### 第六步：访问系统

浏览器打开：

```text
http://127.0.0.1:5000
```

## 6. 第一次启动时重点检查什么

### 1. `.env` 是否存在

至少要保证里面有：

```env
DASHSCOPE_API_KEY=你的通义千问API Key
```

### 2. Python 版本是否合适

建议使用 Python 3.10 或 3.11。

### 3. 知识库数据是否复制完整

重点检查：

- `backend/uploads`
- `backend/vector_store`
- `backend/industrial_rag.db`

## 7. 如果安装依赖时报错怎么办

Windows 本机环境最容易卡在这些依赖上：

- `faiss`
- `PyMuPDF`
- 图像处理相关依赖

如果 `pip install -r requirements.txt` 无法顺利完成，建议不要长时间硬调原生 Windows 环境，而是改用：

1. `WSL2`
2. 或者 `Docker Desktop`

## 8. 如果改用 Docker，怎么启动

先确保 Docker Desktop 已启动，然后在项目根目录执行：

```bash
docker compose up -d --build
```

启动后访问：

```text
http://127.0.0.1:5000
```

## 9. 如果改用 WSL2，建议怎么做

适用于：

- 本机 Python 跑不通
- 依赖兼容性差
- 你想得到更接近 Linux 部署环境的开发体验

WSL2 安装说明：

<https://learn.microsoft.com/en-us/windows/wsl/install>

进入 WSL 后再执行：

```bash
git clone https://github.com/wxy-xixi/industrial-rag.git
cd industrial-rag/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 10. 最推荐的迁移顺序

建议你按这个顺序做：

1. 在 Windows 新电脑上安装 `Git` 和 `VS Code`
2. clone GitHub 仓库
3. 复制 `.env`、`backend/uploads`、`backend/vector_store`、`backend/industrial_rag.db`
4. 用本机 Python 先跑一次
5. 如果依赖报错，再切换到 `WSL2`
6. 如果你要做正式部署展示，再用 `Docker Desktop`

## 11. 你迁移成功的判断标准

满足以下几点，就说明迁移成功：

1. `python app.py` 能正常启动
2. 浏览器能打开 `http://127.0.0.1:5000`
3. 左侧知识库里能看到你之前上传过的文档
4. 提问时还能命中旧知识库内容
5. 单文件检索、历史问答、分类功能都能正常使用

## 12. 额外建议

为了避免答辩前换电脑出问题，建议你在旧电脑上额外准备一份压缩包，至少包含：

- 项目代码
- `.env`
- `backend/uploads`
- `backend/vector_store`
- `backend/industrial_rag.db`

这样即使 GitHub、网络或新环境出问题，你也能快速恢复演示环境。
