"""연결 시험: 토큰은 출력하지 않고, 어떤 계정과 연결됐는지만 텔레그램으로."""
from common import CONFIG, GRAPH, HttpError, env, http, short, telegram

lines = ["🔌 스트레스빵 자동화 연결 시험"]
token = env("THREADS_TOKEN")
try:
    me = http("GET", f"{GRAPH}/me", {"fields": "id,username", "access_token": token})
    lines.append(f"✅ 스레드: @{me.get('username')}")
    posts = http("GET", f"{GRAPH}/me/threads", {"fields": "id", "limit": 1, "access_token": token}).get("data", [])
    if posts:
        try:
            http("GET", f"{GRAPH}/{posts[0]['id']}/conversation", {"fields": "id", "access_token": token})
            lines.append("✅ 스레드 답글 읽기 권한 있음")
        except HttpError as e:
            lines.append(f"❌ 스레드 답글 읽기 권한 없음 (threads_read_replies 필요): {short(e.body, 120)}")
    lim = http("GET", f"{GRAPH}/me/threads_publishing_limit", {"fields": "quota_usage,config", "access_token": token})
    lines.append(f"✅ 게시 권한 확인 (24시간 사용량: {lim.get('data',[{}])[0].get('quota_usage','?')})")
except HttpError as e:
    lines.append(f"❌ 스레드 연결 실패: {short(e.body, 200)}")
try:
    key = env("YOUTUBE_API_KEY")
    r = http("GET", "https://www.googleapis.com/youtube/v3/channels",
             {"part": "snippet", "forHandle": CONFIG.get("youtube_handle", ""), "key": key})
    it = (r.get("items") or [{}])[0]
    if it:
        lines.append(f"✅ 유튜브: {it['snippet']['title']} ({it['id']})")
    else:
        lines.append(f"❌ 유튜브 채널을 핸들 {CONFIG.get('youtube_handle')}로 못 찾음")
except HttpError as e:
    lines.append(f"❌ 유튜브 키 확인 실패: {short(e.body, 200)}")
telegram("\n".join(lines))
print("\n".join(lines))
