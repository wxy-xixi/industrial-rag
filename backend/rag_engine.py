import numpy as np
import dashscope
from dashscope import TextEmbedding, Generation
from config import Config

dashscope.api_key = Config.DASHSCOPE_API_KEY

def get_embedding(text):
    """调用通义千问获取文本向量"""
    resp = TextEmbedding.call(
        model='text-embedding-v2',
        input=text
    )
    if resp.status_code == 200:
        return resp.output['embeddings'][0]['embedding']
    else:
        raise Exception(f'向量化失败: {resp.message}')

def get_embeddings_batch(texts):
    """批量获取向量"""
    embeddings = []
    # 每次最多25条
    for i in range(0, len(texts), 25):
        batch = texts[i:i+25]
        resp = TextEmbedding.call(
            model='text-embedding-v2',
            input=batch
        )
        if resp.status_code == 200:
            for item in resp.output['embeddings']:
                embeddings.append(item['embedding'])
        else:
            raise Exception(f'批量向量化失败: {resp.message}')
    return embeddings

def cosine_similarity(vec1, vec2):
    """计算余弦相似度"""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def search_similar(question, chunks, top_k=3):
    """检索最相似的文本块"""
    q_embedding = get_embedding(question)
    
    scores = []
    for chunk in chunks:
        if chunk.embedding is None:
            continue
        c_embedding = np.frombuffer(chunk.embedding, dtype=np.float64).tolist()
        score = cosine_similarity(q_embedding, c_embedding)
        scores.append((chunk, score))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]

def ask_llm(question, context):
    """调用通义千问大模型生成回答"""
    prompt = f"""你是一个专业的工业领域知识助手。请根据以下参考资料回答用户问题。
如果参考资料中没有相关信息，请如实告知。

参考资料：
{context}

用户问题：{question}

请给出准确、专业的回答："""

    resp = Generation.call(
        model='qwen-turbo',
        prompt=prompt
    )
    
    if resp.status_code == 200:
        return resp.output.text
    else:
        raise Exception(f'生成回答失败: {resp.message}')