# 부장 참모 — 학년부장 실전 데스크 (v2)

처음 학년부장을 맡은 사람이 **급한 순간에 바로 꺼내 쓰는** 웹앱/PWA입니다.
12학급 규모 학년을 혼자 떠안지 않도록, 판단 기준·순서·문구·기록을 한곳에 모았습니다.

- 설치 없이 열리는 단일 HTML + PWA(홈 화면 추가)
- 기록은 이 기기(localStorage)에 먼저 저장, 원하면 **본인 구글 시트**와 자동 동기화
- 앱 코드에 이름·학교명·개인 시트 주소가 들어가지 않습니다

## 화면

| 탭 | 내용 |
|---|---|
| 🎯 데스크 | 10초 즉답 보류 브레이크(말하기 전 3문 + 복사 문구), 미결 사안 트래커, 출근/퇴근 5분 체크(날짜별 자동 초기화) |
| 🛡️ 실전 플레이북 | 29개 상황 카드 — 판단 기준 1~2줄 · 판단 순서 · ⚠️ 초보 실수 · 바로 보내는 문구 3톤 · 내 해결 사례 노트. 검색·분류·`규정 우선` 필터 |
| 📋 회의·연간 | 초안 중심 회의 3단계, 확정/보류/담당/기한 → 카톡 공지 문구 생성·저장, 2~3월 로드맵, 10대 업무 영역(상태·메모) |
| 📚 교육과정 | 이지에듀 1~8단계 체크(3단계 뒤 `!` 단축수업 확인), 핵심 원칙 4, 동학년 전달 체크, 마무리 시수 점검, 내 시간표 시트 링크 |
| ⚙️ 설정 | 테마, 타임머신 스냅샷(최대 5), JSON 내보내기/불러오기, 구글 시트 자동 동기화 |

## 파일

```
work/bujang-pwa/
  index.html        앱 본체 (모든 CSS/JS 포함, 외부 의존 없음)
  manifest.json     PWA 매니페스트
  sw.js             오프라인 캐시 (VERSION 올리면 갱신)
  icon-192.png / icon-512.png / icon-180.png
  build.py          src/*.js|css|html → index.html 로 합치는 빌드 스크립트
  src/              소스 조각 (data-playbooks.js, data-core.js, app.js, style.css, shell.html)
  tests/            run_tests.py(화면 45개 검사) · verify_sync_gs.py(동기화·Apps Script 14개) · shots.py
  make_icons.py     아이콘 생성
/workspace/bujang_chammo.html        단독 실행용 복사본 (파일 하나로 동작)
/workspace/bujang_apps_script.gs     구글 시트 동기화 서버 (Apps Script)
/workspace/work/bujang-shots/        스크린샷
```

## 열기

- **PC**: `index.html`을 브라우저로 열기
- **휴대폰**: 파일을 보내 열거나, 아래처럼 웹에 올려 홈 화면에 추가(PWA)

## GitHub Pages로 배포 (3분)

1. GitHub에서 **빈 저장소**를 하나 만듭니다. (예: `bujang-chammo`, Public)
2. 이 폴더의 파일을 push:

```bash
cd work/bujang-pwa
git init && git add . && git commit -m "부장 참모 v2"
git branch -M main
git remote add origin https://github.com/<계정>/bujang-chammo.git
git push -u origin main
```

3. 저장소 Settings → Pages → Source: **Deploy from a branch** → `main` / `/ (root)` → Save
4. `https://<계정>.github.io/bujang-chammo/` 접속 → 브라우저 메뉴에서 **홈 화면에 추가**

> 아이콘·매니페스트·서비스워커가 같이 올라가야 설치형(PWA)으로 동작합니다.
> `index.html` 하나만 올리면 웹앱으로는 동작하지만 홈 화면 아이콘/오프라인은 제한됩니다.

## 구글 시트 동기화 (5분, 한 번만)

1. 구글 드라이브에서 새 스프레드시트 생성 (예: `부장 참모 백업`)
2. 그 시트에서 **확장 프로그램 → Apps Script**
3. 기본 `Code.gs`를 모두 지우고 `bujang_apps_script.gs` 내용을 붙여 넣기 → 저장
4. **배포 → 새 배포 → 유형: 웹 앱**
   - 실행: 나 / 액세스 권한: **모든 사용자** → 배포 → 권한 허용
5. 나온 `.../exec` 주소를 앱 **설정 → 구글 시트 자동 동기화**에 붙여 넣고 `주소 저장 · 확인`

이후로는 기록을 고치면 1.5초 뒤 시트로 자동 저장되고, 앱을 열거나 화면으로 돌아올 때 최신 기록을 확인합니다.
시트가 비어 있거나 이 기기보다 오래되었으면 **절대 기기 기록을 지우지 않습니다.**

## 데이터·개인정보

- 저장 위치: 브라우저 `localStorage` + (연결 시) 본인 구글 시트
- 앱에는 이름·학교명이 없습니다. 적는 내용(학부모·학생 관련)은 사용자가 직접 관리합니다.
- 공용 기기에서는 **설정 → 기록 지우기**로 정리하세요. 지우기 전 상태는 스냅샷에 남습니다.
- 사례 노트·사안에는 학생 실명 대신 `6반`, `○○`처럼 쓰는 것을 권합니다.

## 고칠 때

```bash
cd work/bujang-pwa
# src/ 수정 후
python3 build.py            # index.html + /workspace/bujang_chammo.html 동시 생성
PLAYWRIGHT_BROWSERS_PATH=/workspace/.cache/pw-browsers \
LD_LIBRARY_PATH=/workspace/.cache/pw-libs python3 tests/run_tests.py
```

`sw.js`의 `VERSION`을 올려야 이미 설치한 사용자에게 새 화면이 반영됩니다.

## 검증 결과 (2026-11-17)

- 화면 자동 검사 **45/45 통과** (4개 탭 + 설정, 복사, 트래커, 공지 생성, 스냅샷 복원, `!` 카드 위치, 모바일 가로 넘침 없음)
- 동기화·Apps Script 목 검사 **14/14 통과** (자동 저장 1.5초, 새 기록 반영, 빈 시트/빈 기록 덮어쓰기 차단, 시트 6종 생성)
- 백업·부가 기능 **9/9 통과** (JSON 내보내기/불러오기 왕복, 전체 지우기, 스냅샷 5개 제한, 테마 유지)
- 콘솔/페이지 오류 0, 단독 HTML(file://) 동작 확인, PWA 서비스워커 active 확인
