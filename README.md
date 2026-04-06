# Parry Warrior Editor

PySide6 기반의 새 리듬게임 에디터와, 기준 구현으로 남겨둔 legacy pygame 에디터가 함께 들어 있는 저장소입니다.

## 현재 구조

- `src/new_editor/` : 새 에디터
- `legacy/pygame_editor/` : legacy 기준 구현
- `docs/` : 분석 / 실행 / 빌드 / 릴리즈 문서
- `packaging/new_editor.spec` : 새 에디터 PyInstaller spec

## 1. 먼저 무엇을 실행하면 되나?

새 에디터를 실행하면 됩니다.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
.venv/bin/python src/new_editor/app.py
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
.venv\Scripts\python.exe src\new_editor\app.py
```

## 2. 실행 후 바로 확인할 것

1. `Open chart...` 또는 `Import legacy source...`
2. `Load song...`
3. `Space` 로 재생 / 일시정지
4. 가운데 타임라인 클릭으로 노트 배치
5. 우클릭 삭제
6. 하단 seek bar 드래그로 위치 이동
7. `Save As...` 로 저장

## 3. 플랫폼별 빌드 튜토리얼

중요: **Windows exe / macOS app / Linux 빌드는 각 OS에서 직접 빌드해야 합니다.**
한 운영체제에서 다른 운영체제용 데스크톱 번들을 직접 만드는 방식은 이 저장소의 기본 빌드 흐름으로 지원하지 않습니다.

### Windows에서 exe 빌드

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
.venv\Scripts\pyinstaller.exe packaging\new_editor.spec
```

결과물 예시:

- `dist/parry-warrior-editor/`

### macOS에서 실행 번들 빌드

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
.venv/bin/pyinstaller packaging/new_editor.spec
```

결과물 예시:

- `dist/parry-warrior-editor/`

### Linux에서 빌드

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
.venv/bin/pyinstaller packaging/new_editor.spec
```

결과물 예시:

- `dist/parry-warrior-editor/`

## 4. 세 OS 결과물을 한 폴더에 모으는 방법

권장 구조는 아래처럼 잡으면 됩니다.

```text
release-artifacts/
  v0.1.0/
    windows/
      parry-warrior-editor-win64.zip
    macos/
      parry-warrior-editor-macos.zip
    linux/
      parry-warrior-editor-linux.tar.gz
```

즉,

1. Windows에서 빌드
2. macOS에서 빌드
3. Linux에서 빌드
4. 각 결과물을 압축
5. 위 폴더 구조에 모아서 전달

이 방식이 가장 단순하고, GitHub Release에도 그대로 올리기 좋습니다.

현재 빌드 흐름은 **시스템 ffmpeg를 따로 설치하지 않는 방향**을 기준으로 정리되어 있습니다. 비-WAV 파형 추출은 번들된 ffmpeg를 우선 사용합니다.

## 5. GitHub Release에 올리는 방법

가장 권장하는 흐름은 **tag 생성 → 각 OS 빌드 수집 → draft release 생성 → asset 업로드 → publish** 입니다.

예시:

```bash
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 --draft --title "v0.1.0" --generate-notes
gh release upload v0.1.0 release-artifacts/v0.1.0/windows/parry-warrior-editor-win64.zip
gh release upload v0.1.0 release-artifacts/v0.1.0/macos/parry-warrior-editor-macos.zip
gh release upload v0.1.0 release-artifacts/v0.1.0/linux/parry-warrior-editor-linux.tar.gz
```

드래프트를 먼저 만든 뒤 asset을 다 올리고 마지막에 publish 하는 방식이 가장 안전합니다.

자세한 절차는 아래 문서를 보세요.

- `docs/github-release-guide.md`

## 6. 문서 목록

- `docs/gui-run-manual.md`
- `docs/quick-edit-mode-manual.md`
- `docs/build-manual.md`
- `docs/build-scripts-guide.md`
- `docs/github-release-guide.md`
- `docs/legacy-editor-analysis.md`
- `docs/legacy-feature-parity-checklist.md`
- `docs/new-editor-architecture.md`
- `docs/new-editor-reliability-requirements.md`

## 7. Legacy editor

legacy 실행/빌드는 아래 문서를 보면 됩니다.

- `legacy/pygame_editor/README.md`
