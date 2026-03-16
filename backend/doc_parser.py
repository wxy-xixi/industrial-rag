import os
import PyPDF2
import docx

def parse_file(filepath):
    """根据文件类型解析文档，返回纯文本"""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        return parse_pdf(filepath)
    elif ext == '.docx':
        return parse_docx(filepath)
    elif ext == '.txt':
        return parse_txt(filepath)
    else:
        raise ValueError(f'不支持的文件格式: {ext}')

def parse_pdf(filepath):
    """解析PDF文件"""
    text = ''
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + '\n'
    return text.strip()

def parse_docx(filepath):
    """解析Word文件"""
    doc = docx.Document(filepath)
    text = ''
    for para in doc.paragraphs:
        if para.text.strip():
            text += para.text + '\n'
    return text.strip()

def parse_txt(filepath):
    """解析文本文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()

def split_text(text, chunk_size=500, overlap=50):
    """将文本分块"""
    if not text:
        return []
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    
    return chunks