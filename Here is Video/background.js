let capturedVideos = {};
const pendingRequests = new Map();
const MAX_PENDING = 500;
let domainBlacklist = [];

browser.storage.local.get("settings").then(data => {
    if (data.settings && data.settings.domainBlacklist) {
        domainBlacklist = data.settings.domainBlacklist.split(',').map(s => s.trim().toLowerCase()).filter(s => s);
    }
}).catch(() => {});

browser.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes.settings) {
        const newVal = changes.settings.newValue || {};
        if (newVal.domainBlacklist !== undefined) {
            domainBlacklist = newVal.domainBlacklist.split(',').map(s => s.trim().toLowerCase()).filter(s => s);
        }
    }
});

// Restore state in case the background page was restarted
browser.storage.session.get("capturedVideos").then(data => {
    if (data.capturedVideos) capturedVideos = data.capturedVideos;
}).catch(() => {});

function isBlacklisted(url) {
    if (domainBlacklist.length === 0) return false;
    try {
        const hostname = new URL(url).hostname.toLowerCase();
        return domainBlacklist.some(domain => hostname.includes(domain));
    } catch (e) {
        return false;
    }
}

function captureVideo(tabId, url, headers) {
    // tabId -1 = request not associated with any tab (prerender, background, etc.)
    // Setting badge with tabId -1 makes it appear globally, which causes the
    // "badge shows but popup is empty" symptom.
    if (!tabId || tabId <= 0) return;

    if (isBlacklisted(url)) return;

    if (!capturedVideos[tabId]) capturedVideos[tabId] = [];
    if (capturedVideos[tabId].some(v => v.url === url)) return;

    capturedVideos[tabId].push({ url, headers, timestamp: Date.now() });

    // Persist so popup still works if background was briefly restarted
    browser.storage.session.set({ capturedVideos }).catch(() => {});

    const count = capturedVideos[tabId].length;
    browser.action.setBadgeText({ text: String(count), tabId });
    browser.action.setBadgeBackgroundColor({ color: "#2ecc71" });
}

// Phase 1: URL-based detection + store headers for content-type check
browser.webRequest.onBeforeSendHeaders.addListener(
    (details) => {
        const headersObj = {};
        for (const h of details.requestHeaders || []) {
            headersObj[h.name.toLowerCase()] = h.value;
        }

        if (details.url.includes(".m3u8")) {
            captureVideo(details.tabId, details.url, headersObj);
            return;
        }

        if (pendingRequests.size >= MAX_PENDING) {
            pendingRequests.delete(pendingRequests.keys().next().value);
        }
        pendingRequests.set(details.requestId, {
            url: details.url,
            headers: headersObj,
            tabId: details.tabId,
        });
    },
    { urls: ["<all_urls>"] },
    ["requestHeaders"]
);

// Phase 2: Content-type detection for URLs that don't contain ".m3u8"
browser.webRequest.onHeadersReceived.addListener(
    (details) => {
        const pending = pendingRequests.get(details.requestId);
        if (!pending) return;
        pendingRequests.delete(details.requestId);

        const ct = details.responseHeaders
            ?.find(h => h.name.toLowerCase() === "content-type")
            ?.value?.toLowerCase() || "";

        if (ct.includes("mpegurl")) {
            captureVideo(pending.tabId, pending.url, pending.headers);
        }
    },
    { urls: ["<all_urls>"] },
    ["responseHeaders"]
);

browser.webRequest.onCompleted.addListener(
    (details) => pendingRequests.delete(details.requestId),
    { urls: ["<all_urls>"] }
);
browser.webRequest.onErrorOccurred.addListener(
    (details) => pendingRequests.delete(details.requestId),
    { urls: ["<all_urls>"] }
);

browser.tabs.onRemoved.addListener((tabId) => {
    delete capturedVideos[tabId];
    browser.storage.session.set({ capturedVideos }).catch(() => {});
});

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "GET_VIDEO_DATA") {
        sendResponse(capturedVideos[message.tabId] || []);
        return true;
    }
    if (message.type === "M3U8_FROM_PAGE" || message.type === "M3U8_FROM_DOM") {
        const tabId = sender.tab?.id;
        if (tabId != null) captureVideo(tabId, message.url, message.headers || {});
    }
});
