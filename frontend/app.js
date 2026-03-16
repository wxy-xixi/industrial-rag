const API = 'http://127.0.0.1:5000/api';

// ==================== 文件上传 ====================
const uploadBox = document.getElementById('uploadBox');
const fileInput = document.getElementById('fileInput');

uploadBox.addEventListener('click', () => fileInput.click());

uploadBox.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = '#1890ff';
    uploadBox.style.background = '#e6f7ff';
});

uploadBox.addEventListener('dragleave', () => {
    uploadBox.style.borderColor = '#d9d9d9';
    uploadBox.style.background = '';
});

uploadBox.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = '#d9d9d9';
    uploadBox.style.background = '';
    if (e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        uploadFile(fileInput.files[0]);
    }
});

function uploadFile(file) {
    const allowed = ['pdf', 'docx', 'txt'];
    const ext = file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
        alert('仅支持 PDF、DOCX、TXT 格式');
        return;
    }

    const progress = document.getElementById('uploadProgress');
    const fill = document.getElementById('progressFill');
    const status = document.getElementById('uploadStatus');

    progress.style.display = 'block';
    fill.style.width = '30%';
    status.textContent = '正在上传并解析...';

    const formData = new FormData();
    formData.append('file', file);

    fetch(`${API}/upload`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.code === 200) {
            fill.style.width = '100%';
            status.textContent = `✅ 上传成功！分块数: ${data.data.chunk_count}`;
            loadDocuments();
            setTimeout(() => {
                progress.style.display = 'none';
                fill.style.width = '0%';
            }, 3000);
        } else {
            fill.style.width = '0%';
            status.textContent = `❌ ${data.msg}`;
        }
    })
    .catch(err => {
        fill.style.width = '0%';
        status.textContent = `❌ 上传失败: ${err.message}`;
    });

    fileInput.value = '';
}

// ==================== 文档列表 ====================
function loadDocuments() {
    fetch(`${API}/documents`)
    .then(res => res.json())
    .then(data => {
        const list = document.getElementById('docList');
        if (data.data.length === 0) {
            list.innerHTML = '<p class="empty-tip">暂无文档</p>';
            return;
        }
        list.innerHTML = data.data.map(doc => `
            <div class="doc-item">
                <div class="doc-info">
                    <h4>${doc.filename}</h4>
                    <span>${doc.chunk_count}个分块 · ${formatSize(doc.file_size)} · ${doc.status === 'completed' ? '✅' : '⏳'}</span>
                </div>
                <button class="doc-delete" onclick="deleteDoc(${doc.id})" title="删除">×</button>
            </div>
        `).join('');
    });
}

function deleteDoc(id) {
    if (!confirm('确定删除此文档？')) return;
    fetch(`${API}/documents/${id}`, { method: 'DELETE' })
    .then(res => res.json())
    .then(() => loadDocuments());
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ==================== 智能问答 ====================
const chatMessages = document.getElementById('chatMessages');
const questionInput = document.getElementById('questionInput');
const sendBtn = document.getElementById('sendBtn');

// 回车发送
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQuestion();
    }
});

// 自动调整高度
questionInput.addEventListener('input', () => {
    questionInput.style.height = 'auto';
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + 'px';
});

function sendQuestion() {
    const question = questionInput.value.trim();
    if (!question) return;

    // 清除欢迎消息
    const welcome = chatMessages.querySelector('.welcome-msg');
    if (welcome) welcome.remove();

    // 显示用户消息
    appendMessage('user', question);
    questionInput.value = '';
    questionInput.style.height = 'auto';

    // 显示加载
    const loadingId = 'loading-' + Date.now();
    appendLoading(loadingId);

    sendBtn.disabled = true;

    fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
    })
    .then(res => res.json())
    .then(data => {
        removeLoading(loadingId);
        if (data.code === 200) {
            appendMessage('bot', data.data.answer, data.data.sources);
        } else {
            appendMessage('bot', `❌ ${data.msg}`);
        }
    })
    .catch(err => {
        removeLoading(loadingId);
        appendMessage('bot', `❌ 请求失败: ${err.message}`);
    })
    .finally(() => {
        sendBtn.disabled = false;
        questionInput.focus();
    });
}

function appendMessage(role, content, sources) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `
            <div class="sources">
                <details>
                    <summary>📎 参考来源 (${sources.length})</summary>
                    ${sources.map(s => `
                        <div class="source-item">
                            <strong>${s.filename}</strong> (相似度: ${s.score})<br>
                            ${s.content}
                        </div>
                    `).join('')}
                </details>
            </div>
        `;
    }

    div.innerHTML = `
        <div class="avatar">${role === 'user' ? '👤' : '🤖'}</div>
        <div class="bubble">
            ${content.replace(/\n/g, '<br>')}
            ${sourcesHtml}
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendLoading(id) {
    const div = document.createElement('div');
    div.className = 'message bot';
    div.id = id;
    div.innerHTML = `
        <div class="avatar">🤖</div>
        <div class="bubble">
            <div class="loading-dots">
                <span>·</span><span>·</span><span>·</span> 思考中
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ==================== 初始化 ====================
loadDocuments();