import json
import os

import faiss
import numpy as np
import dashscope
from dashscope import Generation, MultiModalConversation, TextEmbedding
from config import Config

INDEX_FILE = os.path.join(Config.VECTOR_STORE_DIR, 'chunks.faiss')
METADATA_FILE = os.path.join(Config.VECTOR_STORE_DIR, 'chunk_ids.json')

faiss_index = None
indexed_chunk_ids = []

def ensure_vector_store_dir():
    os.makedirs(Config.VECTOR_STORE_DIR, exist_ok=True)

def _normalize_vector(vector):
    arr = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        raise ValueError('检测到空向量，无法建立索引。')
    return arr / norm

def _persist_index():
    ensure_vector_store_dir()
    if faiss_index is None or faiss_index.ntotal == 0 or not indexed_chunk_ids:
        if os.path.exists(INDEX_FILE):
            os.remove(INDEX_FILE)
        if os.path.exists(METADATA_FILE):
            os.remove(METADATA_FILE)
        return

    faiss.write_index(faiss_index, INDEX_FILE)
    with open(METADATA_FILE, 'w', encoding='utf-8') as metadata_file:
        json.dump(indexed_chunk_ids, metadata_file)

def load_index():
    global faiss_index, indexed_chunk_ids

    ensure_vector_store_dir()
    if not (os.path.exists(INDEX_FILE) and os.path.exists(METADATA_FILE)):
        faiss_index = None
        indexed_chunk_ids = []
        return False

    faiss_index = faiss.read_index(INDEX_FILE)
    with open(METADATA_FILE, 'r', encoding='utf-8') as metadata_file:
        indexed_chunk_ids = json.load(metadata_file)
    return True

def get_indexed_chunk_count():
    return len(indexed_chunk_ids)

def rebuild_index(chunks):
    global faiss_index, indexed_chunk_ids

    ensure_vector_store_dir()
    vectors = []
    ids = []
    dimension = None

    for chunk in chunks:
        if not chunk.embedding:
            continue
        vector = np.frombuffer(chunk.embedding, dtype=np.float64)
        normalized = _normalize_vector(vector)
        if dimension is None:
            dimension = normalized.shape[0]
        vectors.append(normalized)
        ids.append(chunk.id)

    if not vectors:
        faiss_index = None
        indexed_chunk_ids = []
        _persist_index()
        return

    matrix = np.vstack(vectors).astype(np.float32)
    faiss_index = faiss.IndexFlatIP(matrix.shape[1])
    faiss_index.add(matrix)
    indexed_chunk_ids = ids
    _persist_index()

def add_embeddings(chunk_ids, embeddings):
    global faiss_index, indexed_chunk_ids

    if not chunk_ids or not embeddings:
        return

    normalized = np.vstack([_normalize_vector(embedding) for embedding in embeddings]).astype(np.float32)
    if faiss_index is None:
        faiss_index = faiss.IndexFlatIP(normalized.shape[1])
        indexed_chunk_ids = []

    faiss_index.add(normalized)
    indexed_chunk_ids.extend(chunk_ids)
    _persist_index()

def _ensure_api_key():
    if not Config.DASHSCOPE_API_KEY:
        raise ValueError('未配置 DASHSCOPE_API_KEY，请先在环境变量或 .env 中设置。')
    dashscope.api_key = Config.DASHSCOPE_API_KEY

def _extract_multimodal_text(resp):
    if resp.status_code != 200:
        raise Exception(f'多模态调用失败: {resp.message}')

    if not resp.output or not resp.output.choices:
        return ''

    message = resp.output.choices[0].message
    content = message.content
    if isinstance(content, str):
        return content

    parts = []
    for item in content or []:
        if isinstance(item, dict) and item.get('text'):
            parts.append(item['text'])
    return '\n'.join(parts).strip()

def get_embedding(text):
    """调用通义千问获取文本向量"""
    _ensure_api_key()
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
    if not texts:
        return []

    _ensure_api_key()
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

def search_similar(question, top_k=3):
    """基于 FAISS 检索最相似的文本块。"""
    if faiss_index is None or faiss_index.ntotal == 0 or not indexed_chunk_ids:
        return []

    q_embedding = _normalize_vector(get_embedding(question)).reshape(1, -1)
    scores, indices = faiss_index.search(q_embedding, min(top_k, len(indexed_chunk_ids)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(indexed_chunk_ids):
            continue
        results.append((indexed_chunk_ids[idx], float(score)))
    return results

def ask_llm(question, context):
    """调用通义千问大模型生成回答"""
    _ensure_api_key()
    prompt = f"""你是一个专业的工业领域知识助手。请根据以下参考资料回答用户问题。
如果参考资料中没有相关信息，请如实告知。

参考资料：
{context}

用户问题：{question}

请给出准确、专业的回答："""

    resp = Generation.call(
        model=Config.TEXT_MODEL,
        prompt=prompt
    )
    
    if resp.status_code == 200:
        return resp.output.text
    else:
        raise Exception(f'生成回答失败: {resp.message}')

def summarize_image(image_path):
    """将工业图片转为可检索文本摘要。"""
    _ensure_api_key()
    messages = [
        {
            'role': 'system',
            'content': [
                {
                    'text': (
                        '你是工业知识抽取助手。请对图片进行结构化描述，重点提取：'
                        '设备/部件名称、场景用途、可见文字或参数、告警状态、操作界面信息、'
                        '以及后续检索有价值的关键词。输出中文。'
                    )
                }
            ]
        },
        {
            'role': 'user',
            'content': [
                {'image': image_path},
                {'text': '请详细描述这张工业相关图片，便于后续知识库检索。'}
            ]
        }
    ]
    resp = MultiModalConversation.call(
        model=Config.VL_MODEL,
        messages=messages
    )
    return _extract_multimodal_text(resp)

def ask_multimodal_llm(question, context, image_path):
    """结合图片和检索上下文进行问答。"""
    _ensure_api_key()
    messages = [
        {
            'role': 'system',
            'content': [
                {
                    'text': (
                        '你是一个专业的工业领域多模态知识助手。请结合提供的图片和参考资料作答。'
                        '如果图片与参考资料冲突，先说明冲突，再给出判断；如果信息不足，请明确说明。'
                    )
                }
            ]
        },
        {
            'role': 'user',
            'content': [
                {'image': image_path},
                {
                    'text': (
                        f'参考资料：\n{context or "无"}\n\n'
                        f'用户问题：{question}\n\n'
                        '请给出准确、专业的中文回答。'
                    )
                }
            ]
        }
    ]
    resp = MultiModalConversation.call(
        model=Config.VL_MODEL,
        messages=messages
    )
    return _extract_multimodal_text(resp)
