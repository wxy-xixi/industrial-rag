from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Document(db.Model):
    """文档表"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(255), nullable=False, comment='文件名')
    file_type = db.Column(db.String(20), nullable=False, comment='文件类型')
    file_size = db.Column(db.Integer, comment='文件大小(字节)')
    chunk_count = db.Column(db.Integer, default=0, comment='分块数量')
    category = db.Column(db.String(50), default='未分类', comment='文档分类')
    upload_time = db.Column(db.DateTime, default=datetime.now, comment='上传时间')
    status = db.Column(db.String(20), default='processing', comment='状态')
    
    chunks = db.relationship('Chunk', backref='document', cascade='all, delete-orphan')

class Chunk(db.Model):
    """文档分块表"""
    __tablename__ = 'chunks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    content = db.Column(db.Text, nullable=False, comment='文本内容')
    embedding = db.Column(db.LargeBinary, comment='向量数据')
    chunk_index = db.Column(db.Integer, comment='分块序号')

class ChatHistory(db.Model):
    """对话记录表"""
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.Text, nullable=False, comment='用户问题')
    answer = db.Column(db.Text, nullable=False, comment='AI回答')
    sources = db.Column(db.Text, comment='引用来源')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
