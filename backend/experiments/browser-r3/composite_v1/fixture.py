"""Bounded route bytes only; no server or browser startup."""

PAGE = b"""<!doctype html><title>R3 composite</title>
<iframe src='/iframe'></iframe><script src='/script'></script>
<a id='download' download href='/download'>download</a>
<script>
window.composite = {
  xhr: () => new Promise(resolve => {const x=new XMLHttpRequest();
    x.open('GET','/xhr'); x.onload=()=>resolve(x.status); x.send();}),
  fetch: () => fetch('/fetch'),
  pageWS: () => new WebSocket('wss://fixture-r3.test/page-ws'),
  workerWS: () => {const w=new Worker('/worker-script'); w.postMessage('start'); return w;},
  popup: () => window.open('/popup','r3-popup'),
  register: () => navigator.serviceWorker.register('/sw-script'),
  update: registration => registration.update(),
  swFetch: registration => registration.active.postMessage('fetch')
};</script>"""
WORKER = b"onmessage=()=>new WebSocket('wss://fixture-r3.test/worker-ws');"
SW = b"onmessage=()=>fetch('/sw-fetch');"


def response(route: str) -> tuple[int, bytes, str, str | None]:
    routes = {
        "navigation": (200, PAGE, "text/html", None),
        "redirect-start": (302, b"", "text/plain", "/redirect-end"),
        "redirect-end": (200, b"<title>redirect</title>", "text/html", None),
        "iframe": (200, b"<title>frame</title>", "text/html", None),
        "script": (200, b"window.r3ScriptLoaded=true;", "application/javascript", None),
        "worker-script": (200, WORKER, "application/javascript", None),
        "sw-script": (200, SW, "application/javascript", None),
        "xhr": (200, b"{}", "application/json", None),
        "fetch": (200, b"{}", "application/json", None),
    }
    return routes.get(route, (403, b"", "text/plain", None))
