"""공통: 설정, 상태 파일, HTTP, 텔레그램. 표준 라이브러리만 사용."""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = timezone(timedelta(hours=9))
GRAPH = "https://graph.threads.net/v1.0"


def path(*p):
    return os.path.join(ROOT, *p)


def load(rel, default=None):
    try:
        with open(path(rel), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(rel, data):
    with open(path(rel), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


CONFIG = load("config.json", {})


def env(name, required=True):
    v = os.environ.get(name, "").strip()
    if required and not v:
        print(f"[!] 환경 변수 {name} 없음 (GitHub Secrets 확인)")
        sys.exit(1)
    return v


def now_kst():
    return datetime.now(KST)


class HttpError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status, self.body = status, body


def http(method, url, params=None, timeout=60):
    """JSON 응답을 dict로. 토큰이 들어간 URL은 절대 출력하지 않는다."""
    data = None
    if params and method == "GET":
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")) from None


def head_ok(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200, r.headers.get("Content-Type", "")
    except Exception as e:  # noqa
        return False, str(e)


def telegram(text):
    token = env("TELEGRAM_BOT_TOKEN")
    chat = env("TELEGRAM_CHAT_ID")
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]:
        http("POST", f"https://api.telegram.org/bot{token}/sendMessage",
             {"chat_id": chat, "text": chunk, "disable_web_page_preview": "true"})


def short(s, n=80):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"
