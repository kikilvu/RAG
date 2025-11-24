import requests
import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv  # 导入读取.env文件的库

# -------------------------- 加载环境变量 --------------------------
# 加载.env文件中的配置（如果不存在.env文件，会使用系统环境变量）
load_dotenv()  # 关键：加载.env文件

# 从环境变量中读取配置（支持.env文件和系统环境变量）
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
DOCS_FOLDER = os.getenv("DOCS_FOLDER", "docs")  # 默认值：docs（防止未配置）

# 验证必填配置是否存在
required_env_vars = ["OPENROUTER_API_KEY", "API_URL", "MODEL_NAME"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"缺少必要的环境变量：{', '.join(missing_vars)}。请检查.env文件是否配置正确。")

# -------------------------- 工具函数 --------------------------
def load_documents(folder_path: str) -> Dict[str, str]:
    """
    加载指定文件夹中的所有支持格式的文档
    返回: {文件名: 文件内容} 的字典
    """
    documents = {}
    SUPPORTED_EXTENSIONS = [".txt", ".md", ".json"]  # 支持的文件类型
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"警告: 文档文件夹 '{folder_path}' 不存在，将仅使用模型自身知识")
        return documents
    
    # 遍历文件夹中的所有文件
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # 只处理支持的文件类型
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            print(f"跳过不支持的文件类型: {filename}")
            continue
        
        # 读取文件内容
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            documents[filename] = content
            print(f"成功加载文档: {filename} (大小: {len(content)} 字符)")
        except Exception as e:
            print(f"读取文件 {filename} 失败: {str(e)}")
    
    return documents

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

def build_rag_prompt(query: str, relevant_content: List[Dict[str, str]]) -> str:
    """
    构建包含检索到的相关内容的提示词
    """
    if not relevant_content:
        # 没有检索到相关内容，直接返回原始查询
        return query
    
    # 格式化相关内容
    context_parts = []
    for item in relevant_content:
        context_parts.append(
            f"来自文档 '{item['filename']}' (片段 {item['chunk_id']}):\n"
            f"{item['content']}\n"
            "---"
        )
    
    context = "\n".join(context_parts)
    
    # 构建提示词（告诉模型使用提供的上下文来回答）
    rag_prompt = f"""
基于以下参考文档内容来回答用户的问题。如果参考文档中有相关信息，请优先使用文档内容回答；如果没有相关信息，可以使用你自己的知识回答。

参考文档内容：
{context}

用户的问题：
{query}
"""
    
    return rag_prompt.strip()

# -------------------------- 主逻辑 --------------------------
def main():
    # 1. 加载文档
    print("=== 加载文档 ===")
    documents = load_documents(DOCS_FOLDER)  # 使用环境变量中的DOCS_FOLDER
    
    # 2. 定义用户查询（可以修改为任意问题）
    user_query = "mysql中的事务.md 中讲了什么?"
    follow_up_query = "Are you sure? Think carefully."
    
    # 3. 检索相关文档内容
    print("\n=== 检索相关内容 ===")
    relevant_content = retrieve_relevant_content(user_query, documents)
    if relevant_content:
        print(f"找到 {len(relevant_content)} 个相关内容片段")
        for item in relevant_content:
            print(f"- 文档: {item['filename']}, 匹配关键词数: {item['match_count']}")
    else:
        print("未找到相关文档内容")
    
    # 4. 构建RAG提示词
    rag_prompt = build_rag_prompt(user_query, relevant_content)
    print(f"\n=== 构建的RAG提示词 ===")
    print(rag_prompt[:500] + "..." if len(rag_prompt) > 500 else rag_prompt)
    
    # -------------------------- 第一次API调用（带RAG） --------------------------
    print("\n=== 第一次API调用（带RAG） ===")
    response1 = requests.post(
        url=API_URL,  # 使用环境变量中的API_URL
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",  # 使用环境变量中的API_KEY
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": MODEL_NAME,  # 使用环境变量中的MODEL_NAME
            "messages": [
                {
                    "role": "user",
                    "content": rag_prompt  # 使用RAG提示词
                }
            ],
            "extra_body": {"reasoning": {"enabled": True}}
        })
    )
    
    # 处理第一次响应 - 只输出content
    response1_json = response1.json()
    if "choices" not in response1_json or len(response1_json["choices"]) == 0:
        print("第一次API调用失败:", response1_json)
        return
    
    # 提取并打印第一次回答的content
    assistant_content1 = response1_json['choices'][0]['message']['content']
    print("第一次回答:")
    print(assistant_content1)  # 只输出content部分
    
    # -------------------------- 保存对话历史（包含RAG上下文） --------------------------
    messages = [
        {
            "role": "user",
            "content": rag_prompt  # 保存带RAG上下文的查询
        },
        {
            "role": "assistant",
            "content": assistant_content1,  # 只保存content
            # 可选：如果不需要传递reasoning_details，直接删除该字段
            "reasoning_details": response1_json['choices'][0]['message'].get('reasoning_details')
        },
        # 跟进查询：基于之前的RAG结果继续追问
        {
            "role": "user",
            "content": follow_up_query
        }
    ]
    
    # -------------------------- 第二次API调用（继续推理） --------------------------
    print("\n=== 第二次API调用（继续推理） ===")
    response2 = requests.post(
        url=API_URL,  # 使用环境变量中的API_URL
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",  # 使用环境变量中的API_KEY
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": MODEL_NAME,  # 使用环境变量中的MODEL_NAME
            "messages": messages,
            "extra_body": {"reasoning": {"enabled": True}}
        })
    )
    
    # 处理第二次响应 - 只输出content
    response2_json = response2.json()
    if "choices" not in response2_json or len(response2_json["choices"]) == 0:
        print("第二次API调用失败:", response2_json)
        return
    
    # 提取并打印第二次回答的content
    assistant_content2 = response2_json['choices'][0]['message']['content']
    print("第二次回答:")
    print(assistant_content2)  # 只输出content部分

if __name__ == "__main__":
    main()
