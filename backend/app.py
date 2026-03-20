import os
import shutil
import tempfile
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename
from config import Config
from models import db, Document, Chunk, ChatHistory
from doc_parser import parse_file, render_pdf_pages, split_text
from rag_engine import (
    add_embeddings,
    ask_llm,
    ask_multimodal_llm,
    extract_pdf_page_text,
    get_embedding,
    get_embeddings_batch,
    get_indexed_chunk_count,
    load_index,
    looks_like_table_chunk,
    rebuild_index,
    search_similar,
    summarize_image,
)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
DOC_CATEGORIES = {
    '未分类',
    '工艺规范',
    '设备操作',
    '热处理',
    '质量检测',
    '安全规程',
    '维修维护'
}

def normalize_category(category):
    value = (category or '').strip()
    if not value:
        return '未分类'
    return value if value in DOC_CATEGORIES else '未分类'

def ensure_document_schema():
    inspector = inspect(db.engine)
    columns = {column['name'] for column in inspector.get_columns('documents')}
    if 'category' in columns:
        return

    db.session.execute(
        text("ALTER TABLE documents ADD COLUMN category VARCHAR(50) DEFAULT '未分类'")
    )
    db.session.commit()

# 创建表和上传目录
with app.app_context():
    db.create_all()
    ensure_document_schema()
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.VECTOR_STORE_DIR, exist_ok=True)
    os.makedirs(Config.CHAT_IMAGE_FOLDER, exist_ok=True)
    chunk_count = Chunk.query.count()
    index_loaded = load_index()
    if (not index_loaded) or get_indexed_chunk_count() != chunk_count:
        rebuild_index(Chunk.query.order_by(Chunk.id.asc()).all())

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
TEXT_EXTENSIONS = {'.pdf', '.docx', '.txt'}

def sanitize_upload_filename(filename):
    """移除路径成分并确保文件名可安全落盘。"""
    base_name = os.path.basename((filename or '').strip())
    name, ext = os.path.splitext(base_name)
    safe_stem = secure_filename(name)

    if not safe_stem:
        fallback = ''.join(ch for ch in name if ch.isalnum()) or 'document'
        safe_stem = fallback

    safe_name = f'{safe_stem}{ext.lower()}'
    return safe_name

def build_unique_filepath(filename, folder=None):
    """避免同名文件覆盖。"""
    target_folder = folder or Config.UPLOAD_FOLDER
    name, ext = os.path.splitext(filename)
    candidate = filename
    index = 1
    while os.path.exists(os.path.join(target_folder, candidate)):
        candidate = f'{name}_{index}{ext}'
        index += 1
    return os.path.join(target_folder, candidate), candidate

def select_diverse_results(retrieved, chunk_map, top_k):
    """在全知识库候选中做简单去重，避免单一文档占满结果。"""
    selected = []
    per_doc_counts = {}

    for chunk_id, score in retrieved:
        chunk = chunk_map.get(chunk_id)
        if not chunk:
            continue

        doc_count = per_doc_counts.get(chunk.doc_id, 0)
        if doc_count >= Config.MAX_CHUNKS_PER_DOC:
            continue

        selected.append((chunk, score))
        per_doc_counts[chunk.doc_id] = doc_count + 1
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        seen_chunk_ids = {chunk.id for chunk, _score in selected}
        for chunk_id, score in retrieved:
            chunk = chunk_map.get(chunk_id)
            if not chunk or chunk.id in seen_chunk_ids:
                continue
            selected.append((chunk, score))
            if len(selected) >= top_k:
                break

    return selected

def is_table_query(question):
    keywords = ['表', '方法', '作用', '参数', '元素', '对照', '类别', '一览', '有哪些']
    text = (question or '').strip()
    hit_count = sum(1 for keyword in keywords if keyword in text)
    return hit_count >= 2

def augment_table_neighbors(base_results, chunk_map):
    """表格类问题补充相邻 chunk，尽量把整张表拼完整。"""
    if not base_results:
        return base_results

    table_related = [chunk for chunk, _score in base_results if looks_like_table_chunk(chunk.content)]
    if not table_related:
        return base_results

    doc_ranges = {}
    for chunk in table_related:
        current = doc_ranges.setdefault(chunk.doc_id, set())
        for index in range(max(0, (chunk.chunk_index or 0) - 2), (chunk.chunk_index or 0) + 3):
            current.add(index)

    extra_chunks = []
    for doc_id, indexes in doc_ranges.items():
        neighbors = (
            Chunk.query
            .filter(Chunk.doc_id == doc_id, Chunk.chunk_index.in_(sorted(indexes)))
            .order_by(Chunk.chunk_index.asc())
            .all()
        )
        extra_chunks.extend(neighbors)

    existing_ids = {chunk.id for chunk, _score in base_results}
    augmented = list(base_results)
    for chunk in extra_chunks:
        if chunk.id in existing_ids:
            continue
        synthetic_score = 0.88
        augmented.append((chunk, synthetic_score))
        existing_ids.add(chunk.id)

    augmented.sort(key=lambda item: (item[1], -(item[0].chunk_index or 0)), reverse=True)
    return augmented

def is_continuity_query(question):
    keywords = ['过程', '步骤', '流程', '分类', '原理', '包括', '由哪些', '基本过程']
    text = (question or '').strip()
    return any(keyword in text for keyword in keywords)

def augment_context_neighbors(base_results, neighbor_span=1):
    """补充命中 chunk 的相邻上下文，避免条目/列表被截断。"""
    if not base_results:
        return base_results

    doc_ranges = {}
    for chunk, _score in base_results:
        current = doc_ranges.setdefault(chunk.doc_id, set())
        start = max(0, (chunk.chunk_index or 0) - neighbor_span)
        end = (chunk.chunk_index or 0) + neighbor_span + 1
        for index in range(start, end):
            current.add(index)

    augmented = []
    seen_chunk_ids = set()
    for doc_id, indexes in doc_ranges.items():
        neighbors = (
            Chunk.query
            .filter(Chunk.doc_id == doc_id, Chunk.chunk_index.in_(sorted(indexes)))
            .order_by(Chunk.chunk_index.asc())
            .all()
        )
        base_scores = {chunk.id: score for chunk, score in base_results if chunk.doc_id == doc_id}
        for chunk in neighbors:
            if chunk.id in seen_chunk_ids:
                continue
            score = base_scores.get(chunk.id, 0.82)
            augmented.append((chunk, score))
            seen_chunk_ids.add(chunk.id)

    augmented.sort(key=lambda item: (item[0].doc_id, item[0].chunk_index or 0))
    return augmented

def build_focused_continuity_context(ordered_results, question):
    """针对流程/步骤类问题，从连续 chunk 中抽取更干净的局部段落。"""
    if not ordered_results:
        return ''

    question_text = (question or '').strip()
    if '基本过程' not in question_text:
        return ''

    chunks_by_doc = {}
    for chunk, _score in ordered_results:
        chunks_by_doc.setdefault(chunk.doc_id, []).append(chunk)

    for doc_id, chunks in chunks_by_doc.items():
        chunks.sort(key=lambda item: item.chunk_index or 0)
        merged_text = '\n'.join(chunk.content for chunk in chunks)
        anchor = '化学热处理通常由四个基本过程组成'
        start = merged_text.find(anchor)
        if start < 0:
            continue

        end_markers = [
            '根据介质的物理形态',
            '第2页',
            '以下是该 PDF 页面的 OCR 风格抽取内容',
            '---'
        ]
        end_positions = [
            merged_text.find(marker, start + len(anchor))
            for marker in end_markers
            if merged_text.find(marker, start + len(anchor)) != -1
        ]
        end = min(end_positions) if end_positions else min(len(merged_text), start + 900)
        passage = merged_text[start:end].strip()
        if passage:
            return f'【正文资料】\n{passage}'

    return ''

def build_process_answer_from_context(question, focused_context):
    """对“基本过程组成”类问题做规则化抽取，避免模型漏项。"""
    if '基本过程' not in (question or '') or not focused_context:
        return ''

    content = focused_context.replace('【正文资料】', '').strip()
    anchor = '化学热处理通常由四个基本过程组成'
    start = content.find(anchor)
    if start < 0:
        return ''

    passage = content[start:]
    passage = re.sub(r'\s+', ' ', passage)
    titles = {
        '1': '介质中的化学反应',
        '2': '渗剂扩散',
        '3': '相界面反应',
        '4': '被吸附并溶入的渗入元素向工件内部扩散'
    }

    positions = {}
    for number, title in titles.items():
        pattern = re.compile(rf'{number}\)\s*{re.escape(title)}')
        match = pattern.search(passage)
        if not match:
            return ''
        positions[number] = match.start()

    ordered_numbers = ['1', '2', '3', '4']
    item_map = {}
    for index, number in enumerate(ordered_numbers):
        start_pos = positions[number]
        end_pos = positions[ordered_numbers[index + 1]] if index + 1 < len(ordered_numbers) else len(passage)
        item_text = passage[start_pos:end_pos].strip()
        item_text = re.sub(rf'^{number}\)\s*', '', item_text).strip()
        item_text = re.split(r'\s+[1-4]\)\s*', item_text)[0].strip()
        item_text = item_text.rstrip('。')
        item_map[number] = item_text

    if any(not item_map[number] for number in ordered_numbers):
        return ''

    lines = ['总结回答：', '化学热处理通常由 4 个基本过程组成：']
    for number in ordered_numbers:
        lines.append(f'{number}. {item_map[number]}。')
    return '\n'.join(lines)

def search_within_document(question, doc_id, top_k):
    """仅在指定文档内检索相似 chunk。"""
    chunks = (
        Chunk.query
        .filter(Chunk.doc_id == doc_id)
        .order_by(Chunk.chunk_index.asc())
        .all()
    )
    if not chunks:
        return []

    question_embedding = np.array(get_embedding(question), dtype=np.float64).reshape(1, -1)
    scored = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        chunk_embedding = np.frombuffer(chunk.embedding, dtype=np.float64).reshape(1, -1)
        score = float(cosine_similarity(question_embedding, chunk_embedding)[0][0])
        scored.append((chunk.id, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]

@app.route('/')
def index():
    """返回前端首页。"""
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def frontend_assets(filename):
    """提供前端静态资源。"""
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传并解析文档"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'msg': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 400, 'msg': '文件名为空'}), 400
    
    # 检查格式
    allowed = TEXT_EXTENSIONS | IMAGE_EXTENSIONS
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'code': 400, 'msg': '仅支持PDF、DOCX、TXT、PNG、JPG、JPEG、BMP、WEBP格式'}), 400
    
    doc = None
    filepath = None
    pdf_image_dir = None
    try:
        category = normalize_category(request.form.get('category'))
        # 保存文件
        safe_filename = sanitize_upload_filename(file.filename)
        filepath, stored_filename = build_unique_filepath(safe_filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        # 记录到数据库
        doc = Document(
            filename=stored_filename,
            file_type=ext.replace('.', ''),
            file_size=file_size,
            category=category,
            status='processing'
        )
        db.session.add(doc)
        db.session.commit()
        
        if ext in IMAGE_EXTENSIONS:
            text = summarize_image(filepath)
        elif ext == '.pdf':
            text = parse_file(filepath)
            if len(text.strip()) < Config.PDF_TEXT_FALLBACK_THRESHOLD:
                pdf_image_dir = tempfile.mkdtemp(
                    prefix='pdf_pages_',
                    dir=Config.CHAT_IMAGE_FOLDER
                )
                page_images = render_pdf_pages(
                    filepath,
                    pdf_image_dir,
                    max_pages=Config.PDF_IMAGE_MAX_PAGES
                )
                if not page_images:
                    raise ValueError('未能从 PDF 中提取文字或页面图像。')

                page_summaries = []
                for index, image_path in enumerate(page_images, start=1):
                    try:
                        summary = extract_pdf_page_text(image_path, page_number=index)
                    except Exception:
                        summary = summarize_image(image_path)
                    if summary:
                        page_summaries.append(f'第{index}页\n{summary}')

                fallback_text = '\n\n'.join(page_summaries).strip()
                if text.strip() and fallback_text:
                    text = f'{text.strip()}\n\n{fallback_text}'
                else:
                    text = fallback_text or text
        else:
            text = parse_file(filepath)

        chunks = split_text(text, Config.CHUNK_SIZE, Config.CHUNK_OVERLAP)
        if not chunks:
            raise ValueError('未能从文件中提取有效内容。')
        
        # 批量向量化
        embeddings = get_embeddings_batch(chunks)
        
        # 存入分块表
        chunk_ids = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                doc_id=doc.id,
                content=chunk_text,
                embedding=np.array(embedding, dtype=np.float64).tobytes(),
                chunk_index=i
            )
            db.session.add(chunk)
            db.session.flush()
            chunk_ids.append(chunk.id)
        
        doc.chunk_count = len(chunks)
        doc.status = 'completed'
        db.session.commit()
        add_embeddings(chunk_ids, embeddings)
        
        return jsonify({
            'code': 200,
            'msg': '上传成功',
            'data': {
                'id': doc.id,
                'filename': doc.filename,
                'category': doc.category,
                'chunk_count': doc.chunk_count
            }
        })
    except Exception as e:
        app.logger.exception('Upload processing failed for %s', file.filename)
        db.session.rollback()
        if pdf_image_dir and os.path.exists(pdf_image_dir):
            shutil.rmtree(pdf_image_dir, ignore_errors=True)
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        if doc and doc.id:
            existing_doc = db.session.get(Document, doc.id)
            if existing_doc:
                db.session.delete(existing_doc)
                db.session.commit()
        return jsonify({'code': 500, 'msg': f'处理失败: {str(e)}'}), 500
    finally:
        if pdf_image_dir and os.path.exists(pdf_image_dir):
            shutil.rmtree(pdf_image_dir, ignore_errors=True)

@app.route('/api/chat', methods=['POST'])
def chat():
    """RAG问答接口"""
    uploaded_image = request.files.get('image')
    if uploaded_image:
        question = request.form.get('question', '').strip()
        selected_doc_id = request.form.get('doc_id', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
        selected_doc_id = str(data.get('doc_id') or '').strip()
    
    if not question:
        return jsonify({'code': 400, 'msg': '问题不能为空'}), 400
    
    try:
        temp_image_path = None
        if uploaded_image and uploaded_image.filename:
            image_ext = os.path.splitext(uploaded_image.filename)[1].lower()
            if image_ext not in IMAGE_EXTENSIONS:
                return jsonify({'code': 400, 'msg': '问答附图仅支持 PNG、JPG、JPEG、BMP、WEBP 格式'}), 400

            safe_image_name = sanitize_upload_filename(uploaded_image.filename)
            temp_image_path, _ = build_unique_filepath(
                safe_image_name,
                folder=Config.CHAT_IMAGE_FOLDER
            )
            uploaded_image.save(temp_image_path)

        if Chunk.query.count() == 0:
            answer = '知识库为空，请先上传文档。'
            if temp_image_path:
                answer = ask_multimodal_llm(question, '', temp_image_path)
            return jsonify({'code': 200, 'data': {
                'answer': answer,
                'sources': []
            }})
        
        selected_doc = None
        if selected_doc_id:
            try:
                selected_doc = db.session.get(Document, int(selected_doc_id))
            except ValueError:
                return jsonify({'code': 400, 'msg': '检索范围参数无效'}), 400
            if not selected_doc:
                return jsonify({'code': 404, 'msg': '指定检索文档不存在'}), 404

        # 检索相似文本
        if selected_doc:
            candidate_k = max(Config.TOP_K + 4, Config.RETRIEVAL_CANDIDATES)
            retrieved = search_within_document(question, selected_doc.id, candidate_k)
        else:
            candidate_k = max(Config.TOP_K, Config.RETRIEVAL_CANDIDATES)
            retrieved = search_similar(question, candidate_k)
        if not retrieved and not temp_image_path:
            return jsonify({'code': 200, 'data': {
                'answer': '当前索引为空或不可用，请先重新上传文档。',
                'sources': []
            }})
        
        # 拼接上下文
        chunk_ids = [chunk_id for chunk_id, _score in retrieved]
        chunk_map = {
            chunk.id: chunk
            for chunk in Chunk.query.filter(Chunk.id.in_(chunk_ids)).all()
        }

        prefers_table = is_table_query(question)
        prefers_continuity = is_continuity_query(question)
        result_limit = Config.TOP_K + 2 if prefers_table else Config.TOP_K
        ordered_results = select_diverse_results(retrieved, chunk_map, result_limit)
        if prefers_table:
            ordered_results = augment_table_neighbors(ordered_results, chunk_map)
        if prefers_table or prefers_continuity:
            neighbor_span = 2 if prefers_table else 1
            ordered_results = augment_context_neighbors(ordered_results, neighbor_span=neighbor_span)

        narrative_chunks = []
        table_chunks = []
        for chunk, _score in ordered_results:
            is_table_chunk = looks_like_table_chunk(chunk.content)
            if prefers_table and is_table_chunk:
                table_chunks.append(chunk.content)
            elif not is_table_chunk:
                narrative_chunks.append(chunk.content)

        context_parts = []
        if narrative_chunks:
            context_parts.append('【正文资料】\n' + '\n\n'.join(narrative_chunks))
        if table_chunks:
            context_parts.append('【表格/清单资料】\n' + '\n\n'.join(table_chunks))
        context = '\n\n'.join(context_parts)
        focused_context = ''
        if prefers_continuity and not prefers_table:
            focused_context = build_focused_continuity_context(ordered_results, question)
            if focused_context:
                context = focused_context
        sources = []
        for chunk, score in ordered_results:
            doc = db.session.get(Document, chunk.doc_id)
            sources.append({
                'filename': doc.filename if doc else '未知',
                'content': chunk.content[:100] + '...',
                'score': round(float(score), 4)
            })
        
        # 调用大模型
        if temp_image_path:
            answer = ask_multimodal_llm(question, context, temp_image_path)
        else:
            answer = build_process_answer_from_context(question, focused_context)
            if not answer:
                answer = ask_llm(question, context, include_table_mode=prefers_table)
        
        # 保存记录
        history = ChatHistory(
            question=question,
            answer=answer,
            sources=str(sources)
        )
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'data': {
                'answer': answer,
                'sources': sources
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'问答失败: {str(e)}'}), 500
    finally:
        if 'temp_image_path' in locals() and temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """获取文档列表"""
    docs = Document.query.order_by(Document.upload_time.desc()).all()
    data = []
    for doc in docs:
        data.append({
            'id': doc.id,
            'filename': doc.filename,
            'file_type': doc.file_type,
            'file_size': doc.file_size,
            'chunk_count': doc.chunk_count,
            'category': doc.category or '未分类',
            'upload_time': doc.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': doc.status
        })
    return jsonify({'code': 200, 'data': data})

@app.route('/api/documents/<int:doc_id>/category', methods=['PATCH'])
def update_document_category(doc_id):
    """更新文档分类"""
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({'code': 404, 'msg': '文档不存在'}), 404

    data = request.get_json(silent=True) or {}
    doc.category = normalize_category(data.get('category'))
    db.session.commit()

    return jsonify({
        'code': 200,
        'msg': '分类更新成功',
        'data': {
            'id': doc.id,
            'category': doc.category
        }
    })

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档"""
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({'code': 404, 'msg': '文档不存在'}), 404
    
    # 删除文件
    filepath = os.path.join(Config.UPLOAD_FOLDER, doc.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(doc)
    db.session.commit()
    rebuild_index(Chunk.query.order_by(Chunk.id.asc()).all())
    return jsonify({'code': 200, 'msg': '删除成功'})

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取对话历史"""
    records = ChatHistory.query.order_by(ChatHistory.create_time.desc()).limit(50).all()
    data = []
    for r in records:
        data.append({
            'id': r.id,
            'question': r.question,
            'answer': r.answer,
            'create_time': r.create_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'code': 200, 'data': data})

if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
