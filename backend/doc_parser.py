import os
import PyPDF2
import docx
import fitz

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

def render_pdf_pages(filepath, output_dir, max_pages=5):
    """将 PDF 页面渲染为图片，供扫描版 PDF 的视觉解析兜底使用。"""
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    max_dimension = 1600

    with fitz.open(filepath) as pdf:
        total_pages = min(len(pdf), max_pages)
        for page_index in range(total_pages):
            page = pdf.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            if max(pixmap.width, pixmap.height) > max_dimension:
                scale = max_dimension / max(pixmap.width, pixmap.height)
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(2 * scale, 2 * scale),
                    alpha=False
                )
            output_path = os.path.join(output_dir, f'page_{page_index + 1}.jpg')
            pixmap.save(output_path)
            image_paths.append(output_path)

    return image_paths

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
