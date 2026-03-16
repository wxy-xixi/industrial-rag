import os

class Config:
    # MySQL数据库配置
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root123@localhost:3306/industrial_rag'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 最大50MB
    
    # 通义千问API配置
    DASHSCOPE_API_KEY = 'sk-b56e8fe969af4ca88d7fe285a893cdff'
    
    # RAG配置
    CHUNK_SIZE = 500        # 文本分块大小
    CHUNK_OVERLAP = 50      # 分块重叠字符数
    TOP_K = 3               # 检索返回前K个结果