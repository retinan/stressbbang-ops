"""예약 목록(queue/*.json) 중 시간이 된 글을 스레드·인스타 릴스에 올린다.

예 (queue/2026-11-11-2100-p12.json):
{
  "id": "p12",
  "at": "2026-11-11T21:00:00+09:00",
  "channels": ["threads", "instagram"],
  "text": "스레드 본문 (링크 포함)",
  "ig_caption": "릴스 캡션 (없으면 text를 씀)",
  "media": "media/2026-11-11-xxx.mp4",
  "topic": "직장인 공감"
}
- 인스타는 영상(.mp4/.mov)만 올린다 (릴스).
- 채널마다 따로 기록하므로, 한 채널이 실패해도 다른 채널은 올라가고 실패한 쪽만 다음 회차에 다시 시도한다.
"""
import glob, os, time
from datetime import datetime
from common import (CONFIG, GRAPH, IG, HttpError, channels_of, env, head_ok, http, load,
                    now_kst, path, save, short, state_key, telegram)

VIDEO = (".mp4", ".mov")
IMAGE = (".png", ".jpg", ".jpeg")


def media_url(media):
    return CONFIG["pages_base"].rstrip("/") + "/" + media.lstrip("/")


def poll(url, params, field, ok, bad, limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = http("GET", url, params)
        s = st.get(field)
        if s in ok:
            return
        if s in bad:
            raise RuntimeError(f"처리 실패 {s}: {st}")
        time.sleep(10)
    raise RuntimeError("영상 처리 시간 초과")


def post_threads(post):
    token = env("THREADS_TOKEN")
    media = post.get("media")
    params = {"text": post["text"], "access_token": token}
    if not media:
        params["media_type"] = "TEXT"
    elif os.path.splitext(media)[1].lower() in VIDEO:
        params.update(media_type="VIDEO", video_url=media_url(media))
    elif os.path.splitext(media)[1].lower() in IMAGE:
        params.update(media_type="IMAGE", image_url=media_url(media))
    if post.get("topic"):
        params["topic_tag"] = post["topic"]
    try:
        cid = http("POST", f"{GRAPH}/me/threads", params)["id"]
    except HttpError as e:
        if "topic_tag" in params and "topic" in e.body.lower():
            params.pop("topic_tag")
            cid = http("POST", f"{GRAPH}/me/threads", params)["id"]
        else:
            raise
    if params["media_type"] != "TEXT":
        poll(f"{GRAPH}/{cid}", {"fields": "status,error_message", "access_token": token},
             "status", ("FINISHED",), ("ERROR", "EXPIRED"))
    mid = http("POST", f"{GRAPH}/me/threads_publish", {"creation_id": cid, "access_token": token})["id"]
    link = http("GET", f"{GRAPH}/{mid}", {"fields": "permalink", "access_token": token}).get("permalink", "")
    return mid, link


def post_instagram(post):
    token = env("IG_TOKEN")
    media = post.get("media") or ""
    if os.path.splitext(media)[1].lower() not in VIDEO:
        raise RuntimeError("인스타는 영상(릴스)만 올려요. media에 .mp4를 넣어 주세요.")
    cid = http("POST", f"{IG}/me/media", {
        "media_type": "REELS", "video_url": media_url(media), "share_to_feed": "true",
        "caption": post.get("ig_caption") or post["text"], "access_token": token})["id"]
    poll(f"{IG}/{cid}", {"fields": "status_code,status", "access_token": token},
         "status_code", ("FINISHED",), ("ERROR", "EXPIRED"))
    mid = http("POST", f"{IG}/me/media_publish", {"creation_id": cid, "access_token": token})["id"]
    link = http("GET", f"{IG}/{mid}", {"fields": "permalink", "access_token": token}).get("permalink", "")
    return mid, link


SENDERS = {"threads": ("스레드", post_threads), "instagram": ("릴스", post_instagram)}


def main():
    state = load("state/posted.json", {"posted": {}})
    done = state["posted"]
    now = now_kst()
    changed = False
    for f in sorted(glob.glob(path("queue", "*.json"))):
        post = load(os.path.relpath(f, path()))
        pid = post.get("id") or os.path.basename(f)
        at = datetime.fromisoformat(post["at"])
        if at > now:
            continue
        late = int((now - at).total_seconds() // 60)
        for ch in channels_of(post):
            key = state_key(pid, ch)
            if key in done:
                continue
            label, send = SENDERS[ch]
            try:
                if post.get("media"):
                    ok, info = head_ok(media_url(post["media"]))
                    if not ok:
                        print(f"[{key}] 미디어가 아직 안 열림: {info}. 다음 회차에 다시.")
                        continue
                mid, link = send(post)
                done[key] = {"media_id": mid, "posted_at": now.isoformat(timespec="minutes"), "permalink": link}
                changed = True
                msg = f"✅ [{label} 올림] {pid}\n{short(post.get('ig_caption') if ch == 'instagram' and post.get('ig_caption') else post['text'], 60)}\n{link}"
                if late > CONFIG.get("late_warn_minutes", 120):
                    msg += f"\n(예약보다 {late}분 늦게 올라감)"
                telegram(msg)
                print(f"[{key}] 올림 {link}")
            except Exception as e:
                print(f"[{key}] 실패: {e}")
                telegram(f"⚠️ [{label} 올리기 실패] {pid}\n{short(str(e), 300)}\n다음 회차(15분 뒤)에 다시 시도해요.")
    if changed:
        save("state/posted.json", state)


if __name__ == "__main__":
    main()
