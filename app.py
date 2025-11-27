import requests
import json
import os
import re
import subprocess
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, Body
from pydantic import BaseModel

# -------------------------- 加载环境变量 --------------------------
load_dotenv()

# 从环境变量中读取配置
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
DOCS_FOLDER = os.getenv("DOCS_FOLDER", "docs")
GIT_REPOS_FOLDER = os.getenv("GIT_REPOS_FOLDER", "git_repos")

# -------------------------- FastAPI 初始化 --------------------------
app = FastAPI(root_path="/rag")

# -------------------------- 请求模型 --------------------------
class QueryRequest(BaseModel):
    api_key: str
    user_query: str

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

def build_rag_prompt(query: str, relevant_content: List[Dict[str, str]], git_repo_info: Optional[Dict] = None) -> str:
    base_prompt = "基于以下参考信息来回答用户的问题。如果参考信息中有相关数据，请优先使用参考信息回答；如果没有相关信息，可以使用你自己的知识回答。"
    
    context_parts = []
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
@app.post("/query")
async def query(request: QueryRequest):
    api_key = request.api_key
    user_query = request.user_query
    follow_up_query = "Are you sure? Think carefully."
    
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