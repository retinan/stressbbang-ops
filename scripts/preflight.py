"""예약 확인: 아직 안 올라간 스레드 글의 영상 주소가 열리는지 확인하고 텔레그램으로 요약.
queue에 글을 넣을 때(push) 실행된다. Pages 배포를 기다리며 최대 5분 재시도."""
import glob, os, time
from datetime import datetime
from common import CONFIG, channels_of, head_ok, load, path, short, state_key, telegram

done = load("state/posted.json", {"posted": {}})["posted"]
pending = []
for f in sorted(glob.glob(path("queue", "*.json"))):
    p = load(os.path.relpath(f, path()))
    pid = p.get("id") or f
    left = [c for c in channels_of(p) if state_key(pid, c) not in done]
    if left:
        p["_left"] = left
        pending.append(p)
if not pending:
    print("예약된 글 없음")
    raise SystemExit
lines = ["🗓️ 예약 확인"]
NAMES = {"threads": "스레드", "instagram": "릴스"}
for p in pending:
    at = datetime.fromisoformat(p["at"]).strftime("%m/%d(%a) %H:%M")
    status = "글만"
    if p.get("media"):
        url = CONFIG["pages_base"].rstrip("/") + "/" + p["media"].lstrip("/")
        ok, info = False, ""
        for _ in range(10):
            ok, info = head_ok(url)
            if ok:
                break
            time.sleep(30)
        status = f"영상 OK ({info})" if ok else f"❌ 영상 주소 안 열림: {short(info, 80)}"
    lines.append(f"• {p.get('id')} · {at} · {'+'.join(NAMES[c] for c in p['_left'])} · {status}\n  {short(p['text'], 50)}")
telegram("\n".join(lines))
print("\n".join(lines))
