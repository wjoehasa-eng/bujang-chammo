#!/usr/bin/env python3
"""부장 참모 — 브라우저 검증 + 스크린샷"""
import json, os, pathlib, threading, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent   # work/bujang-pwa
SHOTS = ROOT.parent / "bujang-shots"
SHOTS.mkdir(exist_ok=True)
PORT = 8765
ORIGIN = f"http://127.0.0.1:{PORT}"

errors = []
results = []

def check(name, cond, detail=""):
    results.append({"name": name, "ok": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name + (("  — " + str(detail)) if detail and not cond else ""))

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

def serve():
    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

srv = serve()
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 950}, device_scale_factor=2,
                              permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error",) else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("response", lambda r: errors.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    page.goto(ORIGIN + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(400)

    # --- 기본 렌더 ---------------------------------------------------------
    check("탭 4개 + 설정 존재", page.locator(".railnav button").count() >= 5, page.locator(".railnav button").count())
    check("데스크 hold 문구 4개", page.locator("#holdList .holdrow").count() == 4)
    check("데스크 체크리스트 두 벌", page.locator("#ck-am .check").count() == 5 and page.locator("#ck-pm .check").count() == 9)
    check("즉답 보류 카드 제목", page.get_by_text("말하기 전 3문").first.is_visible())

    # --- 트래커: 추가 → 완료 → 새로고침 유지 -------------------------------
    page.click('[data-act="item-new"]')
    page.fill("#ifT", "6반 학부모 민원 답변 정리")
    page.select_option("#ifCat", "dolbal")
    page.fill("#ifWho", "나")
    page.fill("#ifMemo", "퇴근 전 전화")
    page.click('[data-act="item-save"]')
    page.wait_for_timeout(250)
    check("사안 추가됨", page.locator("#trackList .item").count() == 1)
    check("사안 분류 표시", "돌발" in page.inner_text("#trackList"))
    page.check('#trackList input.icheck')
    page.wait_for_timeout(200)
    check("완료 처리됨", "done" in page.locator("#trackList .item").first.get_attribute("class"))
    check("미결 통계 0", page.inner_text("#deskStats .stat b").strip() == "0")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(300)
    page.click('[data-act="tfilter"][data-f="all"]')
    page.wait_for_timeout(150)
    check("새로고침 후에도 사안 유지", page.locator("#trackList .item").count() == 1)

    # --- 체크리스트 저장 --------------------------------------------------
    page.check('#ck-am .check input >> nth=0')
    page.wait_for_timeout(150)
    check("체크 진행 pill 갱신", page.inner_text("#ck-am .ckhead .pill").startswith("1 / 5"))
    bar = page.evaluate("(() => { const p = document.querySelector('#ck-am .progress'); const i = p.querySelector('i'); return i.getBoundingClientRect().width / p.getBoundingClientRect().width; })()")
    check("체크 진행바 비율", 0.15 < bar < 0.25, round(bar, 3))

    # --- 데스크 스크린샷 --------------------------------------------------
    page.screenshot(path=str(SHOTS / "desk.png"))
    page.screenshot(path=str(SHOTS / "desk-full.png"), full_page=True)

    # --- 플레이북 ---------------------------------------------------------
    page.click('[data-act="tab"][data-tab="playbook"]')
    page.wait_for_timeout(250)
    check("플레이북 카드 29개", page.locator("#pbList .pb-card").count() == 29, page.locator("#pbList .pb-card").count())
    check("규정 우선 배지 존재", page.locator("#pbList .badge-rule").count() >= 4)
    page.fill("#pbQ", "학폭")
    page.wait_for_timeout(250)
    check("검색 필터 동작(학폭)", page.locator("#pbList .pb-card").count() >= 1 and page.locator("#pbList .pb-card").count() < 10,
          page.locator("#pbList .pb-card").count())
    page.fill("#pbQ", "거절")
    page.wait_for_timeout(250)
    check("검색 필터 동작(거절)", 1 <= page.locator("#pbList .pb-card").count() < 10, page.locator("#pbList .pb-card").count())
    page.fill("#pbQ", "")
    page.click('[data-act="pbcat"][data-c="minde"]')
    page.wait_for_timeout(200)
    check("분류 필터 동작", page.locator("#pbList .pb-card").count() == 5, page.locator("#pbList .pb-card").count())
    page.click('[data-act="pbcat"][data-c="all"]')
    page.wait_for_timeout(200)
    page.screenshot(path=str(SHOTS / "playbook.png"))

    # 상세 + 복사 + 사례 노트
    page.locator('[data-act="open-pb"][data-id="p01"]').click()
    page.wait_for_timeout(300)
    check("상세 판단기준 표시", page.locator(".sheet .crit").is_visible())
    check("상세 실수 3개", page.locator(".sheet .dont li").count() == 3)
    check("상세 문구 3개", page.locator(".sheet .msg").count() == 3)
    page.locator('.sheet [data-act="copy-msg"]').first.click()
    page.wait_for_timeout(300)
    clip = page.evaluate("navigator.clipboard.readText()")
    check("문구 복사 → 클립board", "말씀 잘 들었습니다" in clip, clip[:60])
    page.fill("#noteInput", "6반 민원 — 시점 약속 지키니 정리됨")
    page.click('[data-act="note-save"]')
    page.wait_for_timeout(300)
    check("사례 노트 저장", page.locator(".sheet .note-item").count() == 1)
    page.screenshot(path=str(SHOTS / "playbook-detail.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    check("시트 닫힘", page.locator("#backdrop").count() == 0)

    # --- 회의 -------------------------------------------------------------
    page.click('[data-act="tab"][data-tab="meeting"]')
    page.wait_for_timeout(250)
    page.fill("#mName", "11월 학년 협의회 결과")
    page.fill('#mRows [data-act="mrow-t"]', "5학년 체험학습 11/28 실시")
    page.fill('#mRows [data-act="mrow-who"]', "나")
    page.fill('#mRows [data-act="mrow-due"]', "2026-11-21")
    page.click('[data-act="mrow-add"]')
    page.wait_for_timeout(150)
    page.fill('#mRows [data-act="mrow-t"] >> nth=1', "운동회 종목 — 예산 확인 후 결정")
    page.select_option('#mRows [data-act="mrow-k"] >> nth=1', "보류")
    page.wait_for_timeout(200)
    page.click('[data-act="m-gen"]')
    page.wait_for_timeout(200)
    preview = page.input_value("#mPreview")
    check("공지 생성 — 확정 포함", "체험학습" in preview and "■ 확정" in preview, preview[:80])
    check("공지 생성 — 보류 포함", "■ 보류" in preview and "예산" in preview)
    check("공지 생성 — 담당/기한", "담당 나" in preview and "11/21" in preview)
    page.locator('[data-act="m-copy"]').click()
    page.wait_for_timeout(250)
    check("공지 복사", "학년 협의회" in page.evaluate("navigator.clipboard.readText()"))
    page.click('[data-act="m-save"]')
    page.wait_for_timeout(250)
    check("회의록 저장", page.locator("#mLog .item").count() == 1)
    check("로드맵 8단계", page.locator("#roadmap .rm").count() == 8)
    check("업무 영역 10개", page.locator("#areas .area").count() == 10)
    page.locator("#areas .area summary").first.click()
    page.wait_for_timeout(150)
    page.locator('#areas [data-act="area-st"][data-st="doing"]').first.click()
    page.wait_for_timeout(200)
    check("영역 상태 변경", page.locator("#areas .area summary .pill.due").count() >= 1)
    page.screenshot(path=str(SHOTS / "meeting.png"))

    # --- 교육과정 ---------------------------------------------------------
    page.click('[data-act="tab"][data-tab="curric"]')
    page.wait_for_timeout(250)
    steps = page.locator("#curSteps .curstep")
    check("교육과정 단계 9장(1~8 + !)", steps.count() == 9, steps.count())
    labels = [steps.nth(i).get_attribute("data-step") for i in range(steps.count())]
    check("! 카드가 3단계 바로 뒤", labels == ["1", "2", "3", "!", "4", "5", "6", "7", "8"], labels)
    check("! 카드 강조", "is-bang" in steps.nth(3).get_attribute("class"))
    check("! 문구 확인", "학년군 부장과 논의" in steps.nth(3).inner_text())
    check("범교과 51시수 표기", "관련지도영역 1·2·3" in page.inner_text("#curSteps") or "51시수" in page.inner_text("#curSteps"))
    check("핵심 원칙 4개", page.locator("#curPrinciples .card").count() == 4)
    check("동학년 전달 7개", page.locator("#curHandoff .check").count() == 7)
    before = page.inner_text("#curSummary .cur-stat b").split("/")[0].strip()
    steps.nth(0).evaluate("d => { d.open = true }")
    page.wait_for_timeout(150)
    steps.nth(0).locator('input[type=checkbox]').first.check()
    page.wait_for_timeout(250)
    after = page.inner_text("#curSummary .cur-stat b").split("/")[0].strip()
    check("체크 시 진행률 증가", int(after) == int(before) + 1, f"{before}->{after}")
    page.click('#curSteps .curstep[data-step="!"] summary')
    page.wait_for_timeout(150)
    page.screenshot(path=str(SHOTS / "curriculum.png"))

    # 시트 링크 저장
    page.fill("#curSheetUrl", "https://docs.google.com/spreadsheets/d/example/edit")
    page.click('[data-act="cur-sheet-save"]')
    page.wait_for_timeout(200)
    check("시트 링크 저장", "example" in page.inner_text("#curSheetSaved"))
    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(200)
    check("활동 시트 링크 ≠ 동기화 주소", page.input_value("#sUrl") == "", page.input_value("#sUrl"))

    # --- 설정 / 스냅샷 ----------------------------------------------------
    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(250)
    page.click('[data-act="snap-now"]')
    page.wait_for_timeout(200)
    check("수동 스냅샷 저장", page.locator("#snapList .snap").count() >= 1)
    page.click('[data-act="tab"][data-tab="desk"]')
    page.wait_for_timeout(150)
    page.click('[data-act="item-new"]')
    page.fill("#ifT", "되돌리기 확인용")
    page.click('[data-act="item-save"]')
    page.wait_for_timeout(250)
    n_before = page.locator("#trackList .item").count()
    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(200)
    page.locator('[data-act="snap-restore"]').first.click()
    page.wait_for_timeout(200)
    page.click('[data-act="snap-do"]')
    page.wait_for_timeout(400)
    page.click('[data-act="tab"][data-tab="desk"]')
    page.wait_for_timeout(200)
    page.click('[data-act="tfilter"][data-f="all"]')
    page.wait_for_timeout(150)
    check("스냅샷 되돌리기", page.locator("#trackList .item").count() == n_before - 1,
          f"{n_before} -> {page.locator('#trackList .item').count()}")
    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(200)
    page.screenshot(path=str(SHOTS / "settings.png"))

    # --- 모바일 -----------------------------------------------------------
    m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                            has_touch=True, permissions=["clipboard-read", "clipboard-write"])
    mp = m.new_page()
    mp.on("pageerror", lambda e: errors.append(f"mobile pageerror: {e}"))
    mp.goto(ORIGIN + "/index.html", wait_until="networkidle")
    mp.wait_for_timeout(400)
    check("모바일 하단 내비 5개", mp.locator(".bottomnav button").count() == 5)
    check("모바일 레일 숨김", not mp.locator(".rail").is_visible())
    # 가로 스크롤 없음
    w = mp.evaluate("document.documentElement.scrollWidth")
    check("모바일 가로 넘침 없음", w <= 392, w)
    mp.screenshot(path=str(SHOTS / "mobile-desk.png"))
    mp.click('.bottomnav [data-tab="playbook"]')
    mp.wait_for_timeout(300)
    mp.locator('[data-act="open-pb"][data-id="p21"]').click()
    mp.wait_for_timeout(300)
    mp.screenshot(path=str(SHOTS / "mobile-playbook.png"))
    mp.keyboard.press("Escape")
    mp.click('.bottomnav [data-tab="curric"]')
    mp.wait_for_timeout(300)
    mp.screenshot(path=str(SHOTS / "mobile-curriculum.png"))
    m.close()

    browser.close()
srv.shutdown()

print("\n== console/page errors ==")
for e in errors:
    print(" -", e)
print(json.dumps({"passed": sum(1 for r in results if r["ok"]), "failed": [r for r in results if not r["ok"]], "total": len(results)}, ensure_ascii=False, indent=1))
