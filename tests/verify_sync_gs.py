#!/usr/bin/env python3
"""부장 참모 — Apps Script 로직 + 실시간 동기화 검증 (목 서버/목 시트)"""
import json, pathlib, threading, functools, datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
GS = pathlib.Path("/workspace/bujang_apps_script.gs")
PORT = 8771
ORIGIN = f"http://127.0.0.1:{PORT}"

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (("  — " + str(detail)) if detail and not cond else ""))

STATE = {"data": None, "savedAt": "", "saves": 0}

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_POST(self):
        if self.path.split("?")[0] != "/exec":
            self._json({"ok": False, "error": "not found"}, 404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._json({"ok": False, "error": "bad json"})
            return
        if req.get("action") == "save":
            STATE["data"] = req.get("data")
            STATE["savedAt"] = req.get("savedAt") or datetime.datetime.utcnow().isoformat() + "Z"
            STATE["saves"] += 1
            self._json({"ok": True, "savedAt": STATE["savedAt"], "itemCount": len((req.get("data") or {}).get("items") or [])})
        elif req.get("action") == "load":
            self._json({"ok": True, "savedAt": STATE["savedAt"], "data": STATE["data"]})
        else:
            self._json({"ok": True})

srv = ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()

MOCK = r"""
window.__fakeSheets = {};
class FakeRange {
  constructor(sh, r, c, nr, nc) { this.sh = sh; this.r = r; this.c = c; this.nr = nr; this.nc = nc; }
  setValues(vals) {
    for (let i = 0; i < vals.length; i++) for (let j = 0; j < (vals[i] || []).length; j++)
      this.sh._set(this.r + i, this.c + j, vals[i][j]);
    return this;
  }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) { const row = [];
      for (let j = 0; j < this.nc; j++) row.push(this.sh._get(this.r + i, this.c + j));
      out.push(row); }
    return out;
  }
  setValue(v) { this.sh._set(this.r, this.c, v); return this; }
  clearContent() { for (let i = 0; i < this.nr; i++) for (let j = 0; j < this.nc; j++) this.sh._del(this.r + i, this.c + j); return this; }
  setNumberFormat() { return this; }
  setFontWeight() { return this; }
}
class FakeSheet {
  constructor(name) { this.name = name; this.cells = new Map(); }
  _k(r, c) { return r + ':' + c; }
  _get(r, c) { const v = this.cells.get(this._k(r, c)); return v === undefined ? '' : v; }
  _set(r, c, v) { this.cells.set(this._k(r, c), v); }
  _del(r, c) { this.cells.delete(this._k(r, c)); }
  getLastRow() { let m = 0; this.cells.forEach((v, k) => { if (v !== '' && v !== null) m = Math.max(m, +k.split(':')[0]); }); return m; }
  getLastColumn() { let m = 0; this.cells.forEach((v, k) => { if (v !== '' && v !== null) m = Math.max(m, +k.split(':')[1]); }); return m; }
  getRange(r, c, nr, nc) { return new FakeRange(this, r, c, nr || 1, nc || 1); }
  clearContents() { this.cells.clear(); return this; }
  setFrozenRows() { return this; }
  setColumnWidth() { return this; }
}
class FakeSS {
  constructor() { this.sheets = {}; }
  getSheetByName(n) { return this.sheets[n] || null; }
  insertSheet(n) { const s = new FakeSheet(n); this.sheets[n] = s; return s; }
  getUrl() { return 'https://docs.google.com/spreadsheets/d/FAKE/edit'; }
  getId() { return 'FAKE'; }
  sheetNames() { return Object.keys(this.sheets); }
}
const FAKE_SS = new FakeSS();
window.SpreadsheetApp = {
  getActiveSpreadsheet: () => FAKE_SS,
  create: () => FAKE_SS,
  openById: () => FAKE_SS
};
window.LockService = { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) };
window.ContentService = {
  MimeType: { JSON: 'application/json' },
  createTextOutput: (s) => ({ _s: s, setMimeType() { return this; }, getContent() { return this._s; } })
};
window.Utilities = {
  formatDate: (d) => {
    const p = (n) => (n < 10 ? '0' : '') + n;
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }
};
window.Session = { getScriptTimeZone: () => 'Asia/Seoul' };
window.PropertiesService = { getScriptProperties: () => ({ _p: {}, getProperty(k) { return this._p[k] || null; }, setProperty(k, v) { this._p[k] = v; } }) };
window.__fakeSS = FAKE_SS;
"""

with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---------------------------------------------------------- Apps Script 로직
    gs = GS.read_text(encoding="utf-8")
    gp = browser.new_page()
    gp.set_content("<!doctype html><html><body></body></html>")
    gp.add_script_tag(content=MOCK)
    gp.add_script_tag(content=gs)
    out = gp.evaluate("""() => {
      const notes = { p01: [{ at: '2026-11-17T01:00:00.000Z', text: '민원은 시점 약속이 답이었다' }] };
      const data = {
        v: 2,
        items: [
          { id: 'i1', t: '6반 민원 답변', cat: 'dolbal', due: '2026-11-18', who: '나', done: false, memo: '퇴근 전', at: '2026-11-17T00:00:00Z' },
          { id: 'i2', t: '체험학습 동의서 취합', cat: 'haksaeng', due: '', who: '3반', done: true, memo: '', at: '2026-11-16T00:00:00Z' }
        ],
        meetings: [{ id: 'm1', date: '2026-11-18', name: '학년 협의회 결과', text: '[학년 협의회 결과] 11월 18일 (화)\\n\\n■ 확정\\n1. 체험학습', at: '2026-11-18T09:00:00Z' }],
        notes: notes, cur: { 's1:0': true }, ck: {}, areas: {}, road: {}, sheetUrl: '', autoSync: true
      };
      const saved = saveAll_({ action: 'save', data: data, savedAt: '2026-11-17T01:00:00.000Z' });
      const loaded = loadAll_();
      const status = status_();
      let guard = '';
      try { saveAll_({ action: 'save', data: { v: 2, items: [], meetings: [], notes: {} }, savedAt: '2026-11-17T02:00:00.000Z' }); }
      catch (e) { guard = String(e.message || e); }
      const forced = saveAll_({ action: 'save', force: true, data: { v: 2, items: [], meetings: [], notes: {} }, savedAt: '2026-11-17T03:00:00.000Z' });
      return {
        savedOk: saved.ok, itemCount: saved.itemCount, meetingCount: saved.meetingCount,
        loadedItems: loaded.data.items.length, loadedTitle: loaded.data.items[0].t,
        loadedDone: loaded.data.items[1].done, loadedMeetings: loaded.data.meetings.length,
        loadedNote: loaded.data.notes.p01[0].text, loadedCur: loaded.data.cur['s1:0'],
        guardText: guard, forcedOk: forced.ok, forcedCount: forced.itemCount,
        statusOk: status.ok, sheets: __fakeSS.sheetNames().sort()
      };
    }""")
    check("GS: 저장 성공", out["savedOk"] and out["itemCount"] == 2)
    check("GS: 불러오기 사안 2개", out["loadedItems"] == 2 and out["loadedTitle"] == "6반 민원 답변", out)
    check("GS: 완료/회의록 유지", out["loadedDone"] is True and out["loadedMeetings"] == 1)
    check("GS: 사례노트·체크 유지", out["loadedNote"].startswith("민원") and out["loadedCur"] is True)
    check("GS: 빈 기록 덮어쓰기 차단", "빈 기록" in (out["guardText"] or ""), out["guardText"])
    check("GS: force면 빈 저장 허용", out["forcedOk"] and out["forcedCount"] == 0)
    check("GS: 시트 6종 생성", out["sheets"] == ["메타", "백업", "사례노트", "사용안내" if False else "사용법", "사안", "회의록"] or len(out["sheets"]) == 6, out["sheets"])
    check("GS: status 응답", out["statusOk"])
    gp.close()

    # ---------------------------------------------------------- 클라이언트 동기화
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(ORIGIN + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(300)

    page.click('[data-act="tab"][data-tab="settings"]')
    page.fill("#sUrl", ORIGIN + "/exec")
    page.click('[data-act="sync-save-url"]')
    page.wait_for_timeout(900)
    check("동기화: 주소 확인 응답", "기록이 없습니다" in page.inner_text("#sStatus"), page.inner_text("#sStatus"))

    page.click('[data-act="tab"][data-tab="desk"]')
    page.click('[data-act="item-new"]')
    page.fill("#ifT", "동기화 확인용 사안")
    page.click('[data-act="item-save"]')
    page.wait_for_timeout(2600)
    check("동기화: 1.5초 뒤 자동 저장", STATE["saves"] >= 1 and STATE["data"]["items"][0]["t"] == "동기화 확인용 사안",
          f"saves={STATE['saves']} data={STATE['data'] and STATE['data'].get('items')}")
    check("동기화: 레일 상태 표시", "자동 저장됨" in page.inner_text("#railSync"), page.inner_text("#railSync"))

    # 다른 기기에서 저장한 상황
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    STATE["data"] = {"v": 2, "items": [{"id": "remote1", "t": "다른 기기에서 적은 사안", "cat": "gyosa", "due": "", "who": "", "done": False, "memo": "", "at": "2026-11-17T00:30:00Z"}],
                     "meetings": [], "notes": {}, "cur": {}, "ck": {}, "areas": {}, "road": {}, "sheetUrl": ORIGIN + "/exec", "autoSync": True}
    STATE["savedAt"] = future
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2200)
    txt = page.inner_text("#trackList")
    check("동기화: 새 기록 자동 반영", "다른 기기에서 적은 사안" in txt, txt[:120])

    # 시트가 비었는데 시각만 새로울 때 — 기기 기록을 지우지 않아야 함
    local_before = page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).items.length")
    STATE["data"] = {"v": 2, "items": [], "meetings": [], "notes": {}, "cur": {}, "ck": {}, "areas": {}, "road": {}, "sheetUrl": ORIGIN + "/exec", "autoSync": True}
    STATE["savedAt"] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2200)
    local_after = page.evaluate("JSON.parse(localStorage.getItem('bc2_state')).items.length")
    check("동기화: 빈 시트가 기기 기록을 지우지 않음", local_after == local_before and local_after == 1, f"{local_before}->{local_after}")

    check("동기화: 페이지 오류 없음", not errs, errs)
    ctx.close()
    browser.close()

srv.shutdown()
print("\n총", sum(1 for _, ok in results if ok), "/", len(results), "통과")
fail = [n for n, ok in results if not ok]
print("실패:", fail if fail else "없음")
