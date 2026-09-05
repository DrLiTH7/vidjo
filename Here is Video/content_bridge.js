// Runs in ISOLATED world. Receives postMessage from page_interceptor.js
// and forwards M3U8 detections to background.js.
window.addEventListener("message", (event) => {
    if (event.source !== window || !event.data?.__m3u8_sniffer) return;
    browser.runtime.sendMessage({
        type: "M3U8_FROM_PAGE",
        url: event.data.url,
        headers: event.data.headers || {},
    }).catch(() => {});
});
