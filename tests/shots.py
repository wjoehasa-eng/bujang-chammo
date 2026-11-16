#!/usr/bin/env python3
"""부장 참모 — 시연 데이터로 스크린샷 촬영"""
import json, pathlib, threading, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT.parent / "bujang-shots"
SHOTS.mkdir(exist_ok=True)
PORT = 8777
ORIGIN = f"http://127.0.0.1:{PORT}"

SEED = {
  "v": 2,
  "items": [
    {"id": "i1", "t": "6반 학부모 민원 답변 정리", "cat": "dolbal", "due": "2026-11-17", "who": "나", "memo": "퇴근 전 전화. 담임과 문구 먼저 맞추기", "done": False, "at": "2026-11-16T23:10:00Z"},
    {"id": "i2", "t": "체험학습 안전계획·동의서 확인", "cat": "haksaeng", "due": "2026-11-20", "who": "3반 담임", "memo": "", "done": False, "at": "2026-11-16T22:10:00Z"},
    {"id": "i3", "t": "협의회 안건 초안 공유", "cat": "gyosa", "due": "2026-11-18", "who": "나", "memo": "하루 전 오전까지", "done": False, "at": "2026-11-16T21:10:00Z"},
    {"id": "i4", "t": "11월 학년 공지 문구 확정", "cat": "gyosa", "due": "", "who": "", "memo": "", "done": True, "at": "2026-11-15T21:10:00Z"}
  ],
  "ck": {"2026-11-17": ["am:0", "am:1", "am:2", "pm:0"]},
  "notes": {"p06": [{"at": "2026-11-16T23:20:00Z", "text": "말로 하지 말고 '무엇을·언제까지·왜' 세 줄로 문자. 다음 날 바로 올라왔다."}]},
  "cur": {"s1:0": True, "s2:0": True, "s3:0": True, "s3:1": True, "s!:0": True, "s4:0": True},
  "areas": {"a1": {"st": "doing", "memo": "분장 기준표 초안 작성. 시수·전년도 이월 두 축으로."}},
  "road": {"r1:0": True, "r1:1": True, "r1:2": True},
  "meetings": [{
    "id": "m1", "date": "2026-11-12", "name": "11월 학년 협의회 결과",
    "text": "[11월 학년 협의회 결과] 11월 12일 (목)\n\n■ 확정\n1. 5학년 체험학습 11/28(금) 실시 (담당 나, ~11/21)\n2. 수행평가 제출일 11/26로 통일 (담당 학년부장)\n\n■ 보류\n· 운동회 종목 — 예산 확인 후 결정 (다음 확인 11/25)\n\n■ 안내\n다음 협의는 11/26(수) 15:30입니다.\n\n문의는 학년부장에게 주시면 됩니다.",
    "at": "2026-11-12T07:00:00Z"
  }],
  "mdraft": {"date": "2026-11-17", "name": "학년 협의회 결과",
             "rows": [{"k": "확정", "t": "5학년 체험학습 11/28(금) 실시", "who": "나", "due": "2026-11-21"},
                      {"k": "보류", "t": "운동회 종목 — 예산 확인 후 결정", "who": "", "due": "2026-11-25"}],
             "memo": "다음 협의는 11/26(수) 15:30입니다."},
  "sheetUrl": "", "docUrl": "", "autoSync": True, "updatedAt": "2026-11-17T00:20:00Z"
}

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

srv = ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 950}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(ORIGIN + "/index.html", wait_until="networkidle")
    page.evaluate("d => localStorage.setItem('bc2_state', JSON.stringify(d))", SEED)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / "desk.png"))
    page.screenshot(path=str(SHOTS / "desk-full.png"), full_page=True)

    page.click('[data-act="tab"][data-tab="playbook"]')
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "playbook.png"))
    page.screenshot(path=str(SHOTS / "playbook-full.png"), full_page=True)
    page.locator('[data-act="open-pb"][data-id="p06"]').click()
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "playbook-detail.png"))
    page.keyboard.press("Escape")

    page.click('[data-act="tab"][data-tab="meeting"]')
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "meeting.png"))
    page.screenshot(path=str(SHOTS / "meeting-full.png"), full_page=True)

    page.click('[data-act="tab"][data-tab="curric"]')
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "curriculum.png"))
    page.screenshot(path=str(SHOTS / "curriculum-full.png"), full_page=True)

    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "settings.png"))

    # 다크 모드
    page.click('[data-act="theme"][data-theme="dark"]')
    page.wait_for_timeout(250)
    page.click('[data-act="tab"][data-tab="desk"]')
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "dark-desk.png"))
    page.click('[data-act="tab"][data-tab="playbook"]')
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / "dark-playbook.png"))
    ctx.close()

    # 모바일
    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    mp = m.new_page()
    mp.goto(ORIGIN + "/index.html", wait_until="networkidle")
    mp.evaluate("d => { localStorage.setItem('bc2_state', JSON.stringify(d)); localStorage.setItem('bc2_theme', 'light'); }", SEED)
    mp.reload(wait_until="networkidle")
    mp.wait_for_timeout(500)
    mp.screenshot(path=str(SHOTS / "mobile-desk.png"))
    mp.click('.bottomnav [data-tab="playbook"]')
    mp.wait_for_timeout(350)
    mp.screenshot(path=str(SHOTS / "mobile-playbook.png"))
    mp.locator('[data-act="open-pb"][data-id="p01"]').click()
    mp.wait_for_timeout(400)
    mp.screenshot(path=str(SHOTS / "mobile-playbook-detail.png"))
    mp.keyboard.press("Escape")
    mp.click('.bottomnav [data-tab="meeting"]')
    mp.wait_for_timeout(350)
    mp.screenshot(path=str(SHOTS / "mobile-meeting.png"))
    mp.click('.bottomnav [data-tab="curric"]')
    mp.wait_for_timeout(350)
    mp.screenshot(path=str(SHOTS / "mobile-curriculum.png"))
    m.close()
    b.close()

srv.shutdown()
print("shots:", sorted(p.name for p in SHOTS.glob("*.png")))
