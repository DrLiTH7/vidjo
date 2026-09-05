// Runs in ISOLATED world — does NOT modify any page globals, so it is
// undetectable by page scripts.
// Captures <video src="..."> and <source src="..." type="..."> elements
// whose src points directly to an M3U8 file (or declares an M3U8 type).

function looksLikeM3U8(url, type) {
    if (!url || url.startsWith("blob:") || url.startsWith("data:")) return false;
    try {
        const path = new URL(url).pathname.toLowerCase();
        if (path.includes(".m3u8")) return true;
    } catch (_) {}
    const t = (type || "").toLowerCase();
    return t.includes("mpegurl");
}

function report(url) {
    browser.runtime.sendMessage({
        type: "M3U8_FROM_DOM",
        url,
        headers: {},
    }).catch(() => {});
}

function checkElement(el) {
    // Use .src (resolved absolute URL) when available; fall back to attribute.
    const url = el.src || el.getAttribute("src") || "";
    const type = el.getAttribute("type") || "";
    if (url && looksLikeM3U8(url, type)) report(url);
}

function scanAll() {
    document.querySelectorAll("video, source").forEach(checkElement);
}

const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        // Newly inserted nodes
        for (const node of mutation.addedNodes) {
            if (node.nodeType !== Node.ELEMENT_NODE) continue;
            const tag = node.tagName;
            if (tag === "VIDEO" || tag === "SOURCE") {
                checkElement(node);
            }
            node.querySelectorAll?.("video, source").forEach(checkElement);
        }
        // src attribute changed on an existing element
        if (
            mutation.type === "attributes" &&
            (mutation.target.tagName === "VIDEO" || mutation.target.tagName === "SOURCE")
        ) {
            checkElement(mutation.target);
        }
    }
});

observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "type"],
});

// Scan elements already in the DOM when the script runs
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scanAll);
} else {
    scanAll();
}
