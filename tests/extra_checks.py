#!/usr/bin/env python3
"""부장 참모 v3 — 추가 확인: 내보내기/불러오기, 초안 유지, 노트 카운트, 테마 유지, 스냅샷 한도"""
import json, pathlib, threading, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8792
ORIGIN = f"http://127.0.0.1:{PORT}"
results = []
def check(n, c, d=""):
    results.append((n, bool(c))); print(("PASS " if c else "FAIL ") + n + ((" — " + str(d)) if d and not c else ""))

class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

srv = ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Q, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    page.goto(ORIGIN + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(300)

    # 1) 회의 전 안내문: 탭 재진입 시 유지
    page.click('.railnav [data-tab="meeting"]'); page.wait_for_timeout(300)
    page.fill("#mName", "테스트 협의회")
    page.fill('#mAgenda [data-act="ag-t"]', "체험학습 일정")
    page.fill('#mAgenda [data-act="ag-d"]', "11/28")
    page.fill("#mFixed", "학사일정")
    page.wait_for_timeout(300)
    page.click('.railnav [data-tab="desk"]'); page.wait_for_timeout(200)
    page.click('.railnav [data-tab="meeting"]'); page.wait_for_timeout(300)
    prev = page.input_value("#mPreview")
    check("회의 안내문 초안 유지", "체험학습 일정" in prev and "학사일정" in prev, prev[:80])

    # 2) 회의 후 공지도 모드만 바꿔 이어서 만들 수 있음
    page.click('[data-act="m-mode"][data-mode="after"]'); page.wait_for_timeout(250)
    page.fill('#mRows [data-act="mrow-t"]', "체험학습 11/28 실시")
    page.wait_for_timeout(250)
    page.click('[data-act="m-mode"][data-mode="before"]'); page.wait_for_timeout(250)
    page.click('[data-act="m-mode"][data-mode="after"]'); page.wait_for_timeout(250)
    check("모드 왕복 후 공지 유지", "체험학습 11/28" in page.input_value("#mPreview"), page.input_value("#mPreview")[:60])

    # 3) 사례 노트 → 카드 카운트
    page.click('.railnav [data-tab="playbook"]'); page.wait_for_timeout(250)
    page.locator('[data-act="open-pb"][data-id="g04"]').click(); page.wait_for_timeout(300)
    page.fill("#noteInput", "기준표 공개 후 문의가 줄었다")
    page.click('[data-act="note-save"]'); page.wait_for_timeout(300)
    page.keyboard.press("Escape"); page.wait_for_timeout(250)
    card = page.locator('[data-act="open-pb"][data-id="g04"]').inner_text()
    check("카드에 내 사례 수 표시", "내 사례 1" in card, card)

    # 4) 트래커 삭제(인라인 확인)
    page.click('.railnav [data-tab="desk"]'); page.wait_for_timeout(200)
    page.click('[data-act="item-new"]'); page.fill("#ifT", "지울 사안"); page.click('[data-act="item-save"]')
    page.wait_for_timeout(250)
    page.click('[data-act="item-askdel"]'); page.wait_for_timeout(150)
    page.click('[data-act="item-del"]'); page.wait_for_timeout(250)
    check("사안 삭제", page.locator("#trackList .item").count() == 0)

    # 5) 테마 고정 유지
    page.click('.railnav [data-tab="settings"]'); page.wait_for_timeout(200)
    page.click('[data-act="theme"][data-theme="dark"]'); page.wait_for_timeout(150)
    page.reload(wait_until="networkidle"); page.wait_for_timeout(400)
    check("테마 새로고침 후 유지", page.get_attribute("html", "data-theme") == "dark",
          page.get_attribute("html", "data-theme"))

    # 6) 리허설 상태도 새로고침 후 유지
    page.click('.railnav [data-tab="desk"]'); page.wait_for_timeout(200)
    page.fill("#rehTitle", "리허설 유지 확인")
    page.click('[data-act="reh-ans"][data-q="who"][data-v="some"]'); page.wait_for_timeout(200)
    page.reload(wait_until="networkidle"); page.wait_for_timeout(400)
    check("리허설 답 유지", page.input_value("#rehTitle") == "리허설 유지 확인" and
          page.locator('[data-act="reh-ans"][data-q="who"][data-v="some"]').get_attribute("aria-pressed") == "true")

    # 7) JSON 내보내기 → 불러오기 왕복
    page.click('.railnav [data-tab="settings"]'); page.wait_for_timeout(200)
    with page.expect_download() as dl:
        page.click('[data-act="export"]')
    path = dl.value.path()
    exported = json.load(open(path, encoding="utf-8"))
    check("내보내기 파일 형식", exported.get("app") == "부장 참모" and "data" in exported)
    check("내보낸 데이터에 회의 초안", exported["data"]["mdraft"]["agenda"][0]["t"].startswith("체험학습"))
    check("내보낸 데이터에 리허설", exported["data"]["reh"]["t"] == "리허설 유지 확인")

    page.click('[data-act="wipe"]'); page.wait_for_timeout(200)
    page.click('[data-act="wipe"][data-confirm="1"]'); page.wait_for_timeout(400)
    check("전체 지우기", page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).meetings.length") == 0)
    page.set_input_files("#importFile", path)
    page.wait_for_timeout(600)
    restored = page.evaluate("JSON.parse(localStorage.getItem('bc2_state'))")
    check("불러오기로 복원", restored["mdraft"]["agenda"][0]["t"].startswith("체험학습")
          and restored["notes"]["g04"][0]["text"].startswith("기준표"))

    # 8) 스냅샷 목록 최대 5개
    for _ in range(7):
        page.click('[data-act="snap-now"]'); page.wait_for_timeout(80)
    n = page.locator("#snapList .snap").count()
    check("스냅샷 최대 5개", n == 5, n)

    ctx.close(); b.close()
srv.shutdown()
print("\n", sum(1 for _, ok in results if ok), "/", len(results), "통과")
print("실패:", [n for n, ok in results if not ok] or "없음")
