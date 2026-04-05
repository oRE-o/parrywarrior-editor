# GitHub Release 업로드 가이드

이 문서는 현재 버전의 빌드 결과물을 GitHub Release에 올리는 가장 단순한 절차를 설명합니다.

## 1. 먼저 알아둘 점

- Windows exe / macOS app / Linux 빌드는 **각 OS에서 직접 빌드**해야 합니다.
- 권장 흐름은 **draft release 먼저 생성하고, asset을 모두 올린 뒤 publish** 하는 방식입니다.
- 결과물은 한 폴더에 모아두면 업로드와 전달이 쉬워집니다.
- release asset에는 ffmpeg가 별도 설치 없이 동작하는 번들 출력물을 사용해야 합니다.

권장 폴더 구조:

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

## 2. release용 태그 만들기

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 3. draft release 만들기

`gh` CLI가 설치되어 있고 로그인되어 있다고 가정합니다.

```bash
gh release create v0.1.0 --draft --title "v0.1.0" --generate-notes
```

또는 notes 파일을 직접 쓸 수도 있습니다.

```bash
gh release create v0.1.0 --draft --title "v0.1.0" --notes-file docs/release-notes.md
```

## 4. 빌드 결과물 업로드

```bash
gh release upload v0.1.0 release-artifacts/v0.1.0/windows/parry-warrior-editor-win64.zip
gh release upload v0.1.0 release-artifacts/v0.1.0/macos/parry-warrior-editor-macos.zip
gh release upload v0.1.0 release-artifacts/v0.1.0/linux/parry-warrior-editor-linux.tar.gz
```

동일한 asset 이름을 교체해야 할 때만 아래 옵션을 사용합니다.

```bash
gh release upload v0.1.0 release-artifacts/v0.1.0/windows/parry-warrior-editor-win64.zip --clobber
```

## 5. 웹 UI에서 publish 하기

1. GitHub 저장소로 이동
2. `Releases` 진입
3. 방금 만든 draft release 열기
4. asset이 모두 붙었는지 확인
5. `Publish release`

## 6. 권장 순서 요약

1. 각 OS에서 빌드
2. 결과물을 `release-artifacts/<tag>/...` 아래에 정리
3. `git tag` + `git push origin <tag>`
4. `gh release create --draft`
5. `gh release upload`
6. 최종 확인 후 publish

## 7. 왜 draft를 먼저 쓰는가?

draft를 먼저 만들면,

- 업로드가 덜 된 상태로 공개되는 일을 막을 수 있고
- Windows/macOS/Linux 결과물을 다 확인한 뒤 publish 할 수 있으며
- release 본문과 asset 이름을 정리하기 쉽습니다.
