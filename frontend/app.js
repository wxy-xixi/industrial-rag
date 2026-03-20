const API = `${window.location.origin}/api`;
const DOC_CATEGORIES = ['未分类', '工艺规范', '设备操作', '热处理', '质量检测', '安全规程', '维修维护'];

// ==================== 文件上传 ====================
const uploadBox = document.getElementById('uploadBox');
const fileInput = document.getElementById('fileInput');
const categorySelect = document.getElementById('categorySelect');
const docFilter = document.getElementById('docFilter');
const docSearch = document.getElementById('docSearch');
const queryDocSelect = document.getElementById('queryDocSelect');
const queryScopeIndicator = document.getElementById('queryScopeIndicator');
let currentDocuments = [];

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
    formData.append('category', categorySelect.value);

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

docFilter.addEventListener('change', () => {
    renderDocuments(currentDocuments);
});

docSearch.addEventListener('input', () => {
    renderDocuments(currentDocuments);
});

queryDocSelect.addEventListener('change', () => {
    updateQueryScopeIndicator();
});

// ==================== 文档列表 ====================
function loadDocuments() {
    fetch(`${API}/documents`)
    .then(res => res.json())
    .then(data => {
        const docs = data.data || [];
        currentDocuments = docs;
        updateQueryDocOptions(docs);
        updateStats(docs);
        renderDocuments(docs);
    });
}

function updateQueryDocOptions(docs) {
    const previousValue = queryDocSelect.value;
    queryDocSelect.replaceChildren();

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = '全知识库';
    queryDocSelect.appendChild(defaultOption);

    docs.forEach((doc) => {
        const option = document.createElement('option');
        option.value = String(doc.id);
        option.textContent = `${doc.filename} · ${doc.file_type.toUpperCase()}`;
        queryDocSelect.appendChild(option);
    });

    if (docs.some((doc) => String(doc.id) === previousValue)) {
        queryDocSelect.value = previousValue;
    }

    updateQueryScopeIndicator();
}

function updateQueryScopeIndicator() {
    const selectedDocId = queryDocSelect.value;
    if (!selectedDocId) {
        queryScopeIndicator.hidden = true;
        queryScopeIndicator.textContent = '';
        return;
    }

    const selectedDoc = currentDocuments.find((doc) => String(doc.id) === selectedDocId);
    if (!selectedDoc) {
        queryScopeIndicator.hidden = true;
        queryScopeIndicator.textContent = '';
        return;
    }

    queryScopeIndicator.hidden = false;
    queryScopeIndicator.textContent = `当前仅检索：${selectedDoc.filename}`;
}

function renderDocuments(docs) {
    const list = document.getElementById('docList');
    const filterValue = docFilter.value;
    const searchValue = docSearch.value.trim().toLowerCase();
    const visibleDocs = docs.filter((doc) => {
        const category = doc.category || '未分类';
        const matchCategory = filterValue === '全部' || category === filterValue;
        const matchSearch = searchValue === ''
            || doc.filename.toLowerCase().includes(searchValue)
            || category.toLowerCase().includes(searchValue)
            || (doc.file_type || '').toLowerCase().includes(searchValue);
        return matchCategory && matchSearch;
    });

    list.replaceChildren();

    if (visibleDocs.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'empty-tip';
        empty.textContent = docs.length === 0 ? '暂无文档' : '当前筛选条件下暂无文档';
        list.appendChild(empty);
        return;
    }

    const groupedDocs = visibleDocs.reduce((groups, doc) => {
        const category = doc.category || '未分类';
        if (!groups[category]) {
            groups[category] = [];
        }
        groups[category].push(doc);
        return groups;
    }, {});

    Object.entries(groupedDocs).forEach(([category, items]) => {
        const group = document.createElement('div');
        group.className = 'doc-group';

        const groupHeader = document.createElement('div');
        groupHeader.className = 'doc-group-header';

        const groupTitle = document.createElement('span');
        groupTitle.className = `doc-group-title category-${slugifyCategory(category)}`;
        groupTitle.textContent = category;

        const groupCount = document.createElement('span');
        groupCount.className = 'doc-group-count';
        groupCount.textContent = `${items.length} 份文档`;

        groupHeader.appendChild(groupTitle);
        groupHeader.appendChild(groupCount);
        group.appendChild(groupHeader);

        items.forEach((doc) => {
            const item = document.createElement('div');
            item.className = 'doc-item';

            const info = document.createElement('div');
            info.className = 'doc-info';
            const topRow = document.createElement('div');
            topRow.className = 'doc-top-row';

            const typeTag = document.createElement('span');
            typeTag.className = `doc-type type-${doc.file_type}`;
            typeTag.textContent = (doc.file_type || 'unknown').toUpperCase();

            const categoryTag = document.createElement('select');
            categoryTag.className = `doc-category-tag category-${slugifyCategory(doc.category || '未分类')}`;
            buildCategoryOptions(categoryTag, doc.category || '未分类');
            categoryTag.addEventListener('change', (event) => {
                updateDocumentCategory(doc.id, event.target.value);
            });

            const title = document.createElement('h4');
            title.textContent = doc.filename;

            const meta = document.createElement('span');
            meta.textContent = `${doc.chunk_count}个分块 · ${formatSize(doc.file_size)} · ${doc.status === 'completed' ? '✅ 已完成' : '⏳ 处理中'}`;

            const button = document.createElement('button');
            button.className = 'doc-delete';
            button.title = '删除';
            button.textContent = '×';
            button.addEventListener('click', () => deleteDoc(doc.id));

            topRow.appendChild(typeTag);
            topRow.appendChild(categoryTag);
            info.appendChild(topRow);
            info.appendChild(title);
            info.appendChild(meta);
            item.appendChild(info);
            item.appendChild(button);
            group.appendChild(item);
        });

        list.appendChild(group);
    });
}

function buildCategoryOptions(selectEl, currentValue) {
    selectEl.replaceChildren();
    DOC_CATEGORIES.forEach((category) => {
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        option.selected = category === currentValue;
        selectEl.appendChild(option);
    });
}

function slugifyCategory(category) {
    const mapping = {
        '未分类': 'uncategorized',
        '工艺规范': 'process',
        '设备操作': 'operation',
        '热处理': 'heat',
        '质量检测': 'quality',
        '安全规程': 'safety',
        '维修维护': 'maintenance'
    };
    return mapping[category] || 'uncategorized';
}

function updateDocumentCategory(id, category) {
    fetch(`${API}/documents/${id}/category`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category })
    })
    .then(res => res.json())
    .then((data) => {
        if (data.code === 200) {
            loadDocuments();
        } else {
            alert(data.msg || '分类更新失败');
        }
    })
    .catch((err) => {
        alert(`分类更新失败: ${err.message}`);
        loadDocuments();
    });
}

function updateStats(docs) {
    const docCount = document.getElementById('docCount');
    const chunkCount = document.getElementById('chunkCount');
    const imageCount = document.getElementById('imageCount');
    const categorySummary = document.getElementById('categorySummary');

    const totalChunks = docs.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
    const totalImages = docs.filter((doc) => ['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(doc.file_type)).length;
    const categoryCounts = docs.reduce((acc, doc) => {
        const category = doc.category || '未分类';
        acc[category] = (acc[category] || 0) + 1;
        return acc;
    }, {});

    animateStatValue(docCount, docs.length);
    animateStatValue(chunkCount, totalChunks);
    animateStatValue(imageCount, totalImages);

    categorySummary.replaceChildren();
    Object.entries(categoryCounts).forEach(([category, count]) => {
        const badge = document.createElement('span');
        badge.className = `category-mini-badge category-${slugifyCategory(category)}`;
        badge.textContent = `${category} ${count}`;
        categorySummary.appendChild(badge);
    });
}

function animateStatValue(element, nextValue) {
    const currentValue = Number(element.dataset.value || '0');
    if (currentValue === nextValue) {
        element.textContent = nextValue;
        return;
    }

    const duration = 420;
    const start = performance.now();
    element.dataset.value = String(nextValue);
    element.classList.add('updating');

    function frame(now) {
        const progress = Math.min((now - start) / duration, 1);
        const value = Math.round(currentValue + (nextValue - currentValue) * progress);
        element.textContent = value;
        if (progress < 1) {
            requestAnimationFrame(frame);
        } else {
            element.textContent = nextValue;
            window.setTimeout(() => element.classList.remove('updating'), 120);
        }
    }

    requestAnimationFrame(frame);
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
const historyModal = document.getElementById('historyModal');
const historyModalBackdrop = document.getElementById('historyModalBackdrop');
const historyModalClose = document.getElementById('historyModalClose');
const historyModalTime = document.getElementById('historyModalTime');
const historyModalQuestion = document.getElementById('historyModalQuestion');
const historyModalAnswer = document.getElementById('historyModalAnswer');

attachBtn.addEventListener('click', () => chatImageInput.click());
chatImageInput.addEventListener('change', () => {
    if (chatImageInput.files.length > 0) {
        attachName.textContent = `已附加: ${chatImageInput.files[0].name}`;
    } else {
        attachName.textContent = '未选择图片';
    }
});

historyModalClose.addEventListener('click', closeHistoryModal);
historyModalBackdrop.addEventListener('click', closeHistoryModal);
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !historyModal.hidden) {
        closeHistoryModal();
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
    const selectedDocId = queryDocSelect.value;
    if (attachedImage) {
        const formData = new FormData();
        formData.append('question', question);
        if (selectedDocId) {
            formData.append('doc_id', selectedDocId);
        }
        formData.append('image', attachedImage);
        options.body = formData;
    } else {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify({
            question,
            doc_id: selectedDocId || null
        });
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
    contentBlock.textContent = normalizeMessageContent(content);
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

function normalizeMessageContent(content) {
    return String(content || '')
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
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

function openHistoryModal(record) {
    historyModalTime.textContent = record.create_time || '';
    historyModalQuestion.textContent = record.question || '';
    historyModalAnswer.textContent = record.answer || '';
    historyModal.hidden = false;
    document.body.classList.add('modal-open');
}

function closeHistoryModal() {
    historyModal.hidden = true;
    document.body.classList.remove('modal-open');
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
            item.tabIndex = 0;
            item.setAttribute('role', 'button');
            item.setAttribute('aria-label', `查看历史问答：${record.question}`);
            item.addEventListener('click', () => openHistoryModal(record));
            item.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openHistoryModal(record);
                }
            });

            const question = document.createElement('div');
            question.className = 'history-question';
            question.textContent = record.question;

            const answer = document.createElement('div');
            answer.className = 'history-answer';
            answer.textContent = record.answer;

            const time = document.createElement('div');
            time.className = 'history-time';
            time.textContent = record.create_time;

            const action = document.createElement('div');
            action.className = 'history-action';
            action.textContent = '点击查看完整回答';

            item.appendChild(question);
            item.appendChild(answer);
            item.appendChild(time);
            item.appendChild(action);
            list.appendChild(item);
        });
    });
}

// ==================== 初始化 ====================
loadDocuments();
loadHistory();
