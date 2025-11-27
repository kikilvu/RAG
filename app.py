import requests
import json
import os
import re
import subprocess
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, Body, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# -------------------------- 加载环境变量 --------------------------
load_dotenv()

# 从环境变量中读取配置
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
DOCS_FOLDER = os.getenv("DOCS_FOLDER", "docs")
GIT_REPOS_FOLDER = os.getenv("GIT_REPOS_FOLDER", "git_repos")
CONFIG_FOLDER = os.getenv("CONFIG_FOLDER", "config")

# 确保必要的目录存在
os.makedirs(DOCS_FOLDER, exist_ok=True)
os.makedirs(CONFIG_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

# -------------------------- FastAPI 初始化 --------------------------
app = FastAPI(root_path="/rag")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------------- 请求模型 --------------------------
class QueryRequest(BaseModel):
    api_key: str
    user_query: str

class PromptConfig(BaseModel):
    system_prompt: str
    follow_up_prompt: str

class ContextConfig(BaseModel):
    project_name: Optional[str] = ""
    project_description: Optional[str] = ""
    tech_stack: Optional[str] = ""
    additional_context: Optional[str] = ""

class ExampleCode(BaseModel):
    language: str
    code: str
    description: Optional[str] = ""

# -------------------------- Git相关工具函数 --------------------------
def is_git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def extract_github_url(query: str) -> Optional[str]:
    github_pattern = r"https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+(?:\.git)?"
    matches = re.findall(github_pattern, query)
    if matches:
        repo_url = matches[0]
        if not repo_url.endswith(".git"):
            repo_url += ".git"
        return repo_url
    return None

def is_git_related_query(query: str) -> bool:
    git_keywords = ["git repo", "github", "git repository", "git仓库", "github仓库"]
    query_lower = query.lower()
    return bool(extract_github_url(query)) or any(keyword in query_lower for keyword in git_keywords)

def get_repo_name_from_url(repo_url: str) -> str:
    repo_name = repo_url.rstrip(".git").split("/")[-1]
    return repo_name

def git_clone_or_pull(repo_url: str) -> Tuple[bool, str]:
    if not is_git_available():
        return False, "系统未安装Git，请先安装Git后重试"
    
    os.makedirs(GIT_REPOS_FOLDER, exist_ok=True)
    
    repo_name = get_repo_name_from_url(repo_url)
    local_repo_path = os.path.join(GIT_REPOS_FOLDER, repo_name)
    
    try:
        if os.path.exists(local_repo_path):
            result = subprocess.run(
                ["git", "-C", local_repo_path, "pull"],
                check=True,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                ["git", "clone", repo_url, local_repo_path],
                check=True,
                capture_output=True,
                text=True
            )
        
        return True, local_repo_path
    
    except subprocess.CalledProcessError as e:
        error_msg = f"Git操作失败：{e.stderr.strip()}"
        return False, error_msg
    except Exception as e:
        error_msg = f"未知错误：{str(e)}"
        return False, error_msg

# -------------------------- 文档加载和检索函数 --------------------------
def load_documents(folder_path: str, skip_binary_files: bool = True) -> Dict[str, str]:
    documents = {}
    TEXT_EXTENSIONS = [
        ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".ini", ".conf",
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".html", ".css",
        ".sh", ".bash", ".bat", ".cmd", ".php", ".rb", ".go", ".rust",
        ".xml", ".csv", ".tsv", ".log", ".txt"
    ]
    
    SKIP_FOLDERS = [".git", "__pycache__", "node_modules", "venv", ".env", ".github", "dist", "build"]
    
    if not os.path.exists(folder_path):
        return documents
    
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]
        
        for filename in files:
            if filename.startswith("."):
                continue
            
            file_path = os.path.join(root, filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            if skip_binary_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        pass
                except UnicodeDecodeError:
                    continue
            
            if file_ext not in TEXT_EXTENSIONS and skip_binary_files:
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                relative_path = os.path.relpath(file_path, folder_path)
                documents[relative_path] = content
            
            except Exception as e:
                continue
    
    return documents

def count_files_in_folder(folder_path: str) -> Tuple[int, List[str]]:
    file_count = 0
    file_paths = []
    SKIP_FOLDERS = [".git", "__pycache__", "node_modules", "venv", ".env", ".github", "dist", "build"]
    
    if not os.path.exists(folder_path):
        return 0, []
    
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]
        
        for filename in files:
            if not filename.startswith("."):
                file_count += 1
                relative_path = os.path.relpath(os.path.join(root, filename), folder_path)
                file_paths.append(relative_path)
    
    return file_count, file_paths

def retrieve_relevant_content(query: str, documents: Dict[str, str], top_k: int = 2) -> List[Dict[str, str]]:
    relevant_chunks = []
    
    if not documents:
        return relevant_chunks
    
    query_keywords = set(query.lower().split())
    
    for filename, content in documents.items():
        chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        
        for i, chunk in enumerate(chunks):
            chunk_keywords = set(chunk.lower().split())
            match_count = len(query_keywords.intersection(chunk_keywords))
            
            if match_count > 0:
                relevant_chunks.append({
                    "filename": filename,
                    "chunk_id": i,
                    "content": chunk,
                    "match_count": match_count
                })
    
    relevant_chunks.sort(key=lambda x: x["match_count"], reverse=True)
    return relevant_chunks[:top_k]

# -------------------------- 配置文件辅助函数 --------------------------
def load_config(filename: str) -> dict:
    """加载配置文件"""
    config_path = os.path.join(CONFIG_FOLDER, filename)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(filename: str, data: dict):
    """保存配置文件"""
    config_path = os.path.join(CONFIG_FOLDER, filename)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_prompt_config() -> dict:
    """获取 Prompt 配置"""
    config = load_config("prompt_config.json")
    return {
        "system_prompt": config.get("system_prompt", "基于以下参考信息来回答用户的问题。如果参考信息中有相关数据，请优先使用参考信息回答；如果没有相关信息，可以使用你自己的知识回答。"),
        "follow_up_prompt": config.get("follow_up_prompt", "Are you sure? Think carefully.")
    }

def get_context_config() -> dict:
    """获取项目上下文配置"""
    return load_config("context_config.json")

def get_example_codes() -> list:
    """获取示例代码列表"""
    config = load_config("examples_config.json")
    return config.get("examples", [])

def build_rag_prompt(query: str, relevant_content: List[Dict[str, str]], git_repo_info: Optional[Dict] = None) -> str:
    # 加载配置
    prompt_config = get_prompt_config()
    context_config = get_context_config()
    example_codes = get_example_codes()
    
    base_prompt = prompt_config["system_prompt"]
    
    context_parts = []
    
    # 添加项目上下文
    if context_config:
        project_info = []
        if context_config.get("project_name"):
            project_info.append(f"项目名称: {context_config['project_name']}")
        if context_config.get("project_description"):
            project_info.append(f"项目描述: {context_config['project_description']}")
        if context_config.get("tech_stack"):
            project_info.append(f"技术栈: {context_config['tech_stack']}")
        if context_config.get("additional_context"):
            project_info.append(f"额外信息: {context_config['additional_context']}")
        
        if project_info:
            context_parts.append("项目背景信息：\n" + "\n".join(project_info))
            context_parts.append("---")
    
    # 添加示例代码
    if example_codes:
        examples_text = "参考示例代码（请遵循类似的代码风格）：\n"
        for idx, ex in enumerate(example_codes):
            examples_text += f"\n示例 {idx + 1} ({ex.get('language', 'unknown')}):\n"
            if ex.get("description"):
                examples_text += f"说明: {ex['description']}\n"
            examples_text += f"```{ex.get('language', '')}\n{ex.get('code', '')}\n```\n"
        context_parts.append(examples_text)
        context_parts.append("---")
    if git_repo_info:
        repo_name = git_repo_info.get("repo_name", "")
        file_count = git_repo_info.get("file_count", 0)
        repo_url = git_repo_info.get("repo_url", "")
        
        repo_info = f"Git仓库信息：\n"
        repo_info += f"- 仓库URL: {repo_url}\n"
        repo_info += f"- 本地存储路径: {git_repo_info.get('local_path', '')}\n"
        repo_info += f"- 总文件数: {file_count} 个\n"
        
        if file_count > 0 and file_count <= 50:
            repo_info += f"- 所有文件列表:\n  " + "\n  ".join(git_repo_info.get("file_paths", [])) + "\n"
        
        context_parts.append(repo_info)
        context_parts.append("---")
    
    if relevant_content:
        for item in relevant_content:
            context_parts.append(
                f"来自文件 '{item['filename']}' (片段 {item['chunk_id']}):\n"
                f"{item['content']}\n"
                "---"
            )
    
    context = "\n".join(context_parts) if context_parts else "无相关参考信息"
    
    rag_prompt = f"""
{base_prompt}

参考信息：
{context}

用户的问题：
{query}
"""
    
    return rag_prompt.strip()

# -------------------------- API接口 --------------------------

# 首页
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

# 文件上传接口
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到 docs 文件夹"""
    try:
        file_path = os.path.join(DOCS_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        return {"message": "文件上传成功", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 获取文件列表
@app.get("/files")
async def list_files():
    """获取 docs 文件夹中的文件列表"""
    files = []
    if os.path.exists(DOCS_FOLDER):
        for filename in os.listdir(DOCS_FOLDER):
            file_path = os.path.join(DOCS_FOLDER, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
    return {"files": files}

# 删除文件
@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """删除指定文件"""
    file_path = os.path.join(DOCS_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"message": "文件已删除"}
    raise HTTPException(status_code=404, detail="文件不存在")

# 获取文件内容
@app.get("/files/{filename}/content")
async def get_file_content(filename: str):
    """获取文件内容"""
    file_path = os.path.join(DOCS_FOLDER, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"content": content}
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="无法读取二进制文件")
    raise HTTPException(status_code=404, detail="文件不存在")

# Prompt 配置接口
@app.get("/config/prompt")
async def get_prompt():
    """获取 Prompt 配置"""
    return get_prompt_config()

@app.post("/config/prompt")
async def save_prompt(config: PromptConfig):
    """保存 Prompt 配置"""
    save_config("prompt_config.json", config.dict())
    return {"message": "配置已保存"}

# 项目上下文配置接口
@app.get("/config/context")
async def get_context():
    """获取项目上下文配置"""
    return get_context_config()

@app.post("/config/context")
async def save_context(config: ContextConfig):
    """保存项目上下文配置"""
    save_config("context_config.json", config.dict())
    return {"message": "配置已保存"}

# 示例代码配置接口
@app.get("/config/examples")
async def get_examples():
    """获取示例代码列表"""
    return {"examples": get_example_codes()}

@app.post("/config/examples")
async def save_example(example: ExampleCode):
    """保存示例代码"""
    config = load_config("examples_config.json")
    examples = config.get("examples", [])
    examples.append(example.dict())
    save_config("examples_config.json", {"examples": examples})
    return {"message": "示例已保存"}

@app.delete("/config/examples/{index}")
async def delete_example(index: int):
    """删除指定示例代码"""
    config = load_config("examples_config.json")
    examples = config.get("examples", [])
    if 0 <= index < len(examples):
        examples.pop(index)
        save_config("examples_config.json", {"examples": examples})
        return {"message": "示例已删除"}
    raise HTTPException(status_code=404, detail="示例不存在")

@app.post("/query")
async def query(request: QueryRequest):
    api_key = request.api_key
    user_query = request.user_query
    
    # 从配置中获取 follow_up_query
    prompt_config = get_prompt_config()
    follow_up_query = prompt_config["follow_up_prompt"]
    
    git_repo_info = None
    local_repo_path = None
    
    # 处理Git相关查询
    if is_git_related_query(user_query):
        repo_url = extract_github_url(user_query)
        if repo_url:
            success, result = git_clone_or_pull(repo_url)
            if success:
                local_repo_path = result
                file_count, file_paths = count_files_in_folder(local_repo_path)
                git_repo_info = {
                    "repo_url": repo_url,
                    "repo_name": get_repo_name_from_url(repo_url),
                    "local_path": local_repo_path,
                    "file_count": file_count,
                    "file_paths": file_paths
                }
    
    # 加载文档
    if local_repo_path and os.path.exists(local_repo_path):
        documents = load_documents(local_repo_path)
    else:
        documents = load_documents(DOCS_FOLDER)
    
    # 检索相关内容
    relevant_content = retrieve_relevant_content(user_query, documents)
    
    # 构建RAG提示词
    rag_prompt = build_rag_prompt(user_query, relevant_content, git_repo_info)
    
    # 第一次API调用
    response1 = requests.post(
        url=API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": rag_prompt}],
            "extra_body": {"reasoning": {"enabled": True}}
        }),
        timeout=30
    )
    response1.raise_for_status()
    response1_json = response1.json()
    assistant_content1 = response1_json['choices'][0]['message']['content']
    
    # 保存对话历史并进行第二次调用
    messages = [
        {"role": "user", "content": rag_prompt},
        {
            "role": "assistant",
            "content": assistant_content1,
            "reasoning_details": response1_json['choices'][0]['message'].get('reasoning_details')
        },
        {"role": "user", "content": follow_up_query}
    ]
    
    response2 = requests.post(
        url=API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": MODEL_NAME,
            "messages": messages,
            "extra_body": {"reasoning": {"enabled": True}}
        }),
        timeout=30
    )
    response2.raise_for_status()
    response2_json = response2.json()
    assistant_content2 = response2_json['choices'][0]['message']['content']
    
    return {
        "first_response": assistant_content1,
        "second_response": assistant_content2
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)