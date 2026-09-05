const DEFAULT_SETTINGS = {
    backendUrl: "http://127.0.0.1:8000",
    savePath: "",
    threads: 0,
    maxConcurrent: 20,
    preferredQuality: "highest",
    domainBlacklist: ""
};

async function loadSettings() {
    const stored = await browser.storage.local.get("settings");
    return { ...DEFAULT_SETTINGS, ...(stored.settings || {}) };
}

async function saveSettings(settings) {
    await browser.storage.local.set({ settings });
}

let eventSource = null;

async function checkActiveTask(backendUrl, tabId) {
    const stored = await browser.storage.local.get("activeTasks");
    const activeTasks = stored.activeTasks || {};
    const taskId = activeTasks[tabId];
    if (!taskId) return null;
    
    try {
        const response = await fetch(`${backendUrl}/status?task_id=${taskId}`);
        if (response.ok) {
            const result = await response.json();
            if (result.data) return { taskId: taskId, data: result.data };
        }
    } catch (e) {
        // Backend might be offline
    }
    return null;
}

function startPolling(taskId, backendUrl) {
    if (eventSource) eventSource.close();
    
    const container = document.getElementById("progressContainer");
    const label = document.getElementById("progressLabel");
    const percent = document.getElementById("progressPercent");
    const fill = document.getElementById("progressFill");
    const statusMsg = document.getElementById("statusMsg");
    const btn = document.getElementById("sendBtn");
    const cancelBtn = document.getElementById("cancelBtn");
    
    if (container) container.style.display = "block";
    
    if (cancelBtn) {
        cancelBtn.style.display = "block";
        cancelBtn.onclick = async () => {
            cancelBtn.disabled = true;
            cancelBtn.innerText = "⏳ Cancelando...";
            try {
                await fetch(`${backendUrl}/cancel`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: taskId })
                });
            } catch (err) {
                console.error("Cancel error:", err);
                cancelBtn.disabled = false;
                cancelBtn.innerText = "⏹ Cancelar";
            }
        };
    }

    eventSource = new EventSource(`${backendUrl}/stream`);
    
    eventSource.onmessage = async (e) => {
        try {
            const result = JSON.parse(e.data);
            
            let data = null;
            if (result.tasks) {
                data = result.tasks[taskId];
            } else if (result.task_id === taskId) {
                data = result.data;
            }
            
            if (data) {
                if (data.status === "starting") {
                    label.innerText = "Iniciando...";
                    percent.innerText = "0%";
                    fill.style.width = "0%";
                } else if (data.status === "done") {
                    label.innerText = "Concluído!";
                    percent.innerText = "100%";
                    fill.style.width = "100%";
                    statusMsg.innerText = "✅ Download finalizado com sucesso!";
                    statusMsg.style.color = "#16a34a";
                    btn.disabled = false;
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Enviar para o Downblob`;
                    if (cancelBtn) cancelBtn.style.display = "none";
                    
                    const btnRow = document.createElement("div");
                    btnRow.className = "btn-row";
                    btnRow.innerHTML = `
                        <button id="openFolderBtn" class="btn btn-neutral" style="margin-top: 6px;">
                            📁 Abrir Pasta
                        </button>
                    `;
                    if (!document.getElementById("openFolderBtn")) {
                        container.appendChild(btnRow);
                        document.getElementById("openFolderBtn").onclick = async () => {
                            try {
                                await fetch(`${backendUrl}/open_folder`, {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify({ task_id: taskId })
                                });
                            } catch (e) {
                                console.error(e);
                            }
                        };
                    }
                    
                    eventSource.close();
                    
                    const stored = await browser.storage.local.get("activeTasks");
                    const activeTasks = stored.activeTasks || {};
                    delete activeTasks[taskId];
                    await browser.storage.local.set({ activeTasks });
                    
                    setTimeout(() => { if (container) container.style.display = "none"; }, 3000);
                } else if (data.status === "error") {
                    label.innerText = "Erro";
                    let errText = data.error || "Falha no download";
                    if (errText.includes("yt-dlp error") || errText.includes("HTTP Error 403")) errText = "O site bloqueou o download ou o vídeo é protegido.";
                    else if (errText.includes("yt-dlp exited")) errText = "Não foi possível baixar o vídeo (formato não suportado).";
                    else if (errText.includes("ffmpeg NOT found")) errText = "FFmpeg não está instalado ou configurado no sistema.";
                    else if (errText.includes("yt-dlp NOT found")) errText = "yt-dlp não está instalado ou configurado no sistema.";
                    statusMsg.innerText = "❌ " + errText;
                    statusMsg.style.color = "#dc2626";
                    btn.disabled = false;
                    btn.innerText = "Tentar Novamente";
                    if (cancelBtn) cancelBtn.style.display = "none";
                    
                    eventSource.close();
                    
                    const stored = await browser.storage.local.get("activeTasks");
                    const activeTasks = stored.activeTasks || {};
                    delete activeTasks[taskId];
                    await browser.storage.local.set({ activeTasks });
                } else if (data.step) {
                    let pct = 0;
                    if (data.total > 0) {
                        pct = Math.round((data.completed / data.total) * 100);
                    }
                    
                    if (data.step === "downloading") {
                        label.innerText = `Baixando segmentos... (${data.completed}/${data.total})`;
                    } else if (data.step === "merging") {
                        label.innerText = `Mesclando vídeo...`;
                    }
                    
                    percent.innerText = `${pct}%`;
                    fill.style.width = `${pct}%`;
                }
            }
        } catch (err) {
            console.error("SSE parsing error:", err);
        }
    };

    eventSource.onerror = (e) => {
        console.error("SSE error:", e);
    };
}

function generateCode(data) {
    const importantHeaders = ['user-agent', 'cookie', 'referer', 'origin', 'authorization'];
    let headersPy = '';
    for (const [key, value] of Object.entries(data.headers || {})) {
        if (importantHeaders.includes(key)) {
            const safeValue = value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
            headersPy += `    "${key}": "${safeValue}",\n`;
        }
    }
    return `BlobUrls = [
    (
        "${data.url}",
        "video.mp4",
    ),
]

HeaderConfig = {
${headersPy}}
`;
}

function selectBestStream(videos) {
    // Prefer master playlists — backend resolves them to the best quality
    const masterIdx = videos.findLastIndex(v => /master\.m3u8/i.test(v.url));
    if (masterIdx !== -1) return masterIdx;

    // Otherwise pick by resolution hint in the URL
    const qualityOrder = ['2160p', '2160', '4k', '1080p', '1080', '720p', '720', '480p', '480', '360p', '360', '240p', '240'];
    for (const q of qualityOrder) {
        const idx = videos.findLastIndex(v => v.url.toLowerCase().includes(q));
        if (idx !== -1) return idx;
    }

    // Fall back to last detected
    return videos.length - 1;
}

function renderVideos(videos, container, tab) {
    const bestIdx = selectBestStream(videos);
    const options = videos.map((v, i) => {
        let label;
        try { label = new URL(v.url).pathname.split('/').pop() || `Stream ${i + 1}`; }
        catch (_) { label = `Stream ${i + 1}`; }
        const selected = (i === bestIdx) ? "selected" : "";
        return `<option value="${i}" ${selected}>${label}</option>`;
    }).join('');

    const selectorHtml = videos.length > 1
        ? `<div style="display:flex; gap:8px; margin-bottom:8px;">
               <select id="videoSelect" style="flex:1;">${options}</select>
               <button id="nextStreamBtn" class="btn btn-secondary" style="padding:0 12px; height: 32px;" title="Próximo Stream">⏭ Próximo</button>
           </div>
           <button id="downloadAllBtn" class="btn btn-orange" style="width:100%; margin-bottom:8px; justify-content:center;">
               📦 Baixar Todos os ${videos.length} Streams
           </button>`
        : '';

    container.innerHTML = `
        <div class="video-card">
            <div class="video-card-header">
                <span class="video-badge">
                    <span class="video-badge-dot"></span>
                    ${videos.length === 1 ? '1 stream' : `${videos.length} streams`}
                </span>
                ${videos.length > 1 ? '<span class="stream-count">Selecione o stream</span>' : ''}
            </div>
            <div class="action-area">
                ${selectorHtml}
                <button id="sendBtn" class="btn btn-primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                    Enviar para o Downblob
                </button>
                <div class="btn-row">
                    <button id="copyUrlBtn" class="btn btn-secondary">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                        Copiar Link
                    </button>
                    <a id="dragLink" draggable="true" class="btn btn-orange">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>
                        Arrastar Link
                    </a>
                </div>
            </div>
            <div id="progressContainer" class="progress-container">
                <div class="progress-header">
                    <span id="progressLabel">Preparando...</span>
                    <span id="progressPercent">0%</span>
                </div>
                <div class="progress-track">
                    <div id="progressFill" class="progress-fill"></div>
                </div>
                <button id="cancelBtn" class="cancel-btn" style="display:none; margin-top:8px; width:100%; padding:6px; background:#dc2626; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;">⏹ Cancelar</button>
            </div>
        </div>
        </div>
        <div style="text-align: center; margin-top: 10px;">
            <a href="#" id="toggleCodeBtn" style="font-size: 11px; color: #6b7280; text-decoration: underline;">Mais detalhes (Uso Manual)</a>
        </div>
        <div id="codeSection" class="code-section" style="display:none;">
            <p class="code-label">Código para uso manual</p>
            <textarea id="pyOutput" readonly></textarea>
            <button id="copyBtn" class="btn btn-neutral" style="margin-top:6px">Copiar Código Python</button>
        </div>
        <p id="statusMsg"></p>
    `;

    let selected = videos[bestIdx];
    document.getElementById("pyOutput").value = generateCode(selected);
    document.getElementById("dragLink").href = selected.url;

    if (videos.length > 1) {
        const selectElement = document.getElementById("videoSelect");
        selectElement.value = String(bestIdx);
        selectElement.addEventListener("change", (e) => {
            selected = videos[parseInt(e.target.value)];
            document.getElementById("pyOutput").value = generateCode(selected);
            document.getElementById("dragLink").href = selected.url;
        });

        const nextBtn = document.getElementById("nextStreamBtn");
        if (nextBtn) {
            nextBtn.addEventListener("click", () => {
                let nextIdx = parseInt(selectElement.value) + 1;
                if (nextIdx >= selectElement.options.length) nextIdx = 0;
                selectElement.value = String(nextIdx);
                selectElement.dispatchEvent(new Event('change'));
            });
        }

        const downloadAllBtn = document.getElementById("downloadAllBtn");
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener("click", async () => {
                downloadAllBtn.disabled = true;
                downloadAllBtn.innerText = "Enviando todos...";
                const settings = await loadSettings();
                let sentCount = 0;
                
                for (let i = 0; i < videos.length; i++) {
                    const vid = videos[i];
                    const payload = {
                        url: vid.url,
                        headers: vid.headers,
                        preferred_quality: settings.preferredQuality,
                        title: `${tab.title} (Stream ${i + 1})`
                    };
                    if (settings.savePath) payload.save_path = settings.savePath;
                    if (settings.threads !== 0) payload.threads = settings.threads;
                    if (settings.maxConcurrent !== DEFAULT_SETTINGS.maxConcurrent) payload.max_concurrent = settings.maxConcurrent;
                    
                    try {
                        const response = await fetch(`${settings.backendUrl}/download`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload)
                        });
                        if (response.ok) sentCount++;
                    } catch(e) { }
                }
                downloadAllBtn.innerText = `✅ ${sentCount} enviados (aba Downloads)`;
                downloadAllBtn.style.backgroundColor = "#16a34a";
                downloadAllBtn.style.borderColor = "#16a34a";
            });
        }
    }

    document.getElementById("sendBtn").onclick = async () => {
        const btn = document.getElementById("sendBtn");
        const statusMsg = document.getElementById("statusMsg");
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Enviando...`;
        btn.disabled = true;
        statusMsg.innerText = "";

        const settings = await loadSettings();

        try {
            const payload = {
                url: selected.url,
                headers: selected.headers,
                preferred_quality: settings.preferredQuality,
                title: tab.title,
            };
            if (settings.savePath) payload.save_path = settings.savePath;
            if (settings.threads !== 0) payload.threads = settings.threads;
            if (settings.maxConcurrent !== DEFAULT_SETTINGS.maxConcurrent) payload.max_concurrent = settings.maxConcurrent;

            const response = await fetch(`${settings.backendUrl}/download`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const result = await response.json();
                statusMsg.innerText = "✅ Download iniciado!";
                statusMsg.style.color = "#16a34a";
                btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Em andamento...`;
                
                if (result.task_id) {
                    const stored = await browser.storage.local.get("activeTasks");
                    const activeTasks = stored.activeTasks || {};
                    activeTasks[tab.id] = result.task_id;
                    await browser.storage.local.set({ activeTasks });
                    startPolling(result.task_id, settings.backendUrl);
                }
            } else {
                statusMsg.innerText = "❌ O aplicativo de download não aceitou o envio.";
                statusMsg.style.color = "#dc2626";
                btn.innerText = "Tentar Novamente";
                btn.disabled = false;
            }
        } catch (e) {
            btn.innerHTML = originalBtnText;
            btn.disabled = false;
            statusMsg.innerHTML = "❌ Não foi possível se conectar.<br>Tente ligar o servidor primeiro.";
            statusMsg.style.color = "#dc2626";
            btn.innerText = "Tentar Novamente";
            btn.disabled = false;
        }
    };

    document.getElementById("copyBtn").onclick = () => {
        navigator.clipboard.writeText(document.getElementById("pyOutput").value);
        const btn = document.getElementById("copyBtn");
        btn.innerText = "✅ Copiado!";
        btn.style.backgroundColor = "#16a34a";
        setTimeout(() => {
            btn.innerText = "Copiar Código Python";
            btn.style.backgroundColor = "";
        }, 2000);
    };

    document.getElementById("copyUrlBtn").onclick = () => {
        navigator.clipboard.writeText(selected.url);
        const btn = document.getElementById("copyUrlBtn");
        btn.innerText = "✅ Copiado!";
        setTimeout(() => {
            btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg> Copiar Link`;
        }, 2000);
    };
}

async function scanPageDirectly(tab, container) {
    try {
        const results = await browser.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                const found = [];
                document.querySelectorAll("video, source").forEach(el => {
                    const src = el.src || el.getAttribute("src") || "";
                    const cur = el.currentSrc || "";
                    [src, cur].forEach(u => {
                        if (u && !u.startsWith("blob:") && !u.startsWith("data:") &&
                            !found.some(f => f.url === u)) {
                            found.push({ url: u, headers: {} });
                        }
                    });
                });
                return found;
            }
        });
        const found = results[0]?.result || [];
        if (found.length > 0) {
            renderVideos(found, container, tab);
        } else {
            container.innerHTML = `
                <div class="video-card">
                    <div class="video-card-header">
                        <span class="video-badge" style="background:#fff7ed; color:#c2410c;">
                            <span class="video-badge-dot" style="background:#f97316;"></span>
                            yt-dlp
                        </span>
                        <span class="stream-count">Alternativo</span>
                    </div>
                    <div class="action-area" style="padding-top: 8px; font-size: 11px; color:#6b7280; text-align:center;">
                        Tentar baixar o vídeo da página atual
                    </div>
                    <div class="action-area">
                        <button id="sendBtn" class="btn btn-primary" style="background:#f97316;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                            Download
                        </button>
                    </div>
                    <div id="progressContainer" class="progress-container">
                        <div class="progress-header">
                            <span id="progressLabel">Preparando...</span>
                            <span id="progressPercent">0%</span>
                        </div>
                        <div class="progress-track">
                            <div id="progressFill" class="progress-fill"></div>
                        </div>
                        <button id="cancelBtn" class="cancel-btn" style="display:none; margin-top:8px; width:100%; padding:6px; background:#dc2626; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600;">⏹ Cancelar</button>
                    </div>
                </div>
                <p id="statusMsg"></p>
            `;
            
            document.getElementById("sendBtn").onclick = async () => {
                const btn = document.getElementById("sendBtn");
                const statusMsg = document.getElementById("statusMsg");
                btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Enviando...`;
                btn.disabled = true;
                statusMsg.innerText = "";
                
                const settings = await loadSettings();
                
                try {
                    const payload = {
                        url: tab.url,
                        title: tab.title,
                        engine: "ytdlp",
                        preferred_quality: settings.preferredQuality
                    };
                    if (settings.savePath) payload.save_path = settings.savePath;

                    const response = await fetch(`${settings.backendUrl}/download`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });

                    if (response.ok) {
                        const result = await response.json();
                        statusMsg.innerText = "✅ Download iniciado!";
                        statusMsg.style.color = "#16a34a";
                        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Em andamento...`;
                        
                        if (result.task_id) {
                            const stored = await browser.storage.local.get("activeTasks");
                            const activeTasks = stored.activeTasks || {};
                            activeTasks[tab.id] = result.task_id;
                            await browser.storage.local.set({ activeTasks });
                            startPolling(result.task_id, settings.backendUrl);
                        }
                    } else {
                        statusMsg.innerText = "❌ Erro: O servidor local rejeitou o envio.";
                        statusMsg.style.color = "#dc2626";
                        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Download`;
                        btn.disabled = false;
                    }
                } catch (err) {
                    statusMsg.innerHTML = "❌ Erro ao conectar ao Downblob.<br>O <b>main.py</b> está rodando?";
                    statusMsg.style.color = "#dc2626";
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Download`;
                    btn.disabled = false;
                }
            };
        }
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                <p class="empty-title">Erro ao escanear</p>
                <p class="empty-sub">${err.message}</p>
            </div>
        `;
    }
}

function initSettingsPanel() {
    const mainView = document.getElementById("mainView");
    const settingsView = document.getElementById("settingsView");

    document.getElementById("downloadsBtn").onclick = () => {
        browser.tabs.create({ url: browser.runtime.getURL("downloads.html") });
    };

    document.getElementById("gearBtn").onclick = async () => {
        const settings = await loadSettings();
        document.getElementById("cfgBackendUrl").value = settings.backendUrl;
        document.getElementById("cfgSavePath").value = settings.savePath;
        document.getElementById("cfgThreads").value = settings.threads;
        document.getElementById("cfgMaxConcurrent").value = settings.maxConcurrent;
        document.getElementById("cfgQuality").value = settings.preferredQuality;
        document.getElementById("cfgDomainBlacklist").value = settings.domainBlacklist;
        document.getElementById("settingsSavedMsg").innerText = "";
        mainView.style.display = "none";
        settingsView.style.display = "block";
    };

    document.getElementById("backBtn").onclick = () => {
        settingsView.style.display = "none";
        mainView.style.display = "block";
    };

    document.getElementById("saveSettingsBtn").onclick = async () => {
        const settings = {
            backendUrl: document.getElementById("cfgBackendUrl").value.trim() || DEFAULT_SETTINGS.backendUrl,
            savePath: document.getElementById("cfgSavePath").value.trim().replace(/^["']+|["']+$/g, ""),
            threads: parseInt(document.getElementById("cfgThreads").value) || 0,
            maxConcurrent: parseInt(document.getElementById("cfgMaxConcurrent").value) || DEFAULT_SETTINGS.maxConcurrent,
            preferredQuality: document.getElementById("cfgQuality").value,
            domainBlacklist: document.getElementById("cfgDomainBlacklist").value
        };
        await saveSettings(settings);
        const msg = document.getElementById("settingsSavedMsg");
        msg.innerText = "✅ Configurações salvas!";
        msg.style.color = "#16a34a";
        setTimeout(() => { msg.innerText = ""; }, 2500);
    };
}

async function init() {
    initSettingsPanel();

    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    const container = document.getElementById("info");

    if (!tab) {
        container.innerHTML = `<div class="empty-state"><p class="empty-title">Erro</p><p class="empty-sub">Não foi possível identificar a aba atual.</p></div>`;
        return;
    }

    // Show a subtle loading state while querying background
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon" style="animation: pulse 1s ease-in-out infinite;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
            <p class="empty-sub" style="color:#9ca3af">Procurando streams...</p>
        </div>
    `;

    browser.runtime.sendMessage({ type: "GET_VIDEO_DATA", tabId: tab.id })
        .then(async videos => {
            const settings = await loadSettings();
            let serverAlive = true;
            try {
                await fetch(`${settings.backendUrl}/status`);
            } catch (err) {
                serverAlive = false;
            }

            if (!serverAlive) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon" style="background:#fef2f2; color:#ef4444;">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
                        </div>
                        <p class="empty-title">Servidor Offline</p>
                        <p class="empty-sub">O backend Python não está rodando.</p>
                        <button id="startServerBtn" class="btn btn-primary" style="margin-top:10px; background:#10b981;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                            Ligar Servidor Python
                        </button>
                        <p id="serverMsg" style="margin-top:8px; font-size:11px; color:#6b7280;"></p>
                    </div>
                `;
                
                document.getElementById("startServerBtn").onclick = async () => {
                    const btn = document.getElementById("startServerBtn");
                    const msg = document.getElementById("serverMsg");
                    btn.disabled = true;
                    btn.innerHTML = `⏳ Iniciando...`;
                    msg.innerText = "Invocando Native Messaging...";
                    
                    try {
                        const port = browser.runtime.connectNative("com.vidjo.idify");
                        port.postMessage({ command: "start" });
                        
                        let attempts = 0;
                        let interval = setInterval(async () => {
                            attempts++;
                            try {
                                const resp = await fetch(`${settings.backendUrl}/status`);
                                if (resp.ok) {
                                    clearInterval(interval);
                                    port.disconnect();
                                    msg.innerText = "✅ Servidor Online!";
                                    msg.style.color = "#10b981";
                                    setTimeout(() => location.reload(), 1000);
                                }
                            } catch (e) {
                                if (attempts > 15) {
                                    clearInterval(interval);
                                    msg.innerText = "❌ Tempo esgotado. Servidor não subiu.";
                                    msg.style.color = "#ef4444";
                                    btn.disabled = false;
                                    btn.innerHTML = `Tentar Novamente`;
                                }
                            }
                        }, 500);

                        port.onDisconnect.addListener((p) => {
                            let errMsg = "❌ O aplicativo de download fechou sozinho.";
                            if (browser.runtime.lastError) {
                                errMsg = "❌ O navegador bloqueou a conexão de rede local.";
                            }
                            if (interval) clearInterval(interval);
                            msg.innerText = errMsg;
                            msg.style.color = "#ef4444";
                            btn.disabled = false;
                            btn.innerHTML = `Tentar Novamente`;
                        });
                        
                    } catch (e) {
                        msg.innerText = "❌ Falha ao tentar ligar: " + e.message;
                        msg.style.color = "#ef4444";
                        btn.disabled = false;
                        btn.innerHTML = `Tentar Novamente`;
                        console.error(e);
                    }
                };
                return;
            }

            if (videos && videos.length > 0) {
                renderVideos(videos, container, tab);
            } else {
                // Nothing from background — silently scan the page DOM
                await scanPageDirectly(tab, container);
            }
            
            const toggleCodeBtn = document.getElementById("toggleCodeBtn");
            const codeSection = document.getElementById("codeSection");
            if (codeSection) codeSection.style.display = "none";
            if (toggleCodeBtn && codeSection) {
                toggleCodeBtn.addEventListener("click", (e) => {
                    e.preventDefault();
                    if (codeSection.style.display === "none") {
                        codeSection.style.display = "block";
                        toggleCodeBtn.innerText = "Ocultar detalhes";
                    } else {
                        codeSection.style.display = "none";
                        toggleCodeBtn.innerText = "Mais detalhes (Uso Manual)";
                    }
                });
            }

            // Check if there is an active task to resume polling
            const activeTask = await checkActiveTask(settings.backendUrl, tab.id);
            if (activeTask) {
                const btn = document.getElementById("sendBtn");
                if (btn) {
                    btn.disabled = true;
                    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Em andamento...`;
                }
                startPolling(activeTask.taskId, settings.backendUrl);
            }
        })
        .catch(async err => {
            console.error("Background error:", err);
            // Try DOM scan as fallback
            await scanPageDirectly(tab, container);
        });
}

init();
