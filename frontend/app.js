const API = `${window.location.origin}/api`;

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
    const allowed = ['pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'bmp', 'webp'];
    const ext = file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
        alert('仅支持 PDF、DOCX、TXT、PNG、JPG、JPEG、BMP、WEBP 格式');
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
        const docs = data.data || [];
        updateStats(docs);
        list.replaceChildren();
        if (docs.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-tip';
            empty.textContent = '暂无文档';
            list.appendChild(empty);
            return;
        }
        docs.forEach((doc) => {
            const item = document.createElement('div');
            item.className = 'doc-item';

            const info = document.createElement('div');
            info.className = 'doc-info';

            const typeTag = document.createElement('span');
            typeTag.className = `doc-type type-${doc.file_type}`;
            typeTag.textContent = (doc.file_type || 'unknown').toUpperCase();

            const title = document.createElement('h4');
            title.textContent = doc.filename;

            const meta = document.createElement('span');
            meta.textContent = `${doc.chunk_count}个分块 · ${formatSize(doc.file_size)} · ${doc.status === 'completed' ? '✅ 已完成' : '⏳ 处理中'}`;

            const button = document.createElement('button');
            button.className = 'doc-delete';
            button.title = '删除';
            button.textContent = '×';
            button.addEventListener('click', () => deleteDoc(doc.id));

            info.appendChild(typeTag);
            info.appendChild(title);
            info.appendChild(meta);
            item.appendChild(info);
            item.appendChild(button);
            list.appendChild(item);
        });
    });
}

function updateStats(docs) {
    const docCount = document.getElementById('docCount');
    const chunkCount = document.getElementById('chunkCount');
    const imageCount = document.getElementById('imageCount');

    const totalChunks = docs.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
    const totalImages = docs.filter((doc) => ['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(doc.file_type)).length;

    docCount.textContent = docs.length;
    chunkCount.textContent = totalChunks;
    imageCount.textContent = totalImages;
}

function deleteDoc(id) {
    if (!confirm('确定删除此文档？')) return;
    fetch(`${API}/documents/${id}`, { method: 'DELETE' })
    .then(res => res.json())
    .then(() => {
        loadDocuments();
        loadHistory();
    });
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
const chatImageInput = document.getElementById('chatImageInput');
const attachBtn = document.getElementById('attachBtn');
const attachName = document.getElementById('attachName');

attachBtn.addEventListener('click', () => chatImageInput.click());
chatImageInput.addEventListener('change', () => {
    if (chatImageInput.files.length > 0) {
        attachName.textContent = `已附加: ${chatImageInput.files[0].name}`;
    } else {
        attachName.textContent = '未选择图片';
    }
});

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
    const attachedImage = chatImageInput.files[0];
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

    const options = { method: 'POST' };
    if (attachedImage) {
        const formData = new FormData();
        formData.append('question', question);
        formData.append('image', attachedImage);
        options.body = formData;
    } else {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify({ question });
    }

    fetch(`${API}/chat`, options)
    .then(res => res.json())
    .then(data => {
        removeLoading(loadingId);
        if (data.code === 200) {
            appendMessage('bot', data.data.answer, data.data.sources);
            loadHistory();
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
        chatImageInput.value = '';
        attachName.textContent = '未选择图片';
        questionInput.focus();
    });
}

function appendMessage(role, content, sources) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const contentBlock = document.createElement('div');
    contentBlock.className = 'message-content';
    contentBlock.textContent = content;
    bubble.appendChild(contentBlock);

    if (sources && sources.length > 0) {
        const wrapper = document.createElement('div');
        wrapper.className = 'sources';

        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `📎 参考来源 (${sources.length})`;

        details.appendChild(summary);

        sources.forEach((source) => {
            const item = document.createElement('div');
            item.className = 'source-item';

            const title = document.createElement('strong');
            title.textContent = source.filename;

            const meta = document.createTextNode(` (相似度: ${source.score})`);
            const excerpt = document.createElement('div');
            excerpt.textContent = source.content;

            item.appendChild(title);
            item.appendChild(meta);
            item.appendChild(document.createElement('br'));
            item.appendChild(excerpt);
            details.appendChild(item);
        });

        wrapper.appendChild(details);
        bubble.appendChild(wrapper);
    }

    div.appendChild(avatar);
    div.appendChild(bubble);
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

function loadHistory() {
    fetch(`${API}/history`)
    .then(res => res.json())
    .then(data => {
        const list = document.getElementById('historyList');
        const records = data.data || [];
        list.replaceChildren();

        if (records.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'empty-tip';
            empty.textContent = '暂无历史记录';
            list.appendChild(empty);
            return;
        }

        records.slice(0, 8).forEach((record) => {
            const item = document.createElement('div');
            item.className = 'history-item';

            const question = document.createElement('div');
            question.className = 'history-question';
            question.textContent = record.question;

            const answer = document.createElement('div');
            answer.className = 'history-answer';
            answer.textContent = record.answer;

            const time = document.createElement('div');
            time.className = 'history-time';
            time.textContent = record.create_time;

            item.appendChild(question);
            item.appendChild(answer);
            item.appendChild(time);
            list.appendChild(item);
        });
    });
}

// ==================== 初始化 ====================
loadDocuments();
loadHistory();
