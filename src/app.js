/* 부장 참모 — 앱 로직 */
(function () {
  'use strict';

  var APP_NAME = '부장 참모';
  var LS = 'bc2_state', LS_SNAP = 'bc2_snaps', LS_THEME = 'bc2_theme';
  var URL_KEY = 'bc2_sheet_url', AUTO_KEY = 'bc2_auto_sync', LAST_KEY = 'bc2_last_sync', EDIT_KEY = 'bc2_edit_at';
  var PUSH_DELAY = 1500, PULL_GAP = 6000, SKEW = 2000;

  /* ------------------------------------------------------------------ 도우미 */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function ymd(d) { d = d || new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function parseYmd(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ''));
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function dayDiff(a, b) {
    var x = parseYmd(a), y = parseYmd(b);
    if (!x || !y) return null;
    return Math.round((x.getTime() - y.getTime()) / 86400000);
  }
  var WD = ['일', '월', '화', '수', '목', '금', '토'];
  function fmtKorean(s) {
    var d = parseYmd(s); if (!d) return s || '';
    return (d.getMonth() + 1) + '월 ' + d.getDate() + '일 (' + WD[d.getDay()] + ')';
  }
  function fmtShort(s) {
    var d = parseYmd(s); if (!d) return '';
    return (d.getMonth() + 1) + '/' + d.getDate();
  }
  function fmtStamp(iso) {
    var d = new Date(iso); if (isNaN(d)) return '';
    return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function uid(p) { return (p || 'x') + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { } }
  function tsOf(v) { var t = Date.parse(String(v || '')); return isNaN(t) ? 0 : t; }

  /* ------------------------------------------------------------------ 상태 */
  function blank() {
    return {
      v: 2, items: [], ck: {}, notes: {}, cur: {}, areas: {}, road: {},
      meetings: [], mdraft: null, sheetUrl: '', docUrl: '', autoSync: true, updatedAt: ''
    };
  }
  var S = blank();
  try {
    var raw = localStorage.getItem(LS);
    if (raw) {
      var p = JSON.parse(raw);
      if (p && typeof p === 'object') {
        Object.keys(blank()).forEach(function (k) { if (p[k] !== undefined) S[k] = p[k]; });
        if (!S.mdraft) S.mdraft = null;
        // 예전 버전에서 활동별 시트 주소를 동기화 주소로 쓰던 값 분리
        if (!S.docUrl && /docs\.google\.com|drive\.google\.com/.test(String(S.sheetUrl || ''))) {
          S.docUrl = S.sheetUrl; S.sheetUrl = '';
        }
      }
    }
  } catch (e) { }

  function persist(opts) {
    opts = opts || {};
    var today = ymd();
    var keys = Object.keys(S.ck || {});
    if (keys.length > 24) {
      keys.sort().slice(0, keys.length - 24).forEach(function (k) { delete S.ck[k]; });
    }
    if (S.items.length > 400) S.items = S.items.slice(0, 400);
    S.updatedAt = new Date().toISOString();
    lsSet(LS, JSON.stringify(S));
    if (!opts.silent) markEdit();
  }

  /* ------------------------------------------------------------------ 테마 */
  function themePref() { return lsGet(LS_THEME, 'auto'); }
  function applyTheme() {
    var t = themePref(), r = document.documentElement;
    if (t === 'light' || t === 'dark') r.setAttribute('data-theme', t);
    else r.removeAttribute('data-theme');
    $$('[data-act="theme"]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.theme === t));
    });
  }

  /* ------------------------------------------------------------------ 토스트 / 시트 */
  var toastTimer = null;
  function toast(msg) {
    var el = $('#toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('show'); }, 2000);
  }
  var lastFocus = null;
  function openSheet(html, cls) {
    closeSheet();
    lastFocus = document.activeElement;
    var b = document.createElement('div');
    b.className = 'backdrop'; b.id = 'backdrop';
    b.innerHTML = '<div class="sheet ' + (cls || '') + '" role="dialog" aria-modal="true">' + html + '</div>';
    document.body.appendChild(b);
    document.body.style.overflow = 'hidden';
    var f = b.querySelector('input:not([type=hidden]),textarea,button');
    if (f) setTimeout(function () { try { f.focus(); } catch (e) { } }, 40);
  }
  function closeSheet() {
    var b = $('#backdrop');
    if (b) b.remove();
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) { } }
  }

  /* ------------------------------------------------------------------ 복사 */
  function copyText(text, btn) {
    function ok() {
      toast('복사했습니다');
      if (btn) {
        var old = btn.innerHTML;
        btn.innerHTML = '✓ 복사됨';
        setTimeout(function () { btn.innerHTML = old; }, 1300);
      }
    }
    function fallback() {
      try {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        var good = document.execCommand('copy');
        ta.remove();
        if (good) ok(); else toast('복사하지 못했습니다. 길게 눌러 선택해 주세요.');
      } catch (e) { toast('복사하지 못했습니다. 길게 눌러 선택해 주세요.'); }
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(ok, fallback);
    } else fallback();
  }

  /* ------------------------------------------------------------------ 데스크 */
  var tFilter = 'open';
  var pendingDelete = null;
  var justDone = {};   // 방금 끝낸 일은 목록에서 바로 사라지지 않게 잠깐 남깁니다

  function dueInfo(it) {
    if (!it.due) return null;
    var d = dayDiff(it.due, ymd());
    if (d == null) return null;
    if (d < 0) return { label: 'D+' + (-d), cls: 'over', order: -1000 + d };
    if (d === 0) return { label: '오늘', cls: 'over', order: -999 };
    if (d === 1) return { label: '내일', cls: 'due', order: -998 };
    if (d <= 7) return { label: 'D-' + d, cls: 'due', order: d };
    return { label: fmtShort(it.due), cls: '', order: d };
  }
  function catName(id) { var c = CATS.filter(function (x) { return x.id === id; })[0]; return c ? c.name : '기타'; }
  function catIdx(id) { for (var i = 0; i < CATS.length; i++) if (CATS[i].id === id) return i; return 6; }

  function sortItems(arr) {
    return arr.slice().sort(function (a, b) {
      if (!!a.done !== !!b.done) return a.done ? 1 : -1;
      var da = a.due ? (dayDiff(a.due, ymd()) == null ? 900 : dayDiff(a.due, ymd())) : 900;
      var db = b.due ? (dayDiff(b.due, ymd()) == null ? 900 : dayDiff(b.due, ymd())) : 900;
      if (da !== db) return da - db;
      return (b.at || '').localeCompare(a.at || '');
    });
  }

  function deskStats() {
    var open = S.items.filter(function (i) { return !i.done; });
    var over = open.filter(function (i) { var d = dayDiff(i.due, ymd()); return d != null && d <= 0; });
    var week = open.filter(function (i) { var d = dayDiff(i.due, ymd()); return d != null && d > 0 && d <= 7; });
    return { open: open.length, over: over.length, week: week.length, done: S.items.length - open.length };
  }

  function renderDesk() {
    var now = new Date();
    var st = deskStats();
    $('#deskDate').textContent = now.getFullYear() + '년 ' + (now.getMonth() + 1) + '월 ' + now.getDate() + '일 ' + WD[now.getDay()] + '요일';

    $('#deskStats').innerHTML =
      '<div class="stat"><b>' + st.open + '</b><span>미결</span></div>' +
      '<div class="stat ' + (st.over ? 'bad' : '') + '"><b>' + st.over + '</b><span>오늘·지남</span></div>' +
      '<div class="stat ' + (st.week ? 'warn' : '') + '"><b>' + st.week + '</b><span>이번 주</span></div>' +
      '<div class="stat"><b>' + st.done + '</b><span>끝낸 일</span></div>';

    $('#holdList').innerHTML = HOLD_PHRASES.map(function (p, i) {
      return '<div class="holdrow"><span class="k">' + esc(p.k) + '</span><span class="t">' + esc(p.t) + '</span>' +
        '<button class="copy-mini" data-act="copy-hold" data-i="' + i + '">복사</button></div>';
    }).join('');

    var fchips = [['open', '미완료'], ['all', '전체'], ['due', '오늘·지남'], ['week', '이번 주']];
    $('#trackFilters').innerHTML = fchips.map(function (f) {
      return '<button class="chip" data-act="tfilter" data-f="' + f[0] + '" aria-pressed="' + (tFilter === f[0]) + '">' + f[1] + '</button>';
    }).join('');
    renderTracker();

    DAILY_CHECKS.forEach(function (g) {
      var box = $('#ck-' + g.id);
      if (!box) return;
      var saved = (S.ck[ymd()] || []).filter(function (k) { return k.indexOf(g.id + ':') === 0; });
      box.querySelector('.ckhead .pill').textContent = saved.length + ' / ' + g.items.length;
      box.querySelector('.progress i').style.width = Math.round(saved.length / g.items.length * 100) + '%';
      box.querySelector('.ckbody').innerHTML = g.items.map(function (t, i) {
        var key = g.id + ':' + i;
        return '<label class="check"><input type="checkbox" data-act="ck" data-k="' + key + '"' + (saved.indexOf(key) > -1 ? ' checked' : '') + '><span>' + esc(t) + '</span></label>';
      }).join('');
    });
  }

  function renderTracker() {
    var arr = S.items.slice();
    function keepDone(i) { return !i.done || justDone[i.id]; }
    if (tFilter === 'open') arr = arr.filter(keepDone);
    if (tFilter === 'due') arr = arr.filter(function (i) { if (!keepDone(i)) return false; var d = dayDiff(i.due, ymd()); return d != null && d <= 0; });
    if (tFilter === 'week') arr = arr.filter(function (i) { if (!keepDone(i)) return false; var d = dayDiff(i.due, ymd()); return d != null && d > 0 && d <= 7; });
    arr = sortItems(arr);
    var host = $('#trackList');
    if (!arr.length) {
      host.innerHTML = '<div class="empty">' + (S.items.length ? '조건에 맞는 사안이 없습니다.' : '아직 적어 둔 사안이 없습니다.<br>머릿속에 남은 요청을 하나 적어 두면 퇴근이 가벼워집니다.') + '</div>';
      return;
    }
    host.innerHTML = arr.map(function (it) {
      var d = dueInfo(it);
      var del = pendingDelete === it.id;
      return '<div class="item' + (it.done ? ' done' : '') + '">' +
        '<input type="checkbox" class="icheck" data-act="item-done" data-id="' + it.id + '"' + (it.done ? ' checked' : '') + ' aria-label="완료">' +
        '<div class="body"><div class="ttl">' + esc(it.t) + '</div>' +
        '<div class="meta">' +
        '<span class="tag"><i class="catdot" style="background:var(--c' + catIdx(it.cat) + ')"></i>' + esc(catName(it.cat)) + '</span>' +
        (d ? '<span class="pill ' + d.cls + '">' + d.label + '</span>' : '') +
        (it.due ? '<span class="pill">' + fmtShort(it.due) + '</span>' : '') +
        (it.who ? '<span class="pill">' + esc(it.who) + '</span>' : '') +
        '</div>' +
        (it.memo ? '<div class="memo">' + esc(it.memo) + '</div>' : '') +
        (del ? '<div class="row" style="margin-top:8px"><span class="tiny" style="color:var(--danger)">삭제할까요?</span><button class="btn btn-sm btn-danger" data-act="item-del" data-id="' + it.id + '">삭제</button><button class="btn btn-sm btn-ghost" data-act="item-del-cancel">취소</button></div>' : '') +
        '</div>' +
        '<div class="acts">' +
        '<button class="iconbtn" data-act="item-edit" data-id="' + it.id + '" aria-label="고치기">✎</button>' +
        '<button class="iconbtn" data-act="item-askdel" data-id="' + it.id + '" aria-label="삭제">⌫</button>' +
        '</div></div>';
    }).join('');
  }

  function openItemForm(id) {
    var it = id ? S.items.filter(function (x) { return x.id === id; })[0] : null;
    var cur = it || { t: '', cat: 'gwanri', due: '', who: '', memo: '' };
    var opts = CATS.map(function (c) { return '<option value="' + c.id + '"' + (cur.cat === c.id ? ' selected' : '') + '>' + c.name + '</option>'; }).join('') + '<option value="etc"' + (cur.cat === 'etc' ? ' selected' : '') + '>기타</option>';
    openSheet(
      '<div class="sheet-head"><h2>' + (it ? '사안 고치기' : '사안 적기') + '</h2><button class="iconbtn" data-act="close-sheet" aria-label="닫기">✕</button></div>' +
      '<div class="sheet-body stack">' +
      '<div class="field"><label for="ifT">무엇을 해야 하나</label><input id="ifT" class="input" placeholder="예: 6반 학부모 민원 답변 정리" value="' + esc(cur.t) + '"></div>' +
      '<div class="grid" style="grid-template-columns:1fr 1fr;gap:10px">' +
      '<div class="field"><label for="ifCat">분류</label><select id="ifCat" class="select">' + opts + '</select></div>' +
      '<div class="field"><label for="ifDue">기한</label><input id="ifDue" class="input" type="date" value="' + esc(cur.due || '') + '"></div>' +
      '</div>' +
      '<div class="field"><label for="ifWho">담당·기다리는 사람</label><input id="ifWho" class="input" placeholder="예: 나, ○○선생님, 교감선생님" value="' + esc(cur.who) + '"></div>' +
      '<div class="field"><label for="ifMemo">메모 (선택)</label><textarea id="ifMemo" class="textarea" placeholder="연락 시각, 확인할 사람, 관련 공문 번호">' + esc(cur.memo) + '</textarea></div>' +
      '<div class="row" style="justify-content:flex-end;margin-top:4px"><button class="btn btn-ghost" data-act="close-sheet">취소</button><button class="btn btn-primary" data-act="item-save" data-id="' + (it ? it.id : '') + '">저장</button></div>' +
      '</div>'
    );
  }

  function saveItemForm(id) {
    var t = $('#ifT').value.trim();
    if (!t) { toast('할 일을 한 줄 적어 주세요'); $('#ifT').focus(); return; }
    var data = {
      t: t, cat: $('#ifCat').value || 'etc', due: $('#ifDue').value || '',
      who: $('#ifWho').value.trim(), memo: $('#ifMemo').value.trim()
    };
    if (id) {
      S.items.forEach(function (x) { if (x.id === id) { Object.keys(data).forEach(function (k) { x[k] = data[k]; }); } });
    } else {
      data.id = uid('i'); data.done = false; data.at = new Date().toISOString();
      S.items.unshift(data);
    }
    persist(); closeSheet(); renderDesk();
    toast(id ? '고쳤습니다' : '적어 뒀습니다');
  }

  /* ------------------------------------------------------------------ 플레이북 */
  var pbQuery = '', pbCat = 'all', pbRuleOnly = false;

  function pbFiltered() {
    var q = pbQuery.trim().toLowerCase();
    return PLAYBOOKS.filter(function (p) {
      if (pbCat !== 'all' && p.cat !== pbCat) return false;
      if (pbRuleOnly && !p.rule) return false;
      if (!q) return true;
      var hay = [p.t, p.lead, p.crit, (p.steps || []).join(' '), (p.dont || []).join(' '), (p.msgs || []).map(function (m) { return m.t; }).join(' '), catName(p.cat)].join(' ').toLowerCase();
      return q.split(/\s+/).filter(Boolean).every(function (tok) {
        var cands = [tok].concat(SEARCH_ALIASES[tok] || []);
        for (var i = 0; i < cands.length; i++) if (hay.indexOf(String(cands[i]).toLowerCase()) > -1) return true;
        return false;
      });
    });
  }
  function pbCard(p) {
    var notes = (S.notes[p.id] || []).length;
    return '<button class="pb-card" data-act="open-pb" data-id="' + p.id + '">' +
      '<div class="ct" style="color:var(--c' + catIdx(p.cat) + ')"><i class="catdot" style="background:var(--c' + catIdx(p.cat) + ')"></i>' + catName(p.cat) +
      (p.rule ? '<span class="tag badge-rule">규정 우선</span>' : '') + '</div>' +
      '<div class="tt">' + esc(p.t) + '</div>' +
      '<div class="ld">' + esc(p.lead) + '</div>' +
      '<div class="ft">문구 ' + (p.msgs || []).length + '개' + (notes ? '<span class="nt">· 내 사례 ' + notes + '</span>' : '') + '</div>' +
      '</button>';
  }
  function renderPbList() {
    var list = pbFiltered();
    $('#pbList').innerHTML = list.length ? list.map(pbCard).join('') : '<div class="empty">해당하는 상황이 없습니다.<br>다른 단어로 찾거나 분류를 넓혀 보세요.</div>';
    $('#pbCount').textContent = list.length + '개';
  }
  function renderPlaybook() {
    $('#pbChips').innerHTML = '<button class="chip" data-act="pbcat" data-c="all" aria-pressed="' + (pbCat === 'all') + '">전체</button>' +
      CATS.map(function (c) {
        return '<button class="chip" data-act="pbcat" data-c="' + c.id + '" aria-pressed="' + (pbCat === c.id) + '"><i class="catdot" style="background:var(--c' + catIdx(c.id) + ')"></i>' + c.name + '</button>';
      }).join('') +
      '<button class="chip" data-act="pbrule" aria-pressed="' + pbRuleOnly + '">⚖ 규정 우선</button>';
    $('#pbQ').value = pbQuery;
    renderPbList();

    $('#principleStrip').innerHTML = PRINCIPLES.map(function (p) {
      return '<div class="pr-card"><b>' + esc(p.t) + '</b><span>' + esc(p.d) + '</span></div>';
    }).join('');

    $('#mindList').innerHTML = MINDSET.map(function (m) {
      return '<div class="mind-item"><b>' + esc(m.t) + '</b><span>' + esc(m.d) + '</span></div>';
    }).join('');

    $('#talkRules').innerHTML = '<ol class="steps">' + SMALL_RULES.map(function (r, i) {
      return '<li><span class="n">' + (i + 1) + '</span><span>' + esc(r) + '</span></li>';
    }).join('') + '</ol>';

    $('#talkChips').innerHTML = SMALLTALK.map(function (s, i) {
      return '<button class="chip" data-act="talk-scene" data-i="' + i + '" aria-pressed="' + (i === 0) + '">' + esc(s.s) + '</button>';
    }).join('');
    renderTalk(0);
    $('#avoid').textContent = AVOID_TOPICS;
  }
  function renderTalk(i) {
    var s = SMALLTALK[i] || SMALLTALK[0];
    $$('[data-act="talk-scene"]').forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.i === i)); });
    $('#talkBody').innerHTML =
      '<p class="tiny" style="margin-bottom:8px">' + esc(s.note) + '</p>' +
      '<div class="row" style="gap:6px">' + s.p.map(function (t) {
        return '<button class="phrase-pill" data-act="copy-text" data-t="' + esc(t) + '">' + esc(t) + '<span class="faint">⧉</span></button>';
      }).join('') + '</div>';
  }

  function openPlaybook(id) {
    var p = PLAYBOOKS.filter(function (x) { return x.id === id; })[0];
    if (!p) return;
    var notes = S.notes[p.id] || [];
    var body =
      '<div class="sheet-head"><div style="flex:1"><div class="pb-meta" style="margin:0 0 6px">' +
      '<span class="tag" style="color:var(--c' + catIdx(p.cat) + ')"><i class="catdot" style="background:var(--c' + catIdx(p.cat) + ')"></i>' + catName(p.cat) + '</span>' +
      (p.rule ? '<span class="tag badge-rule">규정 우선 · 담당자 확인 먼저</span>' : '') +
      '</div><h2>' + esc(p.t) + '</h2></div>' +
      '<button class="iconbtn" data-act="close-sheet" aria-label="닫기">✕</button></div>' +
      '<div class="sheet-body stack-lg">' +
      '<p class="tiny" style="font-size:13px">' + esc(p.lead) + '</p>' +
      '<div class="crit"><span class="lb">판단 기준</span><span>' + esc(p.crit) + '</span></div>' +
      '<div><div class="section-label">판단 순서</div><ol class="steps">' + p.steps.map(function (s, i) {
        return '<li><span class="n">' + (i + 1) + '</span><span>' + esc(s) + '</span></li>';
      }).join('') + '</ol></div>' +
      '<div class="dont"><span class="lb">초보가 자주 하는 실수 — 이건 하지 않습니다</span><ul>' + p.dont.map(function (d) { return '<li>' + esc(d) + '</li>'; }).join('') + '</ul></div>' +
      '<div><div class="section-label">바로 보내는 문구</div>' + p.msgs.map(function (m, i) {
        return '<div class="msg"><div class="mh"><span class="mk">' + esc(m.k) + '</span><button class="copy-mini" data-act="copy-msg" data-id="' + p.id + '" data-i="' + i + '">복사</button></div><div class="mt">' + esc(m.t) + '</div></div>';
      }).join('') + '</div>' +
      (MIND[p.id] ? '<div class="mind-note"><span class="lb">마음 세팅</span><p>' + esc(MIND[p.id][0]) + '</p><small>키우는 힘 · ' + esc(MIND[p.id][1]) + '</small></div>' : '') +
      '<div class="note-sec"><div class="section-label">내 해결 사례</div>' +
      '<div class="row" style="gap:6px;align-items:flex-start"><input id="noteInput" class="input" placeholder="한 줄로 남겨 두면 다음에 그대로 씁니다" style="flex:1"><button class="btn btn-sm btn-primary" data-act="note-save" data-id="' + p.id + '">남기기</button></div>' +
      '<div class="nlist" id="noteList">' + (notes.length ? notes.map(function (n) {
        return '<div class="note-item"><span>' + esc(n.text) + '</span><time>' + fmtStamp(n.at) + ' <button class="btn-quiet" data-act="note-del" data-id="' + p.id + '" data-at="' + esc(n.at) + '" aria-label="삭제">✕</button></time></div>';
      }).join('') : '<div class="tiny faint">아직 없습니다. 오늘 처리한 일을 한 줄 남겨 보세요.</div>') + '</div></div>' +
      '</div>';
    openSheet(body);
  }

  function saveNote(id) {
    var inp = $('#noteInput'), v = inp ? inp.value.trim() : '';
    if (!v) { toast('한 줄 적어 주세요'); return; }
    S.notes[id] = (S.notes[id] || []);
    S.notes[id].unshift({ at: new Date().toISOString(), text: v });
    if (S.notes[id].length > 60) S.notes[id] = S.notes[id].slice(0, 60);
    persist(); inp.value = ''; openPlaybook(id);
    if ($('#pbList')) renderPbList();
    toast('남겼습니다');
  }

  /* ------------------------------------------------------------------ 회의 */
  function draft() {
    if (!S.mdraft) {
      S.mdraft = { date: ymd(), name: '학년 협의회 결과', rows: [{ k: '확정', t: '', who: '', due: '' }], memo: '' };
    }
    if (!S.mdraft.rows || !S.mdraft.rows.length) S.mdraft.rows = [{ k: '확정', t: '', who: '', due: '' }];
    return S.mdraft;
  }
  function renderMeeting() {
    var d = draft();
    $('#mDate').value = d.date || ymd();
    $('#mName').value = d.name || '';
    $('#mMemo').value = d.memo || '';
    renderMRows();
    var hasRows = d.rows.some(function (r) { return (r.t || '').trim(); });
    $('#mPreview').value = hasRows ? buildNotice() : '';
    renderMeetingList();
    renderRoadmap();
    renderAreas();
  }
  function renderMRows() {
    var d = draft();
    $('#mRows').innerHTML = d.rows.map(function (r, i) {
      return '<div class="mrow" data-row="' + i + '">' +
        '<select class="select" data-act="mrow-k" data-i="' + i + '"><option' + (r.k === '확정' ? ' selected' : '') + '>확정</option><option' + (r.k === '보류' ? ' selected' : '') + '>보류</option></select>' +
        '<input class="input" data-act="mrow-t" data-i="' + i + '" placeholder="' + (r.k === '보류' ? '무엇을 왜 보류했나' : '정한 내용') + '" value="' + esc(r.t) + '">' +
        '<input class="input" data-act="mrow-who" data-i="' + i + '" placeholder="담당" value="' + esc(r.who) + '">' +
        '<input class="input" type="date" data-act="mrow-due" data-i="' + i + '" value="' + esc(r.due) + '" aria-label="기한">' +
        '<button class="iconbtn delrow" data-act="mrow-del" data-i="' + i + '" aria-label="줄 지우기">✕</button>' +
        '</div>';
    }).join('');
  }
  function buildNotice() {
    var d = draft();
    var lines = [];
    lines.push('[' + (d.name || '학년 협의회 결과') + '] ' + fmtKorean(d.date || ymd()));
    lines.push('');
    var done = d.rows.filter(function (r) { return r.k === '확정' && r.t.trim(); });
    var hold = d.rows.filter(function (r) { return r.k === '보류' && r.t.trim(); });
    if (done.length) {
      lines.push('■ 확정');
      done.forEach(function (r, i) {
        var extra = [];
        if (r.who.trim()) extra.push('담당 ' + r.who.trim());
        if (r.due) extra.push('~' + fmtShort(r.due));
        lines.push((i + 1) + '. ' + r.t.trim() + (extra.length ? ' (' + extra.join(', ') + ')' : ''));
      });
      lines.push('');
    }
    if (hold.length) {
      lines.push('■ 보류');
      hold.forEach(function (r) {
        var extra = [];
        if (r.who.trim()) extra.push('담당 ' + r.who.trim());
        if (r.due) extra.push('다음 확인 ' + fmtShort(r.due));
        lines.push('· ' + r.t.trim() + (extra.length ? ' — ' + extra.join(', ') : ''));
      });
      lines.push('');
    }
    if (!done.length && !hold.length) {
      lines.push('· 오늘 정한 내용을 적어 주세요.');
      lines.push('');
    }
    if (d.memo.trim()) { lines.push('■ 안내'); lines.push(d.memo.trim()); lines.push(''); }
    lines.push('문의는 학년부장에게 주시면 됩니다.');
    return lines.join('\n');
  }
  function renderMeetingList() {
    var host = $('#mLog');
    if (!S.meetings.length) { host.innerHTML = '<div class="empty">저장한 회의록이 없습니다.<br>확정 내용을 만들고 저장해 두면 다음 회의가 가벼워집니다.</div>'; return; }
    host.innerHTML = S.meetings.map(function (m) {
      var first = (m.text || '').split('\n').map(function (l) { return l.trim(); }).filter(function (l) {
        return l && l.indexOf('[') !== 0 && l.indexOf('■') !== 0;
      })[0] || '';
      return '<div class="item"><div class="body"><div class="ttl">' + esc(fmtKorean(m.date)) + ' · ' + esc(m.name) + '</div>' +
        '<div class="memo">' + esc(first.slice(0, 90)) + '</div></div>' +
        '<div class="acts"><button class="btn btn-sm btn-ghost" data-act="m-view" data-id="' + m.id + '">보기</button>' +
        '<button class="copy-mini" data-act="m-copy" data-id="' + m.id + '">복사</button>' +
        '<button class="iconbtn" data-act="m-del" data-id="' + m.id + '" aria-label="삭제">⌫</button></div></div>';
    }).join('');
  }
  function renderRoadmap() {
    $('#roadmap').innerHTML = ROADMAP.map(function (ph) {
      var items = ph.items.map(function (t, i) {
        var key = ph.id + ':' + i;
        return '<label class="check rcheck"><input type="checkbox" data-act="road" data-k="' + key + '"' + (S.road[key] ? ' checked' : '') + '><span>' + esc(t) + '</span></label>';
      }).join('');
      var n = ph.items.filter(function (_, i) { return S.road[ph.id + ':' + i]; }).length;
      return '<div class="rm"><div class="when">' + esc(ph.when) + ' · ' + n + '/' + ph.items.length + '</div><b>' + esc(ph.t) + '</b>' + items + '</div>';
    }).join('');
  }
  function renderAreas() {
    $('#areas').innerHTML = AREAS.map(function (a) {
      var st = (S.areas[a.id] && S.areas[a.id].st) || 'todo';
      var memo = (S.areas[a.id] && S.areas[a.id].memo) || '';
      var pill = st === 'done' ? '<span class="pill ok">완료</span>' : st === 'doing' ? '<span class="pill due">진행</span>' : '<span class="pill">미착수</span>';
      return '<details class="area"><summary><span class="nm">' + esc(a.name) + (a.rule ? ' <span class="tag badge-rule">규정</span>' : '') + '</span>' + pill + '<span class="faint">▾</span></summary>' +
        '<div class="abody"><div class="agrid">' +
        '<div><b>먼저 확인</b><span>' + esc(a.check) + '</span></div>' +
        '<div><b>도움받을 곳</b><span>' + esc(a.help) + '</span></div>' +
        '<div><b>전달 방법</b><span>' + esc(a.deliver) + '</span></div>' +
        '<div><b>조심할 것</b><span>' + esc(a.risk) + '</span></div>' +
        '</div>' +
        '<div class="row" style="margin-top:11px;justify-content:space-between"><span class="lbl">진행 상태</span><span class="statussel">' +
        ['todo', 'doing', 'done'].map(function (k) {
          var label = k === 'todo' ? '미착수' : k === 'doing' ? '진행' : '완료';
          return '<button data-act="area-st" data-id="' + a.id + '" data-st="' + k + '" aria-pressed="' + (st === k) + '">' + label + '</button>';
        }).join('') + '</span></div>' +
        '<div class="field" style="margin-top:9px"><label for="am-' + a.id + '">내 메모</label><textarea id="am-' + a.id + '" class="textarea" style="min-height:56px" data-act="area-memo" data-id="' + a.id + '" placeholder="올해 우리 학년 상황, 확인한 사람, 결정한 기준">' + esc(memo) + '</textarea></div>' +
        '</div></details>';
    }).join('');
  }

  /* ------------------------------------------------------------------ 교육과정 */
  var curOpen = { 1: true };
  function curProgress() {
    var total = 0, on = 0;
    CUR_STEPS.forEach(function (s) { s.items.forEach(function (_, i) { total++; if (S.cur['s' + s.n + ':' + i]) on++; }); });
    var hTotal = CUR_HANDOFF.length, hOn = CUR_HANDOFF.filter(function (_, i) { return S.cur['h:' + i]; }).length;
    var fTotal = CUR_FINISH.length, fOn = CUR_FINISH.filter(function (_, i) { return S.cur['f:' + i]; }).length;
    return { total: total + hTotal + fTotal, on: on + hOn + fOn, stepTotal: total, stepOn: on, hTotal: hTotal, hOn: hOn, fTotal: fTotal, fOn: fOn };
  }
  function renderCurric() {
    var p = curProgress();
    $('#curSummary').innerHTML =
      '<div class="cur-stat"><b>' + p.on + ' / ' + p.total + '</b><span>전체 완료</span></div>' +
      '<div class="cur-stat"><b>' + Math.round(p.stepOn / p.stepTotal * 100) + '%</b><span>1~8단계</span></div>' +
      '<div class="cur-stat"><b>' + (S.cur['s!:0'] ? '확인' : '미확인') + '</b><span>단축수업 날짜</span></div>' +
      '<div class="cur-stat"><b>' + p.hOn + ' / ' + p.hTotal + '</b><span>동학년 전달</span></div>';
    $('#curBar').style.width = Math.round(p.on / p.total * 100) + '%';

    $('#curSteps').innerHTML = CUR_STEPS.map(function (s) {
      var key = 's' + s.n;
      var n = s.items.filter(function (_, i) { return S.cur[key + ':' + i]; }).length;
      var full = n === s.items.length;
      var open = curOpen[String(s.n)] ? ' open' : '';
      return '<details class="curstep' + (s.n === '!' ? ' is-bang' : '') + (full ? ' done' : '') + '" data-step="' + s.n + '"' + open + '>' +
        '<summary><span class="curno">' + s.n + '</span><span class="cti"><b>' + esc(s.t) + (s.sub ? ' <span class="faint" style="font-weight:500">· ' + esc(s.sub) + '</span>' : '') + '</b>' +
        (s.n === '!' ? '<small>3단계 다음에 확인 · 학년군 부장과 논의</small>' : '') + '</span>' +
        '<span class="cprog">' + n + '/' + s.items.length + '</span><span class="faint">▾</span></summary>' +
        '<div class="cbody">' + s.items.map(function (t, i) {
          var k = key + ':' + i;
          return '<label class="check"><input type="checkbox" data-act="cur" data-k="' + k + '"' + (S.cur[k] ? ' checked' : '') + '><span>' + esc(t) + '</span></label>';
        }).join('') + (s.tip ? '<div class="curtip">' + esc(s.tip) + '</div>' : '') + (s.note ? '<div class="curtip">' + esc(s.note) + '</div>' : '') + '</div></details>';
    }).join('');

    $('#curPrinciples').innerHTML = CUR_PRINCIPLES.map(function (pr, i) {
      return '<div class="card" style="padding:14px"><div class="pb-meta" style="margin-bottom:6px"><span class="tag">원칙 ' + (i + 1) + '</span></div><b style="font-size:13.5px;letter-spacing:-.02em">' + esc(pr.t) + '</b><p class="tiny" style="margin-top:5px;white-space:pre-line">' + esc(pr.d) + '</p></div>';
    }).join('');

    $('#curHandoff').innerHTML = CUR_HANDOFF.map(function (t, i) {
      var k = 'h:' + i;
      return '<label class="check"><input type="checkbox" data-act="cur" data-k="' + k + '"' + (S.cur[k] ? ' checked' : '') + '><span>' + esc(t) + '</span></label>';
    }).join('');

    $('#curFinish').innerHTML = CUR_FINISH.map(function (t, i) {
      var k = 'f:' + i;
      return '<label class="check"><input type="checkbox" data-act="cur" data-k="' + k + '"' + (S.cur[k] ? ' checked' : '') + '><span>' + esc(t) + ' 확인</span></label>';
    }).join('');

    var url = S.docUrl || '';
    $('#curSheetUrl').value = url;
    $('#curSheetSaved').innerHTML = url
      ? '<span class="tag">저장됨</span><a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(url.replace(/^https?:\/\//, '').slice(0, 60)) + '</a>'
      : '<span class="tiny faint">아직 연결한 링크가 없습니다. 학년 활동별 시간표 시트 주소를 붙여 넣으면 여기서 바로 열 수 있습니다.</span>';
  }

  /* ------------------------------------------------------------------ 설정 */
  function renderSettings() {
    var auto = lsGet(AUTO_KEY, '1') !== '0' && urlOk(S.sheetUrl);
    $('#sUrl').value = S.sheetUrl || '';
    $('#sAuto').setAttribute('aria-checked', String(auto));
    $('#sStatus').textContent = statusText;
    $('#sStatus').className = 'st ' + statusKind;

    var snaps = getSnaps();
    $('#snapList').innerHTML = snaps.length ? snaps.map(function (s, i) {
      var count = (s.data && s.data.items ? s.data.items.length : 0);
      return '<div class="snap"><span class="kind">' + (s.kind === 'auto' ? '자동' : '수동') + '</span><time>' + fmtStamp(s.at) + ' · 사안 ' + count + '개</time>' +
        '<button class="btn btn-sm btn-ghost" data-act="snap-restore" data-i="' + i + '">되돌리기</button>' +
        '<button class="iconbtn" data-act="snap-del" data-i="' + i + '" aria-label="지우기">⌫</button></div>';
    }).join('') : '<div class="tiny faint">스냅샷이 없습니다. 오늘 상태를 한 번 저장해 두세요.</div>';
    $$('[data-act="theme"]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.theme === themePref())); });
  }

  /* ------------------------------------------------------------------ 스냅샷 */
  function getSnaps() {
    try { var v = JSON.parse(localStorage.getItem(LS_SNAP) || '[]'); return v instanceof Array ? v : []; } catch (e) { return []; }
  }
  function snapNow(kind) {
    var snaps = getSnaps();
    snaps.unshift({ at: new Date().toISOString(), kind: kind || 'manual', data: JSON.parse(JSON.stringify(S)) });
    snaps = snaps.slice(0, 5);
    lsSet(LS_SNAP, JSON.stringify(snaps));
  }
  function autoSnapOnceADay() {
    var snaps = getSnaps();
    var today = ymd();
    var has = snaps.some(function (s) { return s.kind === 'auto' && s.at.slice(0, 10) === today; });
    if (!has && (S.items.length || S.meetings.length || Object.keys(S.notes).length)) snapNow('auto');
  }
  function restoreSnap(i) {
    var snaps = getSnaps(), s = snaps[i];
    if (!s || !s.data) return;
    snapNow('auto');
    S = Object.assign(blank(), s.data);
    persist({ silent: true });
    closeSheet(); renderAll(); toast('되돌렸습니다 · 되돌리기 전 상태도 저장해 뒀습니다');
  }

  /* ------------------------------------------------------------------ 동기화 */
  var statusText = '', statusKind = '';
  function setSyncStatus(msg, kind) {
    statusText = msg; statusKind = kind || '';
    var el = $('#sStatus');
    if (el) { el.textContent = msg; el.className = 'st ' + (kind || ''); }
    var rail = $('#railSync');
    if (rail) {
      rail.className = 'sync ' + (kind === 'ok' ? 'on' : kind === 'err' ? 'err' : '');
      rail.querySelector('span').textContent = msg || '자동 동기화 꺼짐';
    }
  }
  function urlOk(u) {
    if (!u) return false;
    if (/^https:\/\//i.test(u)) return true;
    return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//i.test(u);
  }
  function autoEnabled() { return lsGet(AUTO_KEY, '1') !== '0' && urlOk(S.sheetUrl); }
  function localLastTs() { return Math.max(tsOf(lsGet(LAST_KEY, '')), tsOf(lsGet(EDIT_KEY, ''))); }
  function stateEmpty() {
    var notes = Object.keys(S.notes || {}).filter(function (k) { return (S.notes[k] || []).length; });
    var cur = Object.keys(S.cur || {}).filter(function (k) { return S.cur[k]; });
    return !S.items.length && !S.meetings.length && !notes.length && !cur.length;
  }
  function callSheet(url, payload) {
    return fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(payload), redirect: 'follow'
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    }).then(function (t) {
      var d;
      try { d = JSON.parse(t); } catch (e) { throw new Error('응답을 읽지 못했습니다. 배포 주소(/exec)와 액세스 권한(모든 사용자)을 확인하세요.'); }
      if (d && d.ok === false) throw new Error(d.error || '시트 쪽에서 거부했습니다.');
      return d;
    });
  }

  var pushTimer = null, pushing = false, pulling = false, pendingPush = false, retries = 0, applying = false, lastPullAt = 0;
  function markEdit() {
    if (applying) return;
    lsSet(EDIT_KEY, new Date().toISOString());
    if (!autoEnabled()) return;
    pendingPush = true;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(pushAuto, PUSH_DELAY);
  }
  function pushAuto(force) {
    if (!force && !autoEnabled()) return;
    if (pushing || pulling) {
      if (!force) { clearTimeout(pushTimer); pushTimer = setTimeout(pushAuto, 800); }
      return;
    }
    if (stateEmpty()) { setSyncStatus('기록이 없어 시트로 보내지 않았습니다.', ''); return; }
    pushing = true; pendingPush = false;
    var at = new Date().toISOString();
    setSyncStatus('동기화 중…', '');
    var payload = { action: 'save', app: APP_NAME, version: 2, savedAt: at, data: S };
    callSheet(S.sheetUrl, payload).then(function (d) {
      pushing = false; retries = 0;
      var savedAt = (d && (d.savedAt || d.updatedAt)) || at;
      lsSet(LAST_KEY, savedAt);
      setSyncStatus('자동 저장됨 · ' + fmtStamp(savedAt), 'ok');
      if (pendingPush) { pendingPush = false; clearTimeout(pushTimer); pushTimer = setTimeout(pushAuto, 600); }
    }).catch(function (err) {
      pushing = false;
      var m = (err && err.message) || '알 수 없는 오류';
      var offline = navigator.onLine === false || /Failed to fetch|NetworkError|Load failed|timeout/i.test(m);
      setSyncStatus((offline ? '오프라인 · 기기에 저장됨' : '동기화 실패: ' + m), 'err');
      if (retries < 3) { retries++; clearTimeout(pushTimer); pushTimer = setTimeout(pushAuto, 5000 * retries); }
    });
  }
  function pullIfNewer(opts) {
    opts = opts || {};
    if ((!opts.force && !autoEnabled()) || pulling || pushing) return Promise.resolve(false);
    if (!urlOk(S.sheetUrl)) return Promise.resolve(false);
    if (!opts.force && document.getElementById('backdrop')) return Promise.resolve(false);  // 입력 중에는 화면을 갈아엎지 않습니다
    var now = Date.now();
    if (opts.ignoreGap !== true && now - lastPullAt < PULL_GAP) return Promise.resolve(false);
    lastPullAt = now;
    pulling = true;
    return callSheet(S.sheetUrl, { action: 'load' }).then(function (d) {
      pulling = false;
      var inc = d && d.data;
      if (!inc || typeof inc !== 'object') { setSyncStatus('시트에 저장된 기록이 없습니다.', ''); return false; }
      var remoteAt = d.savedAt || d.updatedAt || inc.updatedAt || '';
      var rt = tsOf(remoteAt);
      if (!rt || rt <= localLastTs() + SKEW) return false;
      var remoteEmpty = !(inc.items || []).length && !(inc.meetings || []).length;
      if (remoteEmpty && !stateEmpty()) { setSyncStatus('시트가 비어 있어 이 기기 기록을 그대로 두었습니다.', ''); return false; }
      var same = JSON.stringify(normalizeState(inc)) === JSON.stringify(normalizeState(S));
      lsSet(LAST_KEY, remoteAt);
      if (same) { setSyncStatus('시트가 이미 최신입니다.', 'ok'); return false; }
      applying = true;
      try { S = normalizeState(inc); persist({ silent: true }); } finally { applying = false; }
      lsSet(EDIT_KEY, remoteAt);
      renderAll();
      setSyncStatus('시트에서 불러왔습니다 · ' + fmtStamp(remoteAt), 'ok');
      toast('다른 기기의 기록을 불러왔습니다');
      return true;
    }).catch(function (err) {
      pulling = false;
      setSyncStatus('시트 확인 실패: ' + ((err && err.message) || '') + ' · 기기 기록은 그대로입니다.', 'err');
      return false;
    });
  }
  function normalizeState(o) {
    var b = blank();
    Object.keys(b).forEach(function (k) {
      if (o && o[k] !== undefined && o[k] !== null) b[k] = o[k];
    });
    if (!(b.items instanceof Array)) b.items = [];
    if (!(b.meetings instanceof Array)) b.meetings = [];
    return b;
  }

  /* ------------------------------------------------------------------ 내보내기/가져오기 */
  function exportJson() {
    var payload = { app: APP_NAME, version: 2, exportedAt: new Date().toISOString(), data: S };
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'bujang-chammo-' + ymd() + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
    toast('파일로 내보냈습니다');
  }
  function importJson(file) {
    var r = new FileReader();
    r.onload = function () {
      try {
        var o = JSON.parse(String(r.result));
        var data = o && o.data ? o.data : o;
        if (!data || typeof data !== 'object' || !(data.items instanceof Array || data.meetings instanceof Array || data.cur)) throw new Error('형식이 다릅니다');
        snapNow('auto');
        S = normalizeState(data);
        persist({ silent: true });
        renderAll();
        toast('불러왔습니다');
      } catch (e) { toast('불러오지 못했습니다. 이 앱에서 내보낸 파일인지 확인해 주세요.'); }
    };
    r.readAsText(file);
  }

  /* ------------------------------------------------------------------ 탭 */
  var currentTab = 'desk';
  function setTab(name) {
    currentTab = name;
    ['desk', 'playbook', 'meeting', 'curric', 'settings'].forEach(function (t) {
      var v = $('#view-' + t);
      if (v) v.hidden = t !== name;
    });
    $$('[data-act="tab"]').forEach(function (b) {
      if (b.dataset.tab === name) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    if (name === 'desk') renderDesk();
    if (name === 'playbook') renderPlaybook();
    if (name === 'meeting') renderMeeting();
    if (name === 'curric') renderCurric();
    if (name === 'settings') renderSettings();
    window.scrollTo(0, 0);
    try { history.replaceState(null, '', '#' + name); } catch (e) { }
  }
  function renderAll() {
    renderDesk(); renderPlaybook(); renderMeeting(); renderCurric(); renderSettings();
  }

  /* ------------------------------------------------------------------ 이벤트 */
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-act]');
    if (!t) return;
    var act = t.dataset.act;

    if (act === 'tab') { setTab(t.dataset.tab); return; }
    if (act === 'theme') { lsSet(LS_THEME, t.dataset.theme); applyTheme(); return; }
    if (act === 'theme-cycle') {
      var order = ['auto', 'light', 'dark'];
      var nx = order[(order.indexOf(themePref()) + 1) % 3];
      lsSet(LS_THEME, nx); applyTheme();
      toast(nx === 'auto' ? '기기 설정을 따릅니다' : nx === 'light' ? '밝게 고정' : '어둡게 고정');
      return;
    }
    if (act === 'talk-random') {
      var all = [];
      SMALLTALK.forEach(function (s) { s.p.forEach(function (p) { all.push([s.s, p]); }); });
      var pick = all[Math.floor(Math.random() * all.length)];
      $('#talkRand').innerHTML = '<span class="faint">' + esc(pick[0]) + '</span> · ' + esc(pick[1]) +
        ' <button class="copy-mini" data-act="copy-text" data-t="' + esc(pick[1]) + '">복사</button>';
      return;
    }
    if (act === 'close-sheet') { closeSheet(); return; }
    if (t.id === 'backdrop') { closeSheet(); return; }

    if (act === 'copy-hold') { copyText(HOLD_PHRASES[+t.dataset.i].t, t); return; }
    if (act === 'copy-text') { copyText(t.dataset.t || '', t); return; }
    if (act === 'copy-msg') {
      var pb = PLAYBOOKS.filter(function (x) { return x.id === t.dataset.id; })[0];
      if (pb) copyText(pb.msgs[+t.dataset.i].t, t);
      return;
    }

    if (act === 'tfilter') { tFilter = t.dataset.f; justDone = {}; renderDesk(); return; }
    if (act === 'item-new') { openItemForm(null); return; }
    if (act === 'item-edit') { openItemForm(t.dataset.id); return; }
    if (act === 'item-save') { saveItemForm(t.dataset.id); return; }
    if (act === 'item-askdel') { pendingDelete = t.dataset.id; renderTracker(); return; }
    if (act === 'item-del-cancel') { pendingDelete = null; renderTracker(); return; }
    if (act === 'item-del') {
      S.items = S.items.filter(function (x) { return x.id !== t.dataset.id; });
      pendingDelete = null; persist(); renderDesk(); toast('지웠습니다'); return;
    }

    if (act === 'pbcat') { pbCat = t.dataset.c; renderPlaybook(); return; }
    if (act === 'pbrule') { pbRuleOnly = !pbRuleOnly; renderPlaybook(); return; }
    if (act === 'open-pb') { openPlaybook(t.dataset.id); return; }
    if (act === 'note-save') { saveNote(t.dataset.id); return; }
    if (act === 'note-del') {
      var id = t.dataset.id, at = t.dataset.at;
      S.notes[id] = (S.notes[id] || []).filter(function (n) { return n.at !== at; });
      persist(); if ($('#pbList')) renderPbList(); openPlaybook(id); return;
    }
    if (act === 'talk-scene') { renderTalk(+t.dataset.i); return; }

    if (act === 'mrow-del') { var d0 = draft(); d0.rows.splice(+t.dataset.i, 1); if (!d0.rows.length) d0.rows.push({ k: '확정', t: '', who: '', due: '' }); persist(); renderMRows(); return; }
    if (act === 'mrow-add') {
      draft().rows.push({ k: '확정', t: '', who: '', due: '' }); persist(); renderMRows();
      var ins = $$('#mRows [data-act="mrow-t"]'); if (ins.length) ins[ins.length - 1].focus();
      return;
    }
    if (act === 'm-gen') { $('#mPreview').value = buildNotice(); toast('문구를 만들었습니다'); return; }
    if (act === 'm-copy') {
      var text = t.dataset.id ? (S.meetings.filter(function (m) { return m.id === t.dataset.id; })[0] || {}).text : $('#mPreview').value;
      if (text) copyText(text, t); return;
    }
    if (act === 'm-save') {
      var dv = draft();
      var txt = $('#mPreview').value || buildNotice();
      var has = dv.rows.some(function (r) { return r.t.trim(); });
      if (!has) { toast('정한 내용을 먼저 적어 주세요'); return; }
      S.meetings.unshift({ id: uid('m'), date: dv.date, name: dv.name || '학년 협의회 결과', text: txt, rows: JSON.parse(JSON.stringify(dv.rows)), memo: dv.memo, at: new Date().toISOString() });
      if (S.meetings.length > 100) S.meetings = S.meetings.slice(0, 100);
      persist(); renderMeetingList(); toast('회의록에 저장했습니다'); return;
    }
    if (act === 'm-view') {
      var mm = S.meetings.filter(function (m) { return m.id === t.dataset.id; })[0];
      if (!mm) return;
      openSheet('<div class="sheet-head"><h2>' + esc(fmtKorean(mm.date)) + ' · ' + esc(mm.name) + '</h2><button class="iconbtn" data-act="close-sheet">✕</button></div>' +
        '<div class="sheet-body"><textarea class="notice-preview" readonly>' + esc(mm.text) + '</textarea>' +
        '<div class="row" style="justify-content:flex-end;margin-top:10px"><button class="btn btn-primary" data-act="m-copy" data-id="' + mm.id + '">복사</button></div></div>');
      return;
    }
    if (act === 'm-del') {
      S.meetings = S.meetings.filter(function (m) { return m.id !== t.dataset.id; });
      persist(); renderMeetingList(); toast('지웠습니다'); return;
    }
    if (act === 'area-st') {
      var aid = t.dataset.id;
      S.areas[aid] = S.areas[aid] || {};
      S.areas[aid].st = t.dataset.st;
      persist();
      var det = t.closest('details');
      if (det) {
        $$('[data-act="area-st"]', det).forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.st === t.dataset.st)); });
        var pil = det.querySelector('summary .pill');
        if (pil) {
          pil.textContent = t.dataset.st === 'done' ? '완료' : t.dataset.st === 'doing' ? '진행' : '미착수';
          pil.className = 'pill ' + (t.dataset.st === 'done' ? 'ok' : t.dataset.st === 'doing' ? 'due' : '');
        }
      }
      return;
    }

    if (act === 'cur-reset') {
      if (t.dataset.confirm === '1') { S.cur = {}; persist(); renderCurric(); toast('체크를 모두 지웠습니다'); }
      else { t.dataset.confirm = '1'; t.textContent = '한 번 더 누르면 지웁니다'; setTimeout(function () { t.dataset.confirm = ''; t.textContent = '체크 모두 지우기'; }, 3000); }
      return;
    }
    if (act === 'cur-sheet-save') {
      var u = $('#curSheetUrl').value.trim();
      if (u && !urlOk(u)) { toast('https:// 주소를 넣어 주세요'); return; }
      S.docUrl = u; persist(); renderCurric(); toast(u ? '링크를 저장했습니다' : '링크를 지웠습니다'); return;
    }

    if (act === 'snap-now') { snapNow('manual'); renderSettings(); toast('스냅샷을 저장했습니다'); return; }
    if (act === 'snap-restore') {
      var si = +t.dataset.i;
      openSheet('<div class="sheet-head"><h2>이 상태로 되돌릴까요?</h2><button class="iconbtn" data-act="close-sheet">✕</button></div>' +
        '<div class="sheet-body stack"><p class="tiny">되돌리면 지금 상태는 자동으로 한 번 더 저장됩니다. 최근 5개까지만 남습니다.</p>' +
        '<div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-act="close-sheet">취소</button><button class="btn btn-primary" data-act="snap-do" data-i="' + si + '">되돌리기</button></div></div>');
      return;
    }
    if (act === 'snap-do') { restoreSnap(+t.dataset.i); return; }
    if (act === 'snap-del') {
      var snaps = getSnaps(); snaps.splice(+t.dataset.i, 1); lsSet(LS_SNAP, JSON.stringify(snaps)); renderSettings(); return;
    }
    if (act === 'export') { exportJson(); return; }
    if (act === 'import-click') { $('#importFile').click(); return; }
    if (act === 'sync-toggle') {
      if (!urlOk(S.sheetUrl)) { setSyncStatus('먼저 Apps Script 주소를 저장해 주세요.', 'err'); toast('주소를 먼저 저장해 주세요'); return; }
      var nowAuto = lsGet(AUTO_KEY, '1') !== '0';
      lsSet(AUTO_KEY, nowAuto ? '0' : '1');
      renderSettings();
      if (!nowAuto) { pullIfNewer({ ignoreGap: true }); }
      return;
    }
    if (act === 'sync-save-url') {
      var su = $('#sUrl').value.trim();
      if (su && !urlOk(su)) { setSyncStatus('https:// 로 시작하는 Apps Script 웹 앱 주소를 넣어 주세요.', 'err'); return; }
      S.sheetUrl = su; persist({ silent: true });
      if (!su) setSyncStatus('주소를 지웠습니다.', '');
      else { setSyncStatus('연결 확인 중…', ''); pullIfNewer({ ignoreGap: true }); }
      return;
    }
    if (act === 'sync-push') {
      if (!urlOk(S.sheetUrl)) { setSyncStatus('먼저 웹 앱 주소를 저장해 주세요.', 'err'); return; }
      if (stateEmpty()) { setSyncStatus('기록이 없어 보내지 않았습니다.', ''); return; }
      pushAuto(true); return;
    }
    if (act === 'sync-pull') {
      if (!urlOk(S.sheetUrl)) { setSyncStatus('먼저 웹 앱 주소를 저장해 주세요.', 'err'); return; }
      pullIfNewer({ ignoreGap: true, force: true }).then(function (did) { if (!did) toast('시트가 이 기기보다 새롭지 않습니다'); });
      return;
    }
    if (act === 'wipe') {
      if (t.dataset.confirm === '1') {
        snapNow('auto'); S = blank(); persist({ silent: true }); renderAll(); closeSheet(); toast('모두 지웠습니다 · 스냅샷에서 되돌릴 수 있습니다');
      } else {
        openSheet('<div class="sheet-head"><h2>기록을 모두 지울까요?</h2><button class="iconbtn" data-act="close-sheet">✕</button></div>' +
          '<div class="sheet-body stack"><p class="tiny">이 기기의 사안·회의록·사례 노트·체크가 모두 지워집니다. 지우기 전 상태는 스냅샷에 저장됩니다. 구글 시트에 백업이 있으면 설정에서 다시 불러올 수 있습니다.</p>' +
          '<div class="row" style="justify-content:flex-end"><button class="btn btn-ghost" data-act="close-sheet">취소</button><button class="btn btn-danger" data-act="wipe" data-confirm="1">모두 지우기</button></div></div>');
      }
      return;
    }
  });

  document.addEventListener('change', function (e) {
    var t = e.target.closest('[data-act]');
    if (!t) return;
    var act = t.dataset.act;
    if (act === 'ck') {
      var day = ymd();
      S.ck[day] = S.ck[day] || [];
      var i = S.ck[day].indexOf(t.dataset.k);
      if (t.checked && i < 0) S.ck[day].push(t.dataset.k);
      if (!t.checked && i > -1) S.ck[day].splice(i, 1);
      persist(); renderDesk(); return;
    }
    if (act === 'item-done') {
      S.items.forEach(function (x) {
        if (x.id !== t.dataset.id) return;
        x.done = t.checked; x.doneAt = t.checked ? new Date().toISOString() : '';
        if (t.checked) justDone[x.id] = 1; else delete justDone[x.id];
      });
      persist(); renderDesk(); return;
    }
    if (act === 'cur') {
      S.cur[t.dataset.k] = t.checked;
      if (!t.checked) delete S.cur[t.dataset.k];
      persist(); renderCurric(); return;
    }
    if (act === 'road') {
      if (t.checked) S.road[t.dataset.k] = true; else delete S.road[t.dataset.k];
      persist(); renderRoadmap(); return;
    }
    if (act === 'area-memo') {
      var aid = t.dataset.id;
      S.areas[aid] = S.areas[aid] || {};
      S.areas[aid].memo = t.value;
      persist({ silent: true });
      markEdit();
      return;
    }
    if (act === 'mrow-k' || act === 'mrow-t' || act === 'mrow-who' || act === 'mrow-due') {
      var d = draft(), row = d.rows[+t.dataset.i];
      if (!row) return;
      if (act === 'mrow-k') row.k = t.value;
      if (act === 'mrow-t') row.t = t.value;
      if (act === 'mrow-who') row.who = t.value;
      if (act === 'mrow-due') row.due = t.value;
      persist({ silent: true });
      if (act === 'mrow-k') renderMRows();
      return;
    }
    if (act === 'm-date') { draft().date = t.value; persist({ silent: true }); return; }
    if (act === 'm-name') { draft().name = t.value; persist({ silent: true }); return; }
    if (act === 'm-memo') { draft().memo = t.value; persist({ silent: true }); return; }
    if (act === 'import-file') { if (t.files && t.files[0]) importJson(t.files[0]); t.value = ''; return; }
  });

  document.addEventListener('input', function (e) {
    var t = e.target.closest('[data-act]');
    if (t && t.dataset.act === 'pbq') { pbQuery = t.value; renderPbList(); }
    if (t && t.dataset.act === 'm-date-in') { draft().date = t.value; }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSheet();
  });

  document.addEventListener('toggle', function (e) {
    var d = e.target && e.target.closest ? e.target.closest('.curstep') : null;
    if (d) curOpen[d.dataset.step] = d.open;
  }, true);

  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'backdrop') closeSheet();
  });

  /* ------------------------------------------------------------------ 시작 */
  function bindDaily() {
    DAILY_CHECKS.forEach(function (g) {
      var host = $('#ck-' + g.id);
      if (!host) return;
      host.innerHTML =
        '<div class="ckhead"><div style="flex:1"><h3>' + esc(g.title) + '</h3><small>' + esc(g.sub) + '</small></div><span class="pill">0 / ' + g.items.length + '</span></div>' +
        '<div class="progress"><i></i></div><div class="ckbody" style="margin-top:6px"></div>';
    });
  }

  function boot() {
    applyTheme();
    bindDaily();
    autoSnapOnceADay();

    if (S.sheetUrl) setSyncStatus(autoEnabled() ? '자동 동기화 켜짐' : '자동 동기화 꺼짐', autoEnabled() ? 'ok' : '');
    else setSyncStatus('자동 동기화 꺼짐 — 설정에서 연결', '');

    var h = (location.hash || '').replace('#', '');
    setTab(['desk', 'playbook', 'meeting', 'curric', 'settings'].indexOf(h) > -1 ? h : 'desk');
    renderAll();

    if (autoEnabled()) {
      setTimeout(function () { pullIfNewer({ ignoreGap: true }); }, 700);
      document.addEventListener('visibilitychange', function () {
        if (!document.hidden) pullIfNewer({});
      });
      window.addEventListener('focus', function () { pullIfNewer({}); });
    }
    window.addEventListener('online', function () { if (autoEnabled()) { pushAuto(); } });

    if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
      navigator.serviceWorker.register('sw.js').catch(function () { });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
