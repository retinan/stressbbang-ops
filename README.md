# stressbbang-ops

「스트레스 빵!」 마케팅 자동화. 게임 코드(stress-bbam)와 분리된 저장소.

## 하는 일
| 워크플로 | 언제 | 무엇 |
|---|---|---|
| 스레드 예약 게시 (`post.yml`) | 15분마다 + queue에 글을 넣을 때 | `queue/*.json` 중 시간이 된 글을 스레드에 올리고 텔레그램으로 알림 |
| 댓글 알림 (`notify.yml`) | 30분마다 (매시 7분, 37분) | 스레드 답글 + 유튜브(쇼츠) 댓글 중 새것만 텔레그램으로. 토큰 만료 1주 전 알림 |
| 연결 시험 (`whoami.yml`) | 직접 실행 | 스레드 계정, 답글 권한, 유튜브 채널 연결 확인 |

GitHub 예약 실행은 몇 분~수십 분 늦을 수 있다.

## 글 예약하는 법
1. 영상은 `media/`에 넣는다 (GitHub Pages로 공개 주소가 생김: `https://retinan.github.io/stressbbang-ops/media/파일명`).
2. `queue/`에 글 파일을 만든다. 파일 이름은 `날짜-시간-번호.json`.

```json
{
  "id": "p11",
  "at": "2026-11-09T21:00:00+09:00",
  "channel": "threads",
  "text": "본문\nhttps://stress-bbang.vercel.app/?utm_source=threads&utm_content=p11",
  "media": "media/2026-11-09-it.mp4",
  "topic": "직장인 공감"
}
```
- `media`를 빼면 글만 올라간다. `.mp4/.mov`는 영상, `.png/.jpg`는 사진.
- 한 번 올라간 글은 `state/posted.json`에 기록되어 다시 올라가지 않는다.

## Secrets (Settings → Secrets and variables → Actions)
`THREADS_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `YOUTUBE_API_KEY`

## 스레드 토큰 갱신 (60일)
만료 1주 전에 텔레그램으로 알림이 온다. Meta 개발자에서 새 장기 토큰을 받아 `THREADS_TOKEN`을 바꾸고, `config.json`의 `threads_token_issued`를 그날 날짜로 고친다.
