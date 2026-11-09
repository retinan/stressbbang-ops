"""예약 목록(queue/*.json) 중 시간이 된 스레드 글을 올린다.

글 파일 예 (queue/2026-11-09-2100-p11.json):
{
  "id": "p11",
  "at": "2026-11-09T21:00:00+09:00",
  "channel": "threads",
  "text": "본문 (링크 포함)",
  "media": "media/it-intern.mp4",      # 없으면 글만. .mp4/.mov = 영상, .png/.jpg = 사진
  "topic": "직장인 공감"                # 선택
}
"""
import glob, os, sys, time
from datetime import datetime
from common import (CONFIG, GRAPH, HttpError, env, head_ok, http, load, now_kst,
                    path, save, short, telegram)

VIDEO = (".mp4", ".mov")
IMAGE = (".png", ".jpg", ".jpeg")


def media_params(media):
    if not media:
        return {"media_type": "TEXT"}, None
    url = CONFIG["pages_base"].rstrip("/") + "/" + media.lstrip("/")
    ext = os.path.splitext(media)[1].lower()
    if ext in VIDEO:
        return {"media_type": "VIDEO", "video_url": url}, url
    if ext in IMAGE:
        return {"media_type": "IMAGE", "image_url": url}, url
    raise ValueError(f"모르는 파일 형식: {media}")


def create_container(token, post):
    params, url = media_params(post.get("media"))
    params.update({"text": post["text"], "access_token": token})
    if post.get("topic"):
        params["topic_tag"] = post["topic"]
    try:
        return http("POST", f"{GRAPH}/me/threads", params)["id"], url
    except HttpError as e:
        if post.get("topic") and "topic" in e.body.lower():
            params.pop("topic_tag")  # 주제 칸이 거절되면 주제 없이 다시
            return http("POST", f"{GRAPH}/me/threads", params)["id"], url
        raise


def wait_finished(token, cid, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = http("GET", f"{GRAPH}/{cid}", {"fields": "status,error_message", "access_token": token})
        s = st.get("status")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"컨테이너 {s}: {st.get('error_message')}")
        time.sleep(10)
    raise RuntimeError("영상 처리 시간 초과 (5분)")


def main():
    token = env("THREADS_TOKEN")
    state = load("state/posted.json", {"posted": {}})
    done = state["posted"]
    now = now_kst()
    changed = False
    for f in sorted(glob.glob(path("queue", "*.json"))):
        post = load(os.path.relpath(f, path()))
        pid = post.get("id") or os.path.basename(f)
        if post.get("channel", "threads") != "threads" or pid in done:
            continue
        at = datetime.fromisoformat(post["at"])
        if at > now:
            continue
        late = int((now - at).total_seconds() // 60)
        try:
            p, url = media_params(post.get("media"))
            if url:
                ok, info = head_ok(url)
                if not ok:
                    print(f"[{pid}] 미디어가 아직 안 열림: {info}. 다음 회차에 다시.")
                    continue
            cid, _ = create_container(token, post)
            if p["media_type"] != "TEXT":
                wait_finished(token, cid)
            mid = http("POST", f"{GRAPH}/me/threads_publish", {"creation_id": cid, "access_token": token})["id"]
            link = http("GET", f"{GRAPH}/{mid}", {"fields": "permalink", "access_token": token}).get("permalink", "")
            done[pid] = {"media_id": mid, "posted_at": now.isoformat(timespec="minutes"), "permalink": link}
            changed = True
            msg = f"✅ [스레드 올림] {pid}\n{short(post['text'], 60)}\n{link}"
            if late > CONFIG.get("late_warn_minutes", 120):
                msg += f"\n(예약보다 {late}분 늦게 올라감)"
            telegram(msg)
            print(f"[{pid}] 올림 {link}")
        except Exception as e:  # 실패는 기록만, 다음 회차에 다시 시도
            print(f"[{pid}] 실패: {e}")
            telegram(f"⚠️ [스레드 올리기 실패] {pid}\n{short(str(e), 300)}\n다음 회차(15분 뒤)에 다시 시도해요.")
    if changed:
        save("state/posted.json", state)


if __name__ == "__main__":
    main()
