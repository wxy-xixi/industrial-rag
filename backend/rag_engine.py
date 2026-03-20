import json
import os
import base64
import mimetypes
import re

import faiss
import numpy as np
import dashscope
from dashscope import Generation, MultiModalConversation, TextEmbedding
from config import Config

INDEX_FILE = os.path.join(Config.VECTOR_STORE_DIR, 'chunks.faiss')
METADATA_FILE = os.path.join(Config.VECTOR_STORE_DIR, 'chunk_ids.json')

faiss_index = None
indexed_chunk_ids = []

def _local_file_uri(file_path):
    absolute_path = os.path.abspath(file_path)
    return f'file://{absolute_path}'

def _image_data_url(file_path):
    mime_type = mimetypes.guess_type(file_path)[0] or 'image/jpeg'
    with open(file_path, 'rb') as image_file:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'

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

def _looks_like_layout_json(text):
    stripped = (text or '').strip()
    if not stripped:
        return True
    if stripped in {'[]', '{}', '```json\n[]\n```', '```json\n{}\n```'}:
        return True
    markers = ('pos_list', 'rotate_rect', '"pos_list"', '"rotate_rect"')
    return any(marker in stripped for marker in markers)

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

def looks_like_table_chunk(text):
    content = (text or '').strip()
    if not content:
        return False
    pipe_count = content.count('|')
    if pipe_count >= 4:
        return True

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return False

    table_title_pattern = re.compile(r'^表\s*\d+[-－]?\d*')
    if any(table_title_pattern.match(line) for line in lines[:3]):
        return True

    row_like_lines = 0
    for line in lines:
        if '|' in line:
            row_like_lines += 1
            continue
        if '：' in line and any(key in line for key in ['项目', '参数', '字段', '处理方法', '渗入元素', '作用']):
            row_like_lines += 1
    return row_like_lines >= 3

def ask_llm(question, context, include_table_mode=False):
    """调用通义千问大模型生成回答"""
    _ensure_api_key()
    answer_mode = """你的回答默认采用两层结构：
1. 先给“总结回答”：用简洁、专业的语言概括核心结论。
2. 如果参考资料中出现表格、清单、字段对应关系、参数对照，请继续给“表格整理”：把表格内容按项目清晰列出，尽量保留原始对应关系。

当问题本身就是“方法及作用”“参数对照”“有哪些类别”这类查询时：
- 优先保留表格中的项目名称、元素、作用、参数值。
- 不要只做泛化概述。
- 如果表格信息不完整，要说明“以下为参考资料中检索到的部分表格内容整理”。
- 不要输出 Markdown 表格。
- 不要输出 HTML 标签，如 `<br>`、`<table>`。
- 表格整理请改用纯文本结构化列表，格式尽量类似：
  项目：渗碳及碳氮共渗
  渗入元素：C 或 C,N
  作用：提高工件的耐磨性、硬度及疲劳强度
- 不要使用 `|---|---|` 这类表格分隔符。""" if include_table_mode else """你的回答只输出“总结回答”。

当前问题不是表格查询，请只依据正文资料回答，不要输出“表格整理”，也不要引入方法-元素-作用对照表内容。"""

    prompt = f"""你是一个专业的工业领域知识助手。请严格依据参考资料回答问题，不要凭空补充。
如果参考资料中没有相关信息，请明确说明。

{answer_mode}

参考资料：
{context}

用户问题：{question}

请输出准确、专业、结构清晰的中文回答。"""

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
    image_uri = _image_data_url(image_path)
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
                {'image': image_uri},
                {'text': '请详细描述这张工业相关图片，便于后续知识库检索。'}
            ]
        }
    ]
    resp = MultiModalConversation.call(
        model=Config.VL_MODEL,
        messages=messages
    )
    return _extract_multimodal_text(resp)

def extract_pdf_page_text(image_path, page_number=None):
    """对扫描版 PDF 页面执行 OCR 风格的结构化文字抽取。"""
    _ensure_api_key()
    image_uri = _image_data_url(image_path)
    page_prefix = f'这是 PDF 的第 {page_number} 页。' if page_number else '这是 PDF 的一个页面。'
    messages = [
        {
            'role': 'user',
            'content': [
                {'image': image_uri},
                {
                    'text': (
                        f'{page_prefix}'
                        '请对该页做 OCR 风格抽取，尽量保留原文信息；'
                        '如果检测到表格，请按“字段: 数值”方式展开。'
                    )
                }
            ]
        }
    ]
    resp = MultiModalConversation.call(
        model=Config.VL_MODEL,
        messages=messages
    )
    text = _extract_multimodal_text(resp)
    if _looks_like_layout_json(text):
        raise ValueError('OCR 返回了版面坐标而非正文文本。')
    return text

def ask_multimodal_llm(question, context, image_path):
    """结合图片和检索上下文进行问答。"""
    _ensure_api_key()
    image_uri = _image_data_url(image_path)
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
                {'image': image_uri},
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
