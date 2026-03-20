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

def resolve_path(path_value, default_path):
    if not path_value:
        return default_path
    if os.path.isabs(path_value):
        return path_value
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(project_root, path_value)

def resolve_database_url():
    default_sqlite_path = os.path.join(os.path.dirname(__file__), 'industrial_rag.db')
    database_url = os.getenv('DATABASE_URL', f'sqlite:///{default_sqlite_path}')

    if database_url.startswith('sqlite:///') and not database_url.startswith('sqlite:////'):
        relative_path = database_url.replace('sqlite:///', '', 1)
        absolute_path = resolve_path(relative_path, default_sqlite_path)
        return f'sqlite:///{absolute_path}'

    return database_url

class Config:
    BASE_DIR = os.path.dirname(__file__)
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))

    # 数据库配置，默认使用本地 SQLite，便于直接运行演示
    SQLALCHEMY_DATABASE_URI = resolve_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    
    # 上传文件配置
    UPLOAD_FOLDER = resolve_path(
        os.getenv('UPLOAD_FOLDER'),
        os.path.join(BASE_DIR, 'uploads')
    )
    VECTOR_STORE_DIR = resolve_path(
        os.getenv('VECTOR_STORE_DIR'),
        os.path.join(BASE_DIR, 'vector_store')
    )
    CHAT_IMAGE_FOLDER = resolve_path(
        os.getenv('CHAT_IMAGE_FOLDER'),
        os.path.join(BASE_DIR, 'chat_images')
    )
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
    
    # 通义千问 API 配置
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    
    # RAG配置
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 500))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 50))
    TOP_K = int(os.getenv('TOP_K', 3))
    RETRIEVAL_CANDIDATES = int(os.getenv('RETRIEVAL_CANDIDATES', 12))
    MAX_CHUNKS_PER_DOC = int(os.getenv('MAX_CHUNKS_PER_DOC', 2))
    PDF_IMAGE_MAX_PAGES = int(os.getenv('PDF_IMAGE_MAX_PAGES', 8))
    PDF_TEXT_FALLBACK_THRESHOLD = int(os.getenv('PDF_TEXT_FALLBACK_THRESHOLD', 80))
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    TEXT_MODEL = os.getenv('TEXT_MODEL', 'qwen-turbo')
    VL_MODEL = os.getenv('VL_MODEL', 'qwen-vl-plus')
    OCR_MODEL = os.getenv('OCR_MODEL', 'qwen-vl-ocr')
    HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    PORT = int(os.getenv('FLASK_PORT', 5000))
