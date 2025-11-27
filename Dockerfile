# 基础镜像：Python 3.10（轻量且稳定）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Git、编译工具等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装Python包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要目录（Git仓库存储、文档目录、配置目录、静态文件）
RUN mkdir -p /app/git_repos /app/docs /app/config /app/static

# 暴露端口（FastAPI默认8000）
EXPOSE 8000

# 启动命令（使用uvicorn运行FastAPI）
CMD ["python","app.py"]