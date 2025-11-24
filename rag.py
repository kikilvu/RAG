import os
import requests
import json
from dotenv import load_dotenv
# 新的导入方式
from langchain.text_splitter import RecursiveCharacterTextSplitter  # 这个目前还在 langchain 主包中
from langchain_community.vectorstores import FAISS
from langchain_community.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings  # 从 langchain-openai 导入
# 加载环境变量
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --------------------------
# 1. 文档加载与分割
# --------------------------
def load_and_split_documents(document_text: str, chunk_size: int = 500, chunk_overlap: int = 50):
    """
    加载文本并分割成小块
    :param document_text: 原始文档文本
    :param chunk_size: 每个块的最大长度
    :param chunk_overlap: 块之间的重叠长度
    :return: 分割后的文档块列表
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = text_splitter.split_text(document_text)
    return chunks

# --------------------------
# 2. 向量存储初始化
# --------------------------
def init_vector_store(chunks: list, embedding_model: str = "text-embedding-3-small"):
    """
    初始化向量存储（FAISS）
    :param chunks: 文档块列表
    :param embedding_model: OpenAI 的嵌入模型
    :return: FAISS 向量库
    """
    # 使用 OpenAI 的嵌入模型（也可以替换为其他嵌入模型）
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        openai_api_key=OPENROUTER_API_KEY,  # OpenRouter 兼容 OpenAI 的嵌入 API
        openai_api_base="https://openrouter.ai/api/v1"  # OpenRouter 的 API 基础地址
    )
    # 初始化 FAISS 向量库
    vector_store = FAISS.from_texts(chunks, embeddings)
    return vector_store

# --------------------------
# 3. 自定义 OpenRouter LLM 包装器
# --------------------------
class OpenRouterLLM(OpenAI):
    """
    自定义 OpenRouter LLM 包装器，兼容 LangChain
    """
    def __init__(self, model_name: str = "x-ai/grok-4.1-fast:free", **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.api_key = OPENROUTER_API_KEY
        self.api_base = "https://openrouter.ai/api/v1"

    def _call(self, prompt: str, stop=None, **kwargs):
        """
        调用 OpenRouter API 生成回答
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7),
            # 保留 reasoning 功能（可选）
            "extra_body": {"reasoning": {"enabled": True}} if kwargs.get("reasoning", False) else {}
        }
        response = requests.post(
            url=f"{self.api_base}/chat/completions",
            headers=headers,
            data=json.dumps(data)
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

# --------------------------
# 4. 构建 RAG 链
# --------------------------
def build_rag_chain(vector_store: FAISS, model_name: str = "x-ai/grok-4.1-fast:free"):
    """
    构建 RAG 链
    :param vector_store: FAISS 向量库
    :param model_name: OpenRouter 模型名称
    :return: RetrievalQA 链
    """
    # 初始化检索器（从向量库中检索相关文档）
    retriever = vector_store.as_retriever(
        search_kwargs={"k": 3}  # 检索 top 3 相关文档块
    )

    # 初始化 OpenRouter LLM
    llm = OpenRouterLLM(
        model_name=model_name,
        temperature=0.5,
        reasoning=True  # 启用 reasoning 功能
    )

    # 定义 RAG 提示模板（将问题和检索到的上下文结合）
    prompt_template = """
    You are a helpful assistant. Answer the user's question based on the following context. If the context doesn't contain the answer, say "I don't have enough information to answer this question."

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )

    # 构建 RetrievalQA 链
    rag_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",  # 将检索到的上下文直接填入提示模板
        retriever=retriever,
        chain_type_kwargs={"prompt": PROMPT},
        return_source_documents=True  # 返回检索到的源文档（可选）
    )

    return rag_chain

# --------------------------
# 5. 主函数：运行 RAG 系统
# --------------------------
def main():
    # 示例：外部知识库（可以替换为本地文件、数据库等）
    document_text = """
    草莓（学名：Fragaria × ananassa Duch.）是蔷薇科草莓属多年生草本植物。草莓的果实呈心形，颜色鲜艳，果肉多汁，味道酸甜可口。草莓富含维生素C、维生素E、膳食纤维以及多种矿物质，对人体健康有益。

    草莓的种植历史可以追溯到17世纪的欧洲，如今已在全球广泛种植。草莓的生长需要充足的阳光、适宜的温度和肥沃的土壤。常见的草莓品种有红颜、章姬、甜查理等。

    草莓的食用方法多样，可以直接食用，也可以制作成果酱、果汁、蛋糕等甜点。此外，草莓还具有一定的药用价值，传统中医认为其具有生津止渴、润肺化痰等功效。
    """

    # 步骤 1：加载并分割文档
    print("Loading and splitting documents...")
    chunks = load_and_split_documents(document_text)
    print(f"Split into {len(chunks)} chunks.")

    # 步骤 2：初始化向量存储
    print("Initializing vector store...")
    vector_store = init_vector_store(chunks)
    print("Vector store initialized.")

    # 步骤 3：构建 RAG 链
    print("Building RAG chain...")
    rag_chain = build_rag_chain(vector_store)
    print("RAG chain built.")

    # 步骤 4：用户交互
    print("\nRAG Assistant is ready! Ask a question about strawberries.")
    while True:
        question = input("\nYou: ")
        if question.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        
        print("Thinking...")
        # 调用 RAG 链生成回答
        result = rag_chain({"query": question})
        
        # 输出结果
        print(f"\nAssistant: {result['result']}")
        
        # 可选：输出检索到的源文档
        print("\nSource Documents:")
        for i, doc in enumerate(result["source_documents"]):
            print(f"[{i+1}] {doc.page_content}")

if __name__ == "__main__":
    main()