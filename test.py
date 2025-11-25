import requests
import json
import os
import re
import subprocess
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv  # 导入读取.env文件的库

# -------------------------- 加载环境变量 --------------------------
# 加载.env文件中的配置（如果不存在.env文件，会使用系统环境变量）
load_dotenv()  # 关键：加载.env文件

# 从环境变量中读取配置（支持.env文件和系统环境变量）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
DOCS_FOLDER = os.getenv("DOCS_FOLDER", "docs")  # 默认值：docs（防止未配置）
GIT_REPOS_FOLDER = os.getenv("GIT_REPOS_FOLDER", "git_repos")  # Git仓库本地存储文件夹

# 验证必填配置是否存在
required_env_vars = ["OPENROUTER_API_KEY", "API_URL", "MODEL_NAME"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"缺少必要的环境变量：{', '.join(missing_vars)}。请检查.env文件是否配置正确。")

# -------------------------- Git相关工具函数 --------------------------
def is_git_available() -> bool:
    """检查系统是否安装了Git"""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def extract_github_url(query: str) -> Optional[str]:
    """
    从用户查询中提取GitHub仓库URL
    支持的格式：https://github.com/xxx/xxx.git 或 https://github.com/xxx/xxx
    """
    # 匹配GitHub仓库URL的正则表达式
    github_pattern = r"https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+(?:\.git)?"
    matches = re.findall(github_pattern, query)
    if matches:
        # 处理可能缺少.git后缀的情况
        repo_url = matches[0]
        if not repo_url.endswith(".git"):
            repo_url += ".git"
        return repo_url
    return None

def is_git_related_query(query: str) -> bool:
    """判断查询是否涉及Git仓库"""
    # 关键词列表：包含git repo、github等相关词汇
    git_keywords = ["git repo", "github", "git repository", "git仓库", "github仓库"]
    query_lower = query.lower()
    # 要么包含GitHub URL，要么包含Git相关关键词
    return bool(extract_github_url(query)) or any(keyword in query_lower for keyword in git_keywords)

def get_repo_name_from_url(repo_url: str) -> str:
    """从仓库URL中提取仓库名称"""
    # 处理格式：https://github.com/owner/repo.git 或 https://github.com/owner/repo
    repo_name = repo_url.rstrip(".git").split("/")[-1]
    return repo_name

def git_clone_or_pull(repo_url: str) -> Tuple[bool, str]:
    """
    克隆或更新Git仓库到本地
    返回：(是否成功, 本地仓库路径)
    """
    # 检查Git是否可用
    if not is_git_available():
        return False, "系统未安装Git，请先安装Git后重试"
    
    # 创建Git仓库存储文件夹
    os.makedirs(GIT_REPOS_FOLDER, exist_ok=True)
    
    # 提取仓库名称
    repo_name = get_repo_name_from_url(repo_url)
    local_repo_path = os.path.join(GIT_REPOS_FOLDER, repo_name)
    
    try:
        # 检查本地是否已存在该仓库
        if os.path.exists(local_repo_path):
            print(f"仓库 '{repo_name}' 已存在，执行git pull更新...")
            # 执行git pull更新
            result = subprocess.run(
                ["git", "-C", local_repo_path, "pull"],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"更新成功：{result.stdout.strip()}")
        else:
            print(f"克隆仓库 '{repo_url}' 到 {local_repo_path}...")
            # 执行git clone
            result = subprocess.run(
                ["git", "clone", repo_url, local_repo_path],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"克隆成功：{result.stdout.strip()}")
        
        return True, local_repo_path
    
    except subprocess.CalledProcessError as e:
        error_msg = f"Git操作失败：{e.stderr.strip()}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"未知错误：{str(e)}"
        print(error_msg)
        return False, error_msg

# -------------------------- 文档加载和检索函数 --------------------------
def load_documents(folder_path: str, skip_binary_files: bool = True) -> Dict[str, str]:
    """
    加载指定文件夹中的所有支持格式的文档（递归遍历子文件夹）
    skip_binary_files: 是否跳过二进制文件
    返回: {文件相对路径: 文件内容} 的字典
    """
    documents = {}
    # 支持的文本文件类型（可根据需要扩展）
    TEXT_EXTENSIONS = [
        ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".ini", ".conf",
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".html", ".css",
        ".sh", ".bash", ".bat", ".cmd", ".php", ".rb", ".go", ".rust",
        ".xml", ".csv", ".tsv", ".log", ".txt"
    ]
    
    # 跳过的文件夹（Git相关、依赖文件夹等）
    SKIP_FOLDERS = [".git", "__pycache__", "node_modules", "venv", ".env", ".github", "dist", "build"]
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"警告: 文件夹 '{folder_path}' 不存在")
        return documents
    
    # 递归遍历文件夹
    for root, dirs, files in os.walk(folder_path):
        # 跳过指定文件夹
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]
        
        for filename in files:
            # 跳过隐藏文件
            if filename.startswith("."):
                continue
            
            file_path = os.path.join(root, filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            # 跳过二进制文件（简单判断）
            if skip_binary_files:
                try:
                    # 尝试以文本模式打开，判断是否为二进制文件
                    with open(file_path, "r", encoding="utf-8") as f:
                        pass
                except UnicodeDecodeError:
                    # 解码失败，视为二进制文件
                    continue
            
            # 只处理文本文件（或所有文件，如果skip_binary_files为False）
            if file_ext not in TEXT_EXTENSIONS and skip_binary_files:
                continue
            
            # 读取文件内容
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                # 存储相对路径（便于识别文件位置）
                relative_path = os.path.relpath(file_path, folder_path)
                documents[relative_path] = content
                print(f"成功加载文件: {relative_path} (大小: {len(content)} 字符)")
            
            except Exception as e:
                print(f"读取文件 {file_path} 失败: {str(e)}")
    
    return documents

def count_files_in_folder(folder_path: str) -> Tuple[int, List[str]]:
    """
    统计文件夹中的文件数量（递归）
    返回：(文件总数, 文件路径列表)
    """
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
    """
    简单的检索逻辑：基于关键词匹配查找相关文档内容
    实际场景中可以替换为更复杂的检索（如TF-IDF、向量数据库等）
    """
    relevant_chunks = []
    
    # 如果没有加载到文档，返回空
    if not documents:
        return relevant_chunks
    
    # 提取查询中的关键词（简单处理）
    query_keywords = set(query.lower().split())
    
    # 对每个文档计算关键词匹配度
    for filename, content in documents.items():
        # 将文档内容分段（按段落分割，避免内容过长）
        chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        
        for i, chunk in enumerate(chunks):
            # 计算该段落与查询的关键词匹配数
            chunk_keywords = set(chunk.lower().split())
            match_count = len(query_keywords.intersection(chunk_keywords))
            
            if match_count > 0:
                relevant_chunks.append({
                    "filename": filename,
                    "chunk_id": i,
                    "content": chunk,
                    "match_count": match_count
                })
    
    # 按匹配度排序，返回前top_k个相关片段
    relevant_chunks.sort(key=lambda x: x["match_count"], reverse=True)
    return relevant_chunks[:top_k]

def build_rag_prompt(query: str, relevant_content: List[Dict[str, str]], git_repo_info: Optional[Dict] = None) -> str:
    """
    构建包含检索到的相关内容的提示词
    git_repo_info: Git仓库信息（如仓库名称、文件数量等）
    """
    # 基础提示词
    base_prompt = "基于以下参考信息来回答用户的问题。如果参考信息中有相关数据，请优先使用参考信息回答；如果没有相关信息，可以使用你自己的知识回答。"
    
    # 添加Git仓库信息（如果有）
    context_parts = []
    if git_repo_info:
        repo_name = git_repo_info.get("repo_name", "")
        file_count = git_repo_info.get("file_count", 0)
        repo_url = git_repo_info.get("repo_url", "")
        
        repo_info = f"Git仓库信息：\n"
        repo_info += f"- 仓库URL: {repo_url}\n"
        repo_info += f"- 本地存储路径: {git_repo_info.get('local_path', '')}\n"
        repo_info += f"- 总文件数: {file_count} 个\n"
        
        # 如果文件数较少，列出所有文件
        if file_count > 0 and file_count <= 50:
            repo_info += f"- 所有文件列表:\n  " + "\n  ".join(git_repo_info.get("file_paths", [])) + "\n"
        
        context_parts.append(repo_info)
        context_parts.append("---")
    
    # 添加相关文档内容
    if relevant_content:
        for item in relevant_content:
            context_parts.append(
                f"来自文件 '{item['filename']}' (片段 {item['chunk_id']}):\n"
                f"{item['content']}\n"
                "---"
            )
    
    context = "\n".join(context_parts) if context_parts else "无相关参考信息"
    
    # 构建最终提示词
    rag_prompt = f"""
{base_prompt}

参考信息：
{context}

用户的问题：
{query}
"""
    
    return rag_prompt.strip()

# -------------------------- 主逻辑 --------------------------
def main():
    # 1. 初始化变量
    git_repo_info = None
    local_repo_path = None
    
    # 2. 定义用户查询（可以修改为任意问题）
    user_query = "帮我扫描查看一下这个git中readme.org的内容是什么 https://github.com/karthink/gptel.git"
    follow_up_query = "Are you sure? Think carefully."
    
    # 3. 检查是否为Git相关查询并处理
    print("=== 检测Git相关查询 ===")
    if is_git_related_query(user_query):
        print("检测到Git相关查询，开始处理...")
        
        # 提取GitHub URL
        repo_url = extract_github_url(user_query)
        if repo_url:
            print(f"提取到GitHub仓库URL: {repo_url}")
            
            # 克隆或更新仓库
            success, result = git_clone_or_pull(repo_url)
            if success:
                local_repo_path = result
                
                # 统计仓库文件数量
                print(f"\n=== 统计仓库文件数量 ===")
                file_count, file_paths = count_files_in_folder(local_repo_path)
                
                # 存储仓库信息
                git_repo_info = {
                    "repo_url": repo_url,
                    "repo_name": get_repo_name_from_url(repo_url),
                    "local_path": local_repo_path,
                    "file_count": file_count,
                    "file_paths": file_paths
                }
                
                print(f"仓库 '{git_repo_info['repo_name']}' 中共有 {file_count} 个文件")
            else:
                print(f"Git仓库处理失败: {result}")
        else:
            print("未从查询中提取到有效的GitHub仓库URL")
    else:
        print("未检测到Git相关查询，将加载普通文档...")
    
    # 4. 加载文档（优先加载Git仓库文件，否则加载普通文档）
    print("\n=== 加载文档 ===")
    if local_repo_path and os.path.exists(local_repo_path):
        # 加载Git仓库中的文件
        documents = load_documents(local_repo_path)
    else:
        # 加载普通文档文件夹
        documents = load_documents(DOCS_FOLDER)
    
    print(f"共加载 {len(documents)} 个文件")
    
    # 5. 检索相关内容
    print("\n=== 检索相关内容 ===")
    relevant_content = retrieve_relevant_content(user_query, documents)
    if relevant_content:
        print(f"找到 {len(relevant_content)} 个相关内容片段")
        for item in relevant_content:
            print(f"- 文件: {item['filename']}, 匹配关键词数: {item['match_count']}")
    else:
        print("未找到相关内容片段")
    
    # 6. 构建RAG提示词（包含Git仓库信息）
    rag_prompt = build_rag_prompt(user_query, relevant_content, git_repo_info)
    print(f"\n=== 构建的RAG提示词 ===")
    print(rag_prompt[:800] + "..." if len(rag_prompt) > 800 else rag_prompt)
    
    # -------------------------- 第一次API调用（带RAG） --------------------------
    print("\n=== 第一次API调用（带RAG） ===")
    try:
        response1 = requests.post(
            url=API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": rag_prompt}],
                "extra_body": {"reasoning": {"enabled": True}}
            }),
            timeout=30
        )
        response1.raise_for_status()  # 抛出HTTP错误
    except requests.exceptions.RequestException as e:
        print(f"第一次API调用失败: {str(e)}")
        return
    
    # 处理第一次响应
    response1_json = response1.json()
    if "choices" not in response1_json or len(response1_json["choices"]) == 0:
        print("第一次API调用返回格式错误:", response1_json)
        return
    
    assistant_content1 = response1_json['choices'][0]['message']['content']
    print("第一次回答:")
    print(assistant_content1)
    
    # -------------------------- 保存对话历史 --------------------------
    messages = [
        {"role": "user", "content": rag_prompt},
        {
            "role": "assistant",
            "content": assistant_content1,
            "reasoning_details": response1_json['choices'][0]['message'].get('reasoning_details')
        },
        {"role": "user", "content": follow_up_query}
    ]
    
    # -------------------------- 第二次API调用（继续推理） --------------------------
    print("\n=== 第二次API调用（继续推理） ===")
    try:
        response2 = requests.post(
            url=API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
    except requests.exceptions.RequestException as e:
        print(f"第二次API调用失败: {str(e)}")
        return
    
    # 处理第二次响应
    response2_json = response2.json()
    if "choices" not in response2_json or len(response2_json["choices"]) == 0:
        print("第二次API调用返回格式错误:", response2_json)
        return
    
    assistant_content2 = response2_json['choices'][0]['message']['content']
    print("第二次回答:")
    print(assistant_content2)

if __name__ == "__main__":
    main()