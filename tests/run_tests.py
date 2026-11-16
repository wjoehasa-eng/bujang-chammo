#!/usr/bin/env python3
"""부장 참모 v3 — 브라우저 검증 + 스크린샷
   교육과정 탭은 v2 렌더 결과(테스트 기준선)와 글자 단위로 비교합니다."""
import json, pathlib, threading, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent   # work/bujang-pwa
SHOTS = ROOT.parent / "bujang-shots"
SHOTS.mkdir(exist_ok=True)
BASELINE = json.loads((ROOT / "tests" / "curriculum_baseline.json").read_text(encoding="utf-8"))
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

    # ---------------------------------------------------------------- 기본
    check("탭 5개(데스크·갈등·회의·교육과정·설정)", page.locator(".railnav button").count() == 5,
          page.locator(".railnav button").count())
    check("즉답 보류 문구 4개", page.locator("#holdList .holdrow").count() == 4)
    brake = page.inner_text(".brake")
    check("10초 멈춤 3문(사실·권한·시점)", all(k in brake for k in ["사실인가", "내가 정할 일인가", "지금 말할 일인가"]), brake[:120])
    check("하루 마감 체크 4개로 축소", page.locator("#ck-day .check").count() == 4,
          page.locator("#ck-day .check").count())

    # ---------------------------------------------------------------- 결정 전 4문
    check("리허설 질문 4개", page.locator("#rehList .reh-q").count() == 4)
    check("리허설 선택지 12개(문당 3)", page.locator("#rehList .reh-opt").count() == 12)
    check("답 전에는 판단 유보", "4문에 답하면" in page.inner_text("#rehVerdict"))
    check("답 전에는 트래커 추가 버튼 없음", page.locator('[data-act="reh-add"]').count() == 0)

    page.fill("#rehTitle", "12월 학년 행사를 18일 오전으로 확정")
    for q, v in [("back", "yes"), ("who", "no"), ("rule", "ok"), ("worst", "yes")]:
        page.click(f'[data-act="reh-ans"][data-q="{q}"][data-v="{v}"]')
    page.wait_for_timeout(250)
    txt = page.inner_text("#rehVerdict")
    check("4문 통과 → 혼자 결정 가능", "혼자 결정 가능" in txt and "lv0" not in txt, txt[:90])
    check("통과 시 다음 행동 제시", "다음 행동" in txt and "메신저" in txt)
    check("통과 시 카운터 4 / 4", page.inner_text("#rehCount").strip() == "4 / 4", page.inner_text("#rehCount"))
    page.screenshot(path=str(SHOTS / "desk-rehearsal-ok.png"))

    # 규정 미확인 → 교감·담당 확인 필요
    page.click('[data-act="reh-ans"][data-q="rule"][data-v="check"]')
    page.wait_for_timeout(200)
    txt = page.inner_text("#rehVerdict")
    check("규정 미확인 → 교감·담당 확인 필요", "교감·담당 확인 필요" in txt and "규정" in txt, txt[:140])
    check("걸린 이유 설명", "걸린 것" in txt and "확인" in txt)
    page.screenshot(path=str(SHOTS / "desk-rehearsal-block.png"))

    # 못 들은 사람 → 동학년 협의 (규정을 다시 통과시킨 뒤)
    page.click('[data-act="reh-ans"][data-q="rule"][data-v="ok"]')
    page.click('[data-act="reh-ans"][data-q="who"][data-v="some"]')
    page.wait_for_timeout(200)
    txt = page.inner_text("#rehVerdict")
    check("못 들은 사람 있음 → 동학년 협의 먼저", "동학년 협의 먼저" in txt and "전담" in txt, txt[:140])

    # 되돌릴 수 없음 + 부분 설명 → 교감 확인
    page.click('[data-act="reh-ans"][data-q="who"][data-v="no"]')
    page.click('[data-act="reh-ans"][data-q="back"][data-v="no"]')
    page.click('[data-act="reh-ans"][data-q="worst"][data-v="part"]')
    page.wait_for_timeout(200)
    txt = page.inner_text("#rehVerdict")
    check("되돌릴 수 없음+부족한 근거 → 교감 확인", "교감·담당 확인 필요" in txt, txt[:140])

    # 요약 복사 → 미결 추가
    page.locator('[data-act="reh-copy"]').click()
    page.wait_for_timeout(300)
    clip = page.evaluate("navigator.clipboard.readText()")
    check("리허설 요약 복사", "12월 학년 행사" in clip and "교감·담당 확인 필요" in clip, clip[:80])

    page.locator('[data-act="reh-add"]').click()
    page.wait_for_timeout(300)
    check("미결 트래커에 추가됨", page.locator("#trackList .item").count() == 1)
    check("추가된 사안에 판단 결과 기록", "교감·담당 확인 필요" in page.inner_text("#trackList"),
          page.inner_text("#trackList")[:120])
    page.locator('[data-act="reh-reset"]').click()
    page.wait_for_timeout(200)
    check("리허설 새로 하기", page.input_value("#rehTitle") == "" and "4문에 답하면" in page.inner_text("#rehVerdict"))

    # ---------------------------------------------------------------- 트래커
    page.click('[data-act="item-new"]')
    page.fill("#ifT", "6반 학부모 민원 답변 정리")
    page.select_option("#ifCat", "minwon")
    page.fill("#ifWho", "나")
    page.fill("#ifMemo", "퇴근 전 전화")
    page.click('[data-act="item-save"]')
    page.wait_for_timeout(250)
    check("사안 추가", page.locator("#trackList .item").count() == 2)
    check("사안 분류 표시", "학부모" in page.inner_text("#trackList"))
    item_id = page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).items[0].id")
    page.check(f'[data-act="item-done"][data-id="{item_id}"]')
    page.wait_for_timeout(300)
    check("완료 처리", page.locator("#trackList .item.done").count() == 1,
          f"done={page.locator('#trackList .item.done').count()} / {page.inner_text('#trackList')[:80]}")
    check("완료한 사안만 줄 그음", "6반 학부모" in page.inner_text("#trackList .item.done"),
          page.inner_text("#trackList .item.done")[:60])
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click('[data-act="tfilter"][data-f="all"]')
    page.wait_for_timeout(150)
    check("새로고침 후 유지", page.locator("#trackList .item").count() == 2)

    # 체크 저장
    page.check('#ck-day .check input >> nth=0')
    page.wait_for_timeout(150)
    check("하루 체크 진행 표시", page.inner_text("#ck-day .ckhead .pill").startswith("1 / 4"))
    page.screenshot(path=str(SHOTS / "desk.png"))
    page.screenshot(path=str(SHOTS / "desk-full.png"), full_page=True)

    # ---------------------------------------------------------------- 갈등·실전
    page.click('[data-act="tab"][data-tab="playbook"]')
    page.wait_for_timeout(250)
    check("상황 카드 18개", page.locator("#pbList .pb-card").count() == 18, page.locator("#pbList .pb-card").count())
    check("모든 카드에 권한 경계 배지", page.locator("#pbList .pb-card .auth-badge").count() == 18,
          page.locator("#pbList .pb-card .auth-badge").count())
    for label, cnt in [("self", 2), ("team", 7), ("admin", 9)]:
        page.click(f'[data-act="pbauth"][data-a="{label}"]')
        page.wait_for_timeout(200)
        check(f"권한 필터 {label} = {cnt}", page.locator("#pbList .pb-card").count() == cnt,
              page.locator("#pbList .pb-card").count())
    page.click('[data-act="pbauth"][data-a="all"]')
    page.wait_for_timeout(150)
    page.click('[data-act="pbcat"][data-c="minwon"]')
    page.wait_for_timeout(200)
    check("분류 필터(학부모·민원) 4개", page.locator("#pbList .pb-card").count() == 4,
          page.locator("#pbList .pb-card").count())
    page.click('[data-act="pbcat"][data-c="all"]')
    page.wait_for_timeout(150)

    for q, title in [("분장", "맡은 분장"), ("학폭", "학교폭력"), ("결재", "결재를 받아야"), ("하이클래스", "개별 문자")]:
        page.fill("#pbQ", q)
        page.wait_for_timeout(220)
        n = page.locator("#pbList .pb-card").count()
        first = page.locator("#pbList .pb-card .tt").first.inner_text() if n else ""
        check(f"검색 '{q}' → 첫 카드가 관련", 0 < n <= 4 and title in first, f"{n}개 / 첫 카드: {first}")
    page.fill("#pbQ", "")
    page.wait_for_timeout(200)
    page.screenshot(path=str(SHOTS / "playbook.png"))

    page.locator('[data-act="open-pb"][data-id="g01"]').click()
    page.wait_for_timeout(300)
    sheet = page.inner_text(".sheet")
    check("상세: 권한 경계 블록", "권한 경계" in sheet and "내가 정할 수 있는 것" in sheet and "넘겨야 하는 선" in sheet)
    check("상세: 판단 기준", page.locator(".sheet .crit").is_visible())
    check("상세: 하지 않을 것 3개", page.locator(".sheet .dont li").count() == 3)
    check("상세: 문구 3톤", page.locator(".sheet .msg").count() == 3)
    page.locator('.sheet [data-act="copy-msg"]').first.click()
    page.wait_for_timeout(300)
    check("문구 복사", "분장" in page.evaluate("navigator.clipboard.readText()"))
    page.fill("#noteInput", "분장 교환으로 정리됨")
    page.click('[data-act="note-save"]')
    page.wait_for_timeout(300)
    check("내 사례 노트 저장", page.locator(".sheet .note-item").count() == 1)
    page.screenshot(path=str(SHOTS / "playbook-detail.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    check("시트 닫힘", page.locator("#backdrop").count() == 0)
    check("카드에 사례 수 표시", "내 사례 1" in page.inner_text('[data-act="open-pb"][data-id="g01"]'))

    # ---------------------------------------------------------------- 회의
    page.click('[data-act="tab"][data-tab="meeting"]')
    page.wait_for_timeout(300)
    check("회의 3단계 카드", page.locator("#meetSteps .s").count() == 3)
    check("회의 전 모드가 기본", page.locator("#preFields").is_visible() and not page.locator("#postFields").is_visible())

    page.fill("#mName", "11월 학년 협의회")
    page.fill('#mAgenda [data-act="ag-t"] >> nth=0', "12월 학년 행사 일정")
    page.fill('#mAgenda [data-act="ag-d"] >> nth=0', "12/18 오전, 운동장")
    page.click('[data-act="ag-add"]')
    page.wait_for_timeout(150)
    page.fill('#mAgenda [data-act="ag-t"] >> nth=1', "학년 공통 과제")
    page.fill('#mAgenda [data-act="ag-d"] >> nth=1', "주 1회, 수요일")
    page.fill("#mFlex", "행사 순서\n준비물 분담")
    page.fill("#mFixed", "교육과정 시수\n예산 한도")
    page.select_option("#mDecide", "다수결")
    page.wait_for_timeout(150)
    page.click('[data-act="m-gen"]')
    page.wait_for_timeout(200)
    pre = page.input_value("#mPreview")
    check("안내문 — 안건과 초안", "12월 학년 행사 일정" in pre and "12/18 오전" in pre, pre[:80])
    check("안내문 — 바꿀 수 있는 것", "바꿀 수 있는 것" in pre and "준비물 분담" in pre)
    check("안내문 — 못 바꾸는 것", "바꿀 수 없는 것" in pre and "교육과정 시수" in pre)
    check("안내문 — 결정 방식", "다수결" in pre and "소수 의견" in pre)
    check("안내문 — 회의 전 요청", "회의 전까지" in pre)
    page.locator('[data-act="m-copy"]').click()
    page.wait_for_timeout(250)
    check("안내문 복사", "학년 협의회" in page.evaluate("navigator.clipboard.readText()"))
    page.screenshot(path=str(SHOTS / "meeting-before.png"))

    page.click('[data-act="m-save"]')
    page.wait_for_timeout(250)
    check("안내문 저장", page.locator("#mLog .item").count() == 1 and "안내문" in page.inner_text("#mLog"))

    page.click('[data-act="m-mode"][data-mode="after"]')
    page.wait_for_timeout(250)
    check("회의 후 모드 전환", page.locator("#postFields").is_visible() and not page.locator("#preFields").is_visible())
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
    post = page.input_value("#mPreview")
    check("공지 — 확정", "체험학습" in post and "■ 확정" in post, post[:80])
    check("공지 — 보류", "■ 보류" in post and "예산" in post)
    check("공지 — 담당·기한", "담당 나" in post and "11/21" in post)
    page.click('[data-act="m-save"]')
    page.wait_for_timeout(250)
    check("결과 공지 저장", page.locator("#mLog .item").count() == 2 and "결과" in page.inner_text("#mLog"))
    page.screenshot(path=str(SHOTS / "meeting-after.png"))

    check("마일스톤 12개", page.locator("#roadmap .rm").count() == 12, page.locator("#roadmap .rm").count())
    check("마일스톤마다 위험 한 줄", page.locator("#roadmap .rm .risk").count() == 12)
    check("10대 업무 일반론 제거", page.locator("#areas").count() == 0)

    page.fill("#workUrl", "https://docs.google.com/spreadsheets/d/work-sheet/edit")
    page.click('[data-act="work-save"]')
    page.wait_for_timeout(250)
    check("업무 시트 연결", "work-sheet" in page.inner_text("#workSaved") and page.locator("#workSaved a").count() == 1)
    check("업무 시트 ≠ 동기화 주소", page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).sheetUrl") == "")

    page.click('[data-act="tab"][data-tab="desk"]')
    page.wait_for_timeout(200)
    page.click('[data-act="tab"][data-tab="meeting"]')
    page.wait_for_timeout(250)
    check("회의 초안 유지", page.input_value("#mName") == "11월 학년 협의회" and page.input_value("#mPreview").strip() != "")

    # ---------------------------------------------------------------- 교육과정 (v2와 동일해야 함)
    page.click('[data-act="tab"][data-tab="curric"]')
    page.wait_for_timeout(300)
    cur = page.evaluate("""() => ({
      steps: JSON.stringify(CUR_STEPS), principles: JSON.stringify(CUR_PRINCIPLES),
      handoff: JSON.stringify(CUR_HANDOFF), finish: JSON.stringify(CUR_FINISH),
      html: document.querySelector('#view-curric').innerHTML
    })""")
    for key in ["steps", "principles", "handoff", "finish"]:
        check(f"교육과정 데이터 무변경 ({key})", cur[key] == BASELINE[key],
              "내용이 달라졌습니다" if cur[key] != BASELINE[key] else "")
    # 렌더 결과는 상태 영향이 없도록 새 컨텍스트에서 비교합니다
    fresh = browser.new_context(viewport={"width": 1440, "height": 950})
    fp2 = fresh.new_page()
    fp2.goto(ORIGIN + "/index.html", wait_until="networkidle")
    fp2.wait_for_timeout(300)
    fp2.click('[data-act="tab"][data-tab="curric"]')
    fp2.wait_for_timeout(350)
    fresh_html = fp2.evaluate("document.querySelector('#view-curric').innerHTML")
    fresh.close()
    check("교육과정 렌더 결과 무변경(v2 기준선)", fresh_html == BASELINE["html"],
          f"{len(fresh_html)} vs {len(BASELINE['html'])}")
    steps = page.locator("#curSteps .curstep")
    check("교육과정 단계 9장(1~8 + !)", steps.count() == 9, steps.count())
    labels = [steps.nth(i).get_attribute("data-step") for i in range(steps.count())]
    check("! 카드가 3단계 바로 뒤", labels == ["1", "2", "3", "!", "4", "5", "6", "7", "8"], labels)
    check("! 카드 강조·문구", "is-bang" in steps.nth(3).get_attribute("class") and "학년군 부장과 논의" in steps.nth(3).inner_text())
    check("동학년 전달 7개", page.locator("#curHandoff .check").count() == 7)
    before = page.inner_text("#curSummary .cur-stat b").split("/")[0].strip()
    steps.nth(0).evaluate("d => { d.open = true }")
    page.wait_for_timeout(150)
    steps.nth(0).locator('input[type=checkbox]').first.check()
    page.wait_for_timeout(250)
    after = page.inner_text("#curSummary .cur-stat b").split("/")[0].strip()
    check("교육과정 체크 동작", int(after) == int(before) + 1, f"{before}->{after}")
    page.fill("#curSheetUrl", "https://docs.google.com/spreadsheets/d/cur-sheet/edit")
    page.click('[data-act="cur-sheet-save"]')
    page.wait_for_timeout(200)
    check("활동 시트 링크 저장", "cur-sheet" in page.inner_text("#curSheetSaved"))
    check("활동 시트 링크는 업무 시트와 분리", page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).workUrl").find("work-sheet") > 0)
    page.screenshot(path=str(SHOTS / "curriculum.png"))

    # ---------------------------------------------------------------- 설정
    page.click('[data-act="tab"][data-tab="settings"]')
    page.wait_for_timeout(250)
    check("설정 — 동기화 주소 분리", page.input_value("#sUrl") == "", page.input_value("#sUrl"))
    page.click('[data-act="snap-now"]')
    page.wait_for_timeout(200)
    check("수동 스냅샷", page.locator("#snapList .snap").count() >= 1)
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

    # ---------------------------------------------------------------- 모바일
    m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                            has_touch=True, permissions=["clipboard-read", "clipboard-write"])
    mp = m.new_page()
    mp.on("pageerror", lambda e: errors.append(f"mobile pageerror: {e}"))
    mp.goto(ORIGIN + "/index.html", wait_until="networkidle")
    mp.wait_for_timeout(400)
    check("모바일 하단 내비 5개", mp.locator(".bottomnav button").count() == 5)
    check("모바일 레일 숨김", not mp.locator(".rail").is_visible())
    w = mp.evaluate("document.documentElement.scrollWidth")
    check("모바일 가로 넘침 없음(데스크)", w <= 392, w)
    mp.click('[data-act="reh-ans"][data-q="back"][data-v="no"]')
    mp.wait_for_timeout(200)
    w = mp.evaluate("document.documentElement.scrollWidth")
    check("모바일 가로 넘침 없음(리허설)", w <= 392, w)
    mp.screenshot(path=str(SHOTS / "mobile-desk.png"))
    mp.click('.bottomnav [data-tab="playbook"]')
    mp.wait_for_timeout(300)
    w = mp.evaluate("document.documentElement.scrollWidth")
    check("모바일 가로 넘침 없음(카드)", w <= 392, w)
    mp.locator('[data-act="open-pb"][data-id="s02"]').click()
    mp.wait_for_timeout(300)
    mp.screenshot(path=str(SHOTS / "mobile-playbook.png"))
    mp.keyboard.press("Escape")
    mp.click('.bottomnav [data-tab="meeting"]')
    mp.wait_for_timeout(300)
    w = mp.evaluate("document.documentElement.scrollWidth")
    check("모바일 가로 넘침 없음(회의)", w <= 392, w)
    mp.screenshot(path=str(SHOTS / "mobile-meeting.png"))
    mp.click('.bottomnav [data-tab="curric"]')
    mp.wait_for_timeout(300)
    mp.screenshot(path=str(SHOTS / "mobile-curriculum.png"))
    m.close()

    # ---------------------------------------------------------------- 단독 HTML(file://)
    f = browser.new_context(viewport={"width": 1280, "height": 900})
    fp = f.new_page()
    ferrs = []
    fp.on("pageerror", lambda e: ferrs.append(str(e)))
    fp.goto("file:///workspace/bujang_chammo.html")
    fp.wait_for_timeout(600)
    check("단독 HTML 실행", fp.locator("#rehList .reh-q").count() == 4 and not ferrs, ferrs)
    f.close()

    ctx.close()
    browser.close()
srv.shutdown()

print("\n== console/page errors ==")
for e in errors:
    print(" -", e)
print(json.dumps({"passed": sum(1 for r in results if r["ok"]), "total": len(results),
                  "failed": [r for r in results if not r["ok"]]}, ensure_ascii=False, indent=1))
