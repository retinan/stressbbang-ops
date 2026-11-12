"""주간 숫자 보고: 쇼츠·스레드·릴스 숫자를 한 번에 텔레그램으로.
- 유튜브: 공개 숫자(조회수·좋아요·댓글). 지난 보고 대비 증가분도 표시.
- 스레드·릴스: 토큰에 인사이트 권한이 있으면 조회수 등, 없으면 건너뛰고 알림.
- '시청함 vs 스와이프'와 평균 시청 비율은 API로 못 가져와서 스튜디오 캡처를 부탁한다.
"""
from common import CONFIG, GRAPH, env, http, HttpError, load, save, telegram, now_kst

IG = "https://graph.instagram.com"
prev = load("state/stats.json", {}) or {}
snap = {"at": now_kst().strftime("%Y-%m-%d %H:%M"), "youtube": {}, "threads": {}, "instagram": {}}
out, notes = [], []


def delta(ch, vid, v):
    p = (prev.get(ch) or {}).get(vid)
    return f" (+{v - p})" if isinstance(p, int) and v >= p else ""


def youtube():
    key = env("YOUTUBE_API_KEY")
    cid = CONFIG.get("youtube_channel_id") or (load("state/seen.json", {}) or {}).get("youtube_channel_id")
    if not cid:
        notes.append("유튜브 채널 ID를 못 찾았어요."); return
    ch = http("GET", "https://www.googleapis.com/youtube/v3/channels", {"part": "contentDetails,statistics", "id": cid, "key": key})
    it = ch["items"][0]
    up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = http("GET", "https://www.googleapis.com/youtube/v3/playlistItems", {"part": "contentDetails", "playlistId": up, "maxResults": 30, "key": key})
    ids = [x["contentDetails"]["videoId"] for x in pl.get("items", [])]
    if not ids:
        return
    vs = http("GET", "https://www.googleapis.com/youtube/v3/videos", {"part": "snippet,statistics", "id": ",".join(ids), "key": key})
    rows = []
    for v in vs.get("items", []):
        s = v["statistics"]; views = int(s.get("viewCount", 0))
        snap["youtube"][v["id"]] = views
        rows.append((views, v["snippet"]["title"][:28], int(s.get("likeCount", 0)), int(s.get("commentCount", 0)), delta("youtube", v["id"], views)))
    rows.sort(reverse=True)
    tot = sum(r[0] for r in rows)
    out.append(f"▶️ 쇼츠 (구독자 {it['statistics'].get('subscriberCount', '?')}, 총 조회 {tot:,})")
    for views, title, likes, com, d in rows[:15]:
        out.append(f"  {views:>5}{d}  ♥{likes} 💬{com}  {title}")


def insights(ch, base, token, mid, metrics):
    r = http("GET", f"{base}/{mid}/insights", {"metric": metrics, "access_token": token})
    vals = {}
    for m in r.get("data", []):
        v = m.get("values", [{}])[0].get("value", m.get("total_value", {}).get("value", 0))
        vals[m["name"]] = v
    return vals


def social():
    posted = (load("state/posted.json", {}) or {}).get("posted", {})
    queue = {}
    import glob, json, os
    for f in glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "queue", "*.json")):
        d = json.load(open(f, encoding="utf-8")); queue[d["id"]] = d.get("text", "").split("\n")[0][:24]
    th, ig = env("THREADS_TOKEN", False), env("IG_TOKEN", False)
    trows, irows, terr, ierr = [], [], None, None
    for key, p in sorted(posted.items()):
        pid, _, chn = key.partition("@")
        try:
            if not chn and th:
                v = insights("threads", GRAPH, th, p["media_id"], "views,likes,replies,reposts,shares")
                n = int(v.get("views", 0)); snap["threads"][pid] = n
                trows.append((n, pid, v, delta("threads", pid, n)))
            elif chn == "instagram" and ig:
                v = insights("instagram", IG, ig, p["media_id"], "views,reach,likes,comments,shares,saved")
                n = int(v.get("views", 0)); snap["instagram"][pid] = n
                irows.append((n, pid, v, delta("instagram", pid, n)))
        except HttpError as e:
            if chn: ierr = ierr or e.body[:160]
            else: terr = terr or e.body[:160]
    if trows:
        out.append("🧵 스레드")
        for n, pid, v, d in sorted(trows, key=lambda r: r[1]):
            out.append(f"  {pid} 조회 {n}{d} ♥{v.get('likes', 0)} 💬{v.get('replies', 0)} 🔁{v.get('reposts', 0)}  {queue.get(pid, '')}")
    elif terr:
        notes.append("스레드 숫자를 못 가져왔어요(토큰에 인사이트 권한이 없을 수 있어요).")
    if irows:
        out.append("🎬 릴스")
        for n, pid, v, d in sorted(irows, key=lambda r: r[1]):
            out.append(f"  {pid} 조회 {n}{d} 도달 {v.get('reach', 0)} ♥{v.get('likes', 0)} 💬{v.get('comments', 0)} 저장 {v.get('saved', 0)}  {queue.get(pid, '')}")
    elif ierr:
        notes.append("릴스 숫자를 못 가져왔어요(토큰에 인사이트 권한이 없을 수 있어요).")


for fn in (youtube, social):
    try:
        fn()
    except Exception as e:  # noqa
        notes.append(f"{fn.__name__}: {str(e)[:160]}")

since = f" · 괄호는 지난 보고({prev['at']}) 이후 증가" if prev.get("at") else ""
msg = [f"📊 주간 숫자 보고 {snap['at']}{since}"] + out
if notes:
    msg += [""] + ["⚠️ " + n for n in notes]
msg += ["", "📝 부탁: 유튜브 스튜디오에서 이번 주 쇼츠의 '시청함 vs 스와이프'와 '평균 조회율'을 캡처해서 Claude에게 보내 주세요."]
telegram("\n".join(msg))
save("state/stats.json", snap)
print("\n".join(msg))
