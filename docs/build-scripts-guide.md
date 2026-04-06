# Build Scripts Guide

이 문서는 새 editor를 **Windows / macOS에서 바로 빌드**할 때 사용하는 스크립트 사용법만 간단히 정리합니다.

## macOS

스크립트:

- `scripts/build-macos.sh`

실행:

```bash
chmod +x scripts/build-macos.sh
./scripts/build-macos.sh
```

결과물:

- 폴더: `release-artifacts/current/macos/parry-warrior-editor-macos/`
- 압축파일: `release-artifacts/current/macos/parry-warrior-editor-macos.zip`

이 스크립트는 아래를 자동으로 처리합니다.

1. `.venv` 생성(없으면)
2. `requirements-dev.txt` 설치
3. `packaging/new_editor.spec`로 PyInstaller 빌드
4. 결과물을 `release-artifacts/current/macos/` 아래에 복사
5. zip 생성

## Windows

스크립트:

- `scripts/build-windows.bat`

실행:

```bat
scripts\build-windows.bat
```

결과물:

- 폴더: `release-artifacts/current/windows/parry-warrior-editor-win64/`
- 압축파일: `release-artifacts/current/windows/parry-warrior-editor-win64.zip`

이 스크립트는 아래를 자동으로 처리합니다.

1. `.venv` 생성(없으면)
2. `requirements-dev.txt` 설치
3. `packaging\new_editor.spec`로 PyInstaller 빌드
4. 결과물을 `release-artifacts/current/windows/` 아래에 복사
5. zip 생성

## 주의

- macOS 빌드는 macOS에서 실행해야 합니다.
- Windows 빌드는 Windows에서 실행해야 합니다.
- Linux는 현재 별도 스크립트를 아직 추가하지 않았습니다. 필요하면 같은 방식으로 바로 추가할 수 있습니다.
