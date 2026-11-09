"""새 댓글을 텔레그램으로. 스레드 답글 + 유튜브(쇼츠) 댓글. 처음 실행 때 있던 댓글은 건너뛴다."""
from datetime import date, datetime, timedelta
from common import CONFIG, GRAPH, IG, HttpError, env, http, load, now_kst, save, short, telegram

state = load("state/seen.json", {"threads": [], "youtube": [], "init": {}, "alerts": {}})
for k, v in (("threads", []), ("youtube", []), ("instagram", []), ("init", {}), ("alerts", {})):
    state.setdefault(k, v)
out, notes = [], []


def remember(key, ids):
    seen = state[key]
    seen.extend(i for i in ids if i not in seen)
    state[key] = seen[-3000:]


def threads():
    token = env("THREADS_TOKEN")
    me = http("GET", f"{GRAPH}/me", {"fields": "id,username", "access_token": token})
    posts = http("GET", f"{GRAPH}/me/threads", {"fields": "id,text,timestamp,permalink", "limit": 25,
                                                 "access_token": token}).get("data", [])
    cutoff = now_kst() - timedelta(days=21)
    new, ids = [], []
    for p in posts:
        if datetime.fromisoformat(p["timestamp"].replace("+0000", "+00:00")) < cutoff:
            continue
        try:
            rs = http("GET", f"{GRAPH}/{p['id']}/conversation",
                      {"fields": "id,text,username,timestamp", "access_token": token}).get("data", [])
        except HttpError as e:
            if e.status in (400, 403) and ("permission" in e.body.lower() or "scope" in e.body.lower()):
                notes.append("스레드 답글 읽기 권한(threads_read_replies)이 토큰에 없어요. Meta 개발자 앱에서 권한을 추가하고 토큰을 다시 받아야 해요.")
                return
            raise
        for r in rs:
            ids.append(r["id"])
            if r["id"] in state["threads"] or r.get("username") == me.get("username"):
                continue
            new.append(f"💬 [스레드] {short(r.get('text'), 120)} — @{r.get('username')}\n   ↳ 글: {short(p.get('text'), 40)}\n   {p.get('permalink','')}")
    if not state["init"].get("threads"):
        state["init"]["threads"] = True
        notes.append(f"스레드 알림 시작 (기존 답글 {len(ids)}개는 건너뜀)")
        new = []
    out.extend(new)
    remember("threads", ids)


def youtube():
    key = env("YOUTUBE_API_KEY")
    cid = CONFIG.get("youtube_channel_id") or state.get("youtube_channel_id")
    if not cid:
        r = http("GET", "https://www.googleapis.com/youtube/v3/channels",
                 {"part": "id", "forHandle": CONFIG.get("youtube_handle", ""), "key": key})
        items = r.get("items", [])
        if not items:
            notes.append(f"유튜브 채널을 못 찾았어요 (핸들 {CONFIG.get('youtube_handle')}). config.json에 채널 ID를 넣어 주세요.")
            return
        cid = state["youtube_channel_id"] = items[0]["id"]
    r = http("GET", "https://www.googleapis.com/youtube/v3/commentThreads",
             {"part": "snippet", "allThreadsRelatedToChannelId": cid, "maxResults": 50,
              "order": "time", "key": key})
    new, ids = [], []
    for it in r.get("items", []):
        s = it["snippet"]["topLevelComment"]["snippet"]
        ids.append(it["id"])
        if it["id"] in state["youtube"] or s.get("authorChannelId", {}).get("value") == cid:
            continue
        new.append(f"💬 [유튜브] {short(s.get('textOriginal'), 120)} — {s.get('authorDisplayName')}\n   https://www.youtube.com/watch?v={it['snippet'].get('videoId','')}")
    if not state["init"].get("youtube"):
        state["init"]["youtube"] = True
        notes.append(f"유튜브 알림 시작 (기존 댓글 {len(ids)}개는 건너뜀)")
        new = []
    out.extend(new)
    remember("youtube", ids)


def instagram():
    token = env("IG_TOKEN", required=False)
    if not token:
        return
    me = http("GET", f"{IG}/me", {"fields": "username", "access_token": token})
    media = http("GET", f"{IG}/me/media", {"fields": "id,caption,permalink,timestamp", "limit": 20,
                                         "access_token": token}).get("data", [])
    new, ids = [], []
    for m in media:
        cs = http("GET", f"{IG}/{m['id']}/comments", {"fields": "id,text,username,timestamp",
                                                     "access_token": token}).get("data", [])
        for c in cs:
            ids.append(c["id"])
            if c["id"] in state["instagram"] or c.get("username") == me.get("username"):
                continue
            new.append(f"💬 [인스타] {short(c.get('text'), 120)} — @{c.get('username')}\n   ↳ 릴스: {short(m.get('caption'), 40)}\n   {m.get('permalink','')}")
    if not state["init"].get("instagram"):
        state["init"]["instagram"] = True
        notes.append(f"인스타 알림 시작 (기존 댓글 {len(ids)}개는 건너뜀)")
        new = []
    out.extend(new)
    remember("instagram", ids)


def token_age():
    today = now_kst().date().isoformat()
    for name, key, secret in (("스레드", "threads", "THREADS_TOKEN"), ("인스타", "ig", "IG_TOKEN")):
        if not CONFIG.get(f"{key}_token_issued"):
            continue
        issued = date.fromisoformat(CONFIG[f"{key}_token_issued"])
        left = CONFIG.get(f"{key}_token_days", 60) - (now_kst().date() - issued).days
        if left <= 7 and state["alerts"].get(f"token_{key}") != today:
            state["alerts"][f"token_{key}"] = today
            notes.append(f"⏰ {name} 토큰이 {left}일 뒤 만료돼요. 새 토큰을 받아 {secret}를 바꾸고 config.json의 {key}_token_issued 날짜를 고쳐 주세요.")


for fn in (threads, instagram, youtube, token_age):
    try:
        fn()
    except Exception as e:
        notes.append(f"⚠️ {fn.__name__} 확인 실패: {short(str(e), 200)}")

msgs = out + notes
if msgs:
    telegram("\n\n".join(msgs))
print("\n".join(msgs) or "새 소식 없음")
save("state/seen.json", state)
