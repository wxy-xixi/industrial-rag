import os
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from config import Config
from models import db, Document, Chunk, ChatHistory
from doc_parser import parse_file, split_text
from rag_engine import (
    add_embeddings,
    ask_llm,
    ask_multimodal_llm,
    get_embeddings_batch,
    get_indexed_chunk_count,
    load_index,
    rebuild_index,
    search_similar,
    summarize_image,
)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

# 创建表和上传目录
with app.app_context():
    db.create_all()
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
    safe_name = secure_filename(base_name)
    if not safe_name:
        name, ext = os.path.splitext(base_name)
        fallback = ''.join(ch for ch in name if ch.isalnum()) or 'document'
        safe_name = f'{fallback}{ext.lower()}'
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
    try:
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
            status='processing'
        )
        db.session.add(doc)
        db.session.commit()
        
        if ext in IMAGE_EXTENSIONS:
            text = summarize_image(filepath)
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
                'chunk_count': doc.chunk_count
            }
        })
    except Exception as e:
        db.session.rollback()
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        if doc and doc.id:
            existing_doc = db.session.get(Document, doc.id)
            if existing_doc:
                db.session.delete(existing_doc)
                db.session.commit()
        return jsonify({'code': 500, 'msg': f'处理失败: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """RAG问答接口"""
    uploaded_image = request.files.get('image')
    if uploaded_image:
        question = request.form.get('question', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
    
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
        
        # 检索相似文本
        retrieved = search_similar(question, Config.TOP_K)
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

        ordered_results = []
        for chunk_id, score in retrieved:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                ordered_results.append((chunk, score))

        context = '\n\n'.join([chunk.content for chunk, score in ordered_results])
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
            answer = ask_llm(question, context)
        
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
            'upload_time': doc.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': doc.status
        })
    return jsonify({'code': 200, 'data': data})

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
    app.run(debug=Config.DEBUG, port=5000)
