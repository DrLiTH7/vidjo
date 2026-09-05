// Injects page_interceptor.js into the page's own JS context so it can
// wrap fetch/XHR. This is equivalent to world:"MAIN" but works in all
// Firefox versions without requiring manifest support for that field.
const script = document.createElement("script");
script.src = browser.runtime.getURL("page_interceptor.js");
document.documentElement.appendChild(script);
