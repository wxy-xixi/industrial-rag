import os

def load_env_file():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

load_env_file()

class Config:
    BASE_DIR = os.path.dirname(__file__)

    # 数据库配置，默认使用本地 SQLite，便于直接运行演示
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'industrial_rag.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    VECTOR_STORE_DIR = os.path.join(BASE_DIR, 'vector_store')
    CHAT_IMAGE_FOLDER = os.path.join(BASE_DIR, 'chat_images')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
    
    # 通义千问 API 配置
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    
    # RAG配置
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 500))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 50))
    TOP_K = int(os.getenv('TOP_K', 3))
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    TEXT_MODEL = os.getenv('TEXT_MODEL', 'qwen-turbo')
    VL_MODEL = os.getenv('VL_MODEL', 'qwen-vl-chat-v1')
