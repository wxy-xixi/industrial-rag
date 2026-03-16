import os
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from models import db, Document, Chunk, ChatHistory
from doc_parser import parse_file, split_text
from rag_engine import get_embeddings_batch, search_similar, ask_llm

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

# 创建表和上传目录
with app.app_context():
    db.create_all()
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传并解析文档"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'msg': '未选择文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 400, 'msg': '文件名为空'}), 400
    
    # 检查格式
    allowed = {'.pdf', '.docx', '.txt'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'code': 400, 'msg': '仅支持PDF、DOCX、TXT格式'}), 400
    
    try:
        # 保存文件
        filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        # 记录到数据库
        doc = Document(
            filename=file.filename,
            file_type=ext.replace('.', ''),
            file_size=file_size,
            status='processing'
        )
        db.session.add(doc)
        db.session.commit()
        
        # 解析文档
        text = parse_file(filepath)
        chunks = split_text(text, Config.CHUNK_SIZE, Config.CHUNK_OVERLAP)
        
        # 批量向量化
        embeddings = get_embeddings_batch(chunks)
        
        # 存入分块表
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                doc_id=doc.id,
                content=chunk_text,
                embedding=np.array(embedding, dtype=np.float64).tobytes(),
                chunk_index=i
            )
            db.session.add(chunk)
        
        doc.chunk_count = len(chunks)
        doc.status = 'completed'
        db.session.commit()
        
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
        return jsonify({'code': 500, 'msg': f'处理失败: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """RAG问答接口"""
    data = request.get_json()
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'code': 400, 'msg': '问题不能为空'}), 400
    
    try:
        # 获取所有分块
        all_chunks = Chunk.query.all()
        if not all_chunks:
            return jsonify({'code': 200, 'data': {
                'answer': '知识库为空，请先上传文档。',
                'sources': []
            }})
        
        # 检索相似文本
        results = search_similar(question, all_chunks, Config.TOP_K)
        
        # 拼接上下文
        context = '\n\n'.join([chunk.content for chunk, score in results])
        sources = []
        for chunk, score in results:
            doc = Document.query.get(chunk.doc_id)
            sources.append({
                'filename': doc.filename if doc else '未知',
                'content': chunk.content[:100] + '...',
                'score': round(float(score), 4)
            })
        
        # 调用大模型
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
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'code': 404, 'msg': '文档不存在'}), 404
    
    # 删除文件
    filepath = os.path.join(Config.UPLOAD_FOLDER, doc.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(doc)
    db.session.commit()
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
    app.run(debug=True, port=5000)