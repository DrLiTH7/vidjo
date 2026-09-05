const DEFAULT_SETTINGS = {
    backendUrl: "http://127.0.0.1:8000"
};

async function loadSettings() {
    const stored = await browser.storage.local.get("settings");
    return { ...DEFAULT_SETTINGS, ...(stored.settings || {}) };
}

function getStatusBadge(data) {
    if (data.status === "starting") return `<span class="status-badge starting">Iniciando</span>`;
    if (data.status === "done") return `<span class="status-badge done">Concluído</span>`;
    if (data.status === "error") return `<span class="status-badge error">Erro</span>`;
    
    if (data.step === "downloading") return `<span class="status-badge downloading">Baixando</span>`;
    if (data.step === "merging") return `<span class="status-badge merging">Mesclando</span>`;
    
    return `<span class="status-badge">Processando</span>`;
}

function getProgressInfo(data) {
    let pct = 0;
    let label = "Aguardando...";
    let fillClass = "";

    if (data.status === "done") {
        pct = 100;
        label = "Download finalizado!";
        fillClass = "done";
    } else if (data.status === "error") {
        pct = 100;
        label = "Falha no download";
        fillClass = "error";
    } else if (data.step === "downloading") {
        if (data.total > 0) pct = Math.round((data.completed / data.total) * 100);
        label = `Segmentos: ${data.completed || 0} / ${data.total || "?"}`;
    } else if (data.step === "merging") {
        if (data.total > 0) pct = Math.round((data.completed / data.total) * 100);
        label = "Mesclando arquivo final...";
        fillClass = "merging";
    } else if (data.status === "starting") {
        label = "Preparando...";
    }

    return { pct, label, fillClass };
}

function renderCards(tasks) {
    const grid = document.getElementById("grid");
    const entries = Object.entries(tasks);
    
    if (entries.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
                <h3>Nenhum download encontrado</h3>
                <p>Os downloads iniciados recentemente aparecerão aqui.</p>
            </div>
        `;
        return;
    }

    // Sort: active first, then done/error
    entries.sort((a, b) => {
        const aActive = a[1].status !== "done" && a[1].status !== "error";
        const bActive = b[1].status !== "done" && b[1].status !== "error";
        if (aActive && !bActive) return -1;
        if (!aActive && bActive) return 1;
        return 0;
    });

    let html = "";
    for (const [taskId, data] of entries) {
        const shortId = taskId.split("-")[0];
        const progress = getProgressInfo(data);
        const urlName = data.title || (data.url ? (new URL(data.url).pathname.split('/').pop() || data.url) : "Link Desconhecido");
        
        let errorHtml = "";
        let actionBtnHtml = "";
        let deleteBtnHtml = `<button class="delete-btn" data-taskid="${taskId}" style="flex:1; padding:6px; background:#4b5563; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;" title="Remover da lista">🗑️ Excluir</button>`;
        
        if (data.status === "error" && data.error) {
            errorHtml = `<div class="error-text">Erro: ${data.error}</div>`;
            let retryBtnHtml = `<button class="retry-btn" data-url="${data.url || ''}" data-title="${data.title || ''}" data-taskid="${taskId}" style="flex:1; padding:6px; background:#2563eb; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;">🔄 Tentar Novamente</button>`;
            actionBtnHtml = `<div style="display:flex; gap:8px; margin-top:8px; width:100%;">${retryBtnHtml}${deleteBtnHtml}</div>`;
        } else if (data.status === "done") {
            let openBtnHtml = `<button class="open-folder-btn" data-taskid="${taskId}" style="flex:1; padding:6px; background:#4f46e5; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;">📁 Abrir Pasta</button>`;
            actionBtnHtml = `<div style="display:flex; gap:8px; margin-top:8px; width:100%;">${openBtnHtml}${deleteBtnHtml}</div>`;
        } else {
            actionBtnHtml = `<button class="cancel-btn" data-taskid="${taskId}" style="margin-top:8px; width:100%; padding:6px; background:#dc2626; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;">⏹ Cancelar</button>`;
        }

        html += `
            <div class="card">
                <div class="card-header">
                    <span class="task-id">ID: ${shortId}</span>
                    ${getStatusBadge(data)}
                </div>
                <div class="url" title="${data.url}">${urlName}</div>
                <div class="progress-container">
                    <div class="progress-header">
                        <span>${progress.label}</span>
                        <span>${progress.pct}%</span>
                    </div>
                    <div class="progress-track">
                        <div class="progress-fill ${progress.fillClass}" style="width: ${progress.pct}%"></div>
                    </div>
                </div>
                ${errorHtml}
                ${actionBtnHtml}
            </div>
        `;
    }
    grid.innerHTML = html;

    document.querySelectorAll('.retry-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const btnEl = e.currentTarget;
            btnEl.disabled = true;
            btnEl.innerText = "⏳ Iniciando...";
            const url = btnEl.getAttribute('data-url');
            const title = btnEl.getAttribute('data-title');
            const taskId = btnEl.getAttribute('data-taskid');
            
            const settings = await loadSettings();
            try {
                let headers = {};
                if (tasks[taskId] && tasks[taskId].headers) {
                    headers = tasks[taskId].headers;
                }
                
                const payload = {
                    url: url,
                    title: title,
                    headers: headers,
                    preferred_quality: settings.preferredQuality
                };
                if (settings.savePath) payload.save_path = settings.savePath;
                if (settings.threads !== 0) payload.threads = settings.threads;
                if (settings.maxConcurrent !== DEFAULT_SETTINGS.maxConcurrent) payload.max_concurrent = settings.maxConcurrent;
                
                const response = await fetch(`${settings.backendUrl}/download`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                
                if (!response.ok) {
                    btnEl.innerText = "❌ Falhou";
                    btnEl.disabled = false;
                }
            } catch (err) {
                btnEl.innerText = "❌ Erro";
                btnEl.disabled = false;
            }
        });
    });

    document.querySelectorAll('.cancel-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const btnEl = e.currentTarget;
            btnEl.disabled = true;
            btnEl.innerText = "⏳ Cancelando...";
            const taskId = btnEl.getAttribute('data-taskid');
            
            const settings = await loadSettings();
            try {
                await fetch(`${settings.backendUrl}/cancel`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: taskId })
                });
            } catch (err) {
                console.error("Cancel failed:", err);
                btnEl.innerText = "❌ Erro";
                btnEl.disabled = false;
            }
        });
    });

    document.querySelectorAll('.open-folder-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const btnEl = e.currentTarget;
            const taskId = btnEl.getAttribute('data-taskid');
            const settings = await loadSettings();
            try {
                await fetch(`${settings.backendUrl}/open_folder`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: taskId })
                });
            } catch (err) {
                console.error("Open folder failed:", err);
            }
        });
    });

    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const btnEl = e.currentTarget;
            btnEl.disabled = true;
            btnEl.innerText = "⏳";
            const taskId = btnEl.getAttribute('data-taskid');
            const settings = await loadSettings();
            try {
                await fetch(`${settings.backendUrl}/delete`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: taskId })
                });
                delete tasks[taskId];
                renderCards(tasks);
            } catch (err) {
                console.error("Delete failed:", err);
                btnEl.innerText = "❌";
                btnEl.disabled = false;
            }
        });
    });
}

async function init() {
    const settings = await loadSettings();
    let tasksState = {};

    const eventSource = new EventSource(`${settings.backendUrl}/stream`);
    
    eventSource.onmessage = (e) => {
        try {
            const result = JSON.parse(e.data);
            
            if (result.tasks) {
                // Initial state
                tasksState = result.tasks;
            } else if (result.task_id) {
                // Single update
                tasksState[result.task_id] = result.data;
            }
            
            renderCards(tasksState);
        } catch (err) {
            console.error("SSE parse error:", err);
        }
    };
    
    eventSource.onerror = (e) => {
        console.error("SSE connection error:", e);
    };
}

document.addEventListener("DOMContentLoaded", init);
