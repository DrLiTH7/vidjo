// Runs in MAIN world at document_start — before any page script executes.
// Uses Proxy instead of direct replacement so toString() still returns
// "[native code]", making detection by the page much harder.
(function () {
    const M3U8_CONTENT_TYPES = [
        "application/x-mpegurl",
        "application/vnd.apple.mpegurl",
        "audio/mpegurl",
        "audio/x-mpegurl",
    ];

    function isM3U8ContentType(ct) {
        return M3U8_CONTENT_TYPES.some(t => (ct || "").toLowerCase().includes(t));
    }

    function isM3U8Text(text) {
        return typeof text === "string" && text.trimStart().startsWith("#EXTM3U");
    }

    function report(url, headers) {
        window.postMessage({ __m3u8_sniffer: true, url, headers }, "*");
    }

    // --- fetch ---
    // Proxy keeps the original function as the target, so:
    //   window.fetch.toString()       → "function fetch() { [native code] }"
    //   window.fetch instanceof Function → true
    //   Object.is(window.fetch, nativeFetch) → false (unavoidable), but toString passes
    window.fetch = new Proxy(window.fetch, {
        apply: async (target, thisArg, args) => {
            const [input, init] = args;
            const url =
                typeof input === "string" ? input
                : input instanceof Request ? input.url
                : String(input);

            const response = await Reflect.apply(target, thisArg, args);

            const ct = response.headers.get("content-type") || "";
            if (url.includes(".m3u8") || isM3U8ContentType(ct)) {
                try {
                    const text = await response.clone().text();
                    if (isM3U8Text(text)) {
                        const hdrs = {};
                        new Headers((init && init.headers) || {}).forEach(
                            (v, k) => { hdrs[k.toLowerCase()] = v; }
                        );
                        report(url, hdrs);
                    }
                } catch (_) {}
            }

            return response;
        },
    });

    // --- XMLHttpRequest.open ---
    XMLHttpRequest.prototype.open = new Proxy(XMLHttpRequest.prototype.open, {
        apply: (target, thisArg, args) => {
            thisArg.__url = String(args[1] || "");
            thisArg.__hdrs = {};
            return Reflect.apply(target, thisArg, args);
        },
    });

    // --- XMLHttpRequest.setRequestHeader ---
    XMLHttpRequest.prototype.setRequestHeader = new Proxy(
        XMLHttpRequest.prototype.setRequestHeader,
        {
            apply: (target, thisArg, args) => {
                if (!thisArg.__hdrs) thisArg.__hdrs = {};
                thisArg.__hdrs[String(args[0]).toLowerCase()] = String(args[1]);
                return Reflect.apply(target, thisArg, args);
            },
        }
    );

    // --- XMLHttpRequest.send ---
    XMLHttpRequest.prototype.send = new Proxy(XMLHttpRequest.prototype.send, {
        apply: (target, thisArg, args) => {
            thisArg.addEventListener("load", () => {
                const url = thisArg.__url || "";
                const ct = thisArg.getResponseHeader("content-type") || "";
                if (url.includes(".m3u8") || isM3U8ContentType(ct)) {
                    if (isM3U8Text(thisArg.responseText)) {
                        report(url, thisArg.__hdrs || {});
                    }
                }
            });
            return Reflect.apply(target, thisArg, args);
        },
    });
})();
