# Legacy Editor Analysis

## 1. 목적

이 문서는 현재 저장소의 **기존 pygame 기반 리듬게임 에디터**를 분석한 결과를 정리한 문서다.

이 문서의 목적은 다음과 같다.

1. 현재 legacy 에디터가 실제로 지원하는 기능을 명확히 고정한다.
2. 새 editor를 만들 때 반드시 유지해야 하는 동작을 정리한다.
3. 어떤 코드가 재사용 가능하고, 어떤 코드는 교체 대상인지 구분한다.
4. 초보자도 현재 프로젝트 구조와 이후 개발 방향을 이해할 수 있게 한다.

---

## 2. 현재 프로젝트 요약

현재 에디터는 `pygame` + `pygame_gui` 중심의 데스크톱 앱이다.

- 메인 진입점: `legacy/pygame_editor/src/main.py`
- 렌더링: `legacy/pygame_editor/src/editor_canvas.py`
- 오디오 처리: `legacy/pygame_editor/src/audio_manager.py`
- 차트 데이터 모델/저장: `legacy/pygame_editor/src/chart.py`
- 구 포맷 변환 스크립트: `legacy/pygame_editor/src/note_parser.py`
- 패키징: `legacy/pygame_editor/packaging/main.spec` (PyInstaller)

즉, 지금 구조는 **하나의 큰 pygame 앱**에 가깝다.
새 editor를 만들 때는 이 구조를 그대로 확장하는 것보다, **legacy 앱은 기준 구현(reference implementation)으로 남기고 새 editor는 별도 구조로 만드는 편이 안전하다.**

---

## 3. 현재 폴더 구조에서 중요한 위치

```text
legacy/pygame_editor/
  src/
    main.py            # 앱 실행, UI, 입력, 편집 로직, 재생 제어
    editor_canvas.py   # 중앙 편집 화면/파형/그리드 렌더링
    audio_manager.py   # 음악 로드, 파형 분석, 재생, hitsound
    chart.py           # 차트 데이터 구조, JSON 저장/로드
    note_parser.py     # 구 포맷 -> 현재 차트 포맷 변환 스크립트

  assets/
    hitsound.wav       # 편집 중 재생되는 타격음

  data/charts/
    *.json             # 예제 차트/자동저장 추정 파일

  packaging/
    main.spec          # PyInstaller 빌드 설정

src/new_editor/
  ...                  # 새 Qt 기반 에디터 구현
```

---

## 4. Legacy Editor의 실제 기능 목록

아래 내용은 코드 기준으로 확인한 기능만 적었다.

### 4.1 곡 로드

- 우측 패널의 `Load Song` 버튼으로 오디오 파일을 선택할 수 있다.
- `tkinter.filedialog`를 이용해 파일을 고른다.
- 지원 대상으로 보이는 확장자:
  - `.wav`
  - `.mp3`
  - `.ogg`
  - `.flac`
  - `.m4a`
  - `.aac`
  - `.opus`
  - `.aiff`
  - `.aif`
  - `.wma`
- 곡 로드가 성공하면:
  - 총 길이를 계산한다.
  - 파형 데이터를 준비한다.
  - 현재 시간과 재생 관련 상태를 초기화한다.
  - 우측 패널에 곡 이름을 표시한다.

관련 코드:

- `legacy/pygame_editor/src/main.py`
- `legacy/pygame_editor/src/audio_manager.py`

### 4.2 차트 저장 / 불러오기

- `Save Chart`, `Load Chart` 버튼이 있다.
- 차트는 JSON 파일로 저장된다.
- 개발 환경에서는 `legacy/pygame_editor/data/charts/`를 기본 경로로 사용한다.
- 패키징된 앱에서는 사용자 데이터 폴더를 사용한다.

저장되는 주요 값:

- `song_path`
- `bpm`
- `offset_ms`
- `num_lanes`
- `note_types`
- `notes`

관련 코드:

- `legacy/pygame_editor/src/chart.py`
- `legacy/pygame_editor/src/main.py`

### 4.3 재생 / 일시정지 / 정지

- 하단 패널에 `Play`, `Stop`, 시간 표시가 있다.
- 스페이스바로 재생/일시정지가 가능하다.
- 재생 중에는 현재 시간에 따라 hitsound 재생 체크가 이루어진다.
- 음수 시간(0ms 이전)에서 재생 시작할 경우 preroll 방식으로 처리한다.

이 의미는, 새 editor에서도 단순한 “음악 재생”이 아니라 아래 동작이 유지되어야 한다는 뜻이다.

- 현재 시간 기준 재생 시작
- 일시정지 후 같은 위치에서 재개
- 음수 시작 시간 처리
- 노트 시점 통과 시 hitsound 재생

관련 코드:

- `legacy/pygame_editor/src/main.py`
- `legacy/pygame_editor/src/audio_manager.py`

### 4.4 현재 시간 이동 / 스크롤

- 마우스 휠로 시간을 앞뒤로 이동할 수 있다.
- 재생 중이 아닐 때만 스크롤 이동이 동작한다.
- `Alt` 키를 누르면 더 느리게 이동한다.
- `Ctrl` 키를 누르면 더 빠르게 이동한다.
- 위/아래 방향키로 1ms 단위 미세 이동이 가능하다.
- 왼쪽 파형 패널을 클릭하면 그 위치로 현재 시간이 이동한다.

이 부분은 사용성에 매우 중요하므로 새 editor에서도 반드시 보존해야 한다.

### 4.5 에디터 캔버스 표시

중앙 편집 영역에는 다음 요소가 그려진다.

- 레인 경계선
- 그리드 라인
- 마디/박자 기준선
- 판정선
- 탭 노트
- 롱노트
- 롱노트 배치 중 미리보기

그리드 계산은 BPM과 snap division에 따라 달라진다.

관련 코드:

- `legacy/pygame_editor/src/editor_canvas.py`

### 4.6 파형 표시

- 왼쪽 패널에 현재 시간 기준의 파형이 세로 방향으로 표시된다.
- 파형 패널에도 판정선이 별도로 그려진다.
- 파형 데이터는 `librosa`로 읽고, 렌더링은 `pygame` 선 그리기로 처리한다.

새 editor에서 파형 표시는 거의 필수 기능으로 봐야 한다.

### 4.7 BPM / Offset 편집

- 우측 패널에서 BPM을 수정할 수 있다.
- Offset(ms)를 수정할 수 있다.
- 입력값이 잘못되면 기존 값으로 복구한다.

### 4.8 Zoom / Scroll Speed 조절

- 슬라이더로 `scale_pixels_per_ms` 값을 바꾸며 확대/축소 효과를 만든다.
- 화면에 보이는 시간 범위가 이 값에 따라 달라진다.

### 4.9 Snap Division 변경

- `4`, `8`, `12`, `16`, `24`, `32` 중 선택 가능하다.
- 노트를 배치할 때 raw time을 snap 기준으로 반올림해서 저장한다.

이 로직은 새 editor에서도 동일하거나 호환되게 유지되어야 한다.

### 4.10 레인 수 변경

- `3` ~ `7` 레인 지원
- 중앙 편집 영역은 현재 레인 수에 맞게 다시 계산된다.

### 4.11 노트 타입 선택

- 노트 타입 목록이 있으며 현재 선택된 타입으로 노트를 배치한다.
- 기본 노트 타입은 `Tap`, `Long`이다.

### 4.12 노트 타입 생성 / 편집

노트 타입에 대해 아래 속성을 편집할 수 있다.

- 이름
- 색상
- 롱노트 여부
- hitsound 재생 여부

지원 UI:

- 새 노트 타입 생성
- 기존 노트 타입 편집
- 프리셋 색상 버튼
- 컬러 피커

단, 현재 구현은 완성도가 높지 않다.

- 아무 노트 타입도 선택하지 않았을 때 Edit 버튼 흐름이 사실상 비어 있다.

### 4.13 노트 배치

- 중앙 편집 영역 클릭으로 노트를 배치한다.
- 레인 위치를 계산해서 해당 lane에 노트를 넣는다.
- snap에 맞춰 시간 보정 후 저장한다.
- 같은 위치가 점유되어 있으면 생성하지 않는다.

### 4.14 롱노트 배치

- 현재 선택된 노트 타입이 롱노트 타입이면:
  1. 첫 클릭으로 시작점 저장
  2. 두 번째 클릭으로 끝점 확정
- 끝점이 시작점보다 앞이면 자동으로 순서를 정리한다.
- 시작점과 끝점이 같으면 일반 노트처럼 처리한다.
- 배치 중에는 미리보기 사각형을 화면에 표시한다.

### 4.15 노트 삭제

- 우클릭으로 노트를 삭제할 수 있다.
- 삭제는 lane과 시간 기준으로 판정한다.
- 일반 노트는 특정 허용 오차 내에서 삭제한다.
- 롱노트는 시작~끝 범위와 허용 오차 기준으로 삭제한다.

이 삭제 판정 규칙은 새 editor에서 그대로 재현해야 한다.

### 4.16 재생 중 hitsound 처리

- 재생 프레임마다 현재 시간 구간을 지나간 노트를 검사한다.
- 노트 타입의 `play_hitsound`가 켜져 있으면 hitsound를 재생한다.
- 롱노트는 끝 지점도 hitsound 체크 대상이다.

---

## 5. 현재 UI 배치 구조

현재 UI는 4영역 구조다.

1. **왼쪽 패널**: 파형 표시, 클릭으로 시간 이동
2. **가운데 패널**: 실제 노트 편집 영역
3. **오른쪽 패널**: 설정, 노트 타입 편집, 파일 조작
4. **하단 패널**: 재생/정지/시간 표시

즉, 새 editor를 만들 때도 사용자가 기대하는 기본 배치는 아래와 유사할 가능성이 크다.

- 왼쪽: overview / waveform
- 가운데: timeline / lanes
- 오른쪽: property editor / tool panel
- 아래: transport controls

이 기본 레이아웃은 legacy 호환 관점에서 중요한 기준이다.

---

## 6. 차트 데이터 구조

현재 저장 포맷은 비교적 단순한 JSON이다.

예시 구조:

```json
{
  "song_path": "...",
  "bpm": 120.0,
  "offset_ms": 0,
  "num_lanes": 4,
  "note_types": {
    "Tap": {
      "name": "Tap",
      "color": [255, 80, 80],
      "is_long_note": false,
      "play_hitsound": true
    }
  },
  "notes": [
    {
      "time_ms": 3625.0,
      "note_type_name": "Tap",
      "lane": 0,
      "end_time_ms": null
    }
  ]
}
```

### 6.1 좋은 점

- 사람이 읽기 쉽다.
- 직렬화/역직렬화가 쉽다.
- UI와 분리된 순수 데이터 포맷으로 유지하기 좋다.

### 6.2 주의할 점

- `song_path`가 절대 경로일 수 있다.
- 환경이 바뀌면 해당 경로가 깨질 수 있다.
- 이후 새 editor에서는 프로젝트 기반 상대경로 정책을 고민할 필요가 있다.

---

## 7. 현재 구조의 기술적 문제점

### 7.1 `main.py` 집중도 과다

`legacy/pygame_editor/src/main.py`가 너무 많은 책임을 가진다.

- UI 생성
- 이벤트 처리
- 파일 열기/저장
- 재생 제어
- 스크롤/단축키
- 노트 배치/삭제
- 노트 타입 편집
- hitsound 트리거
- 렌더링 호출

즉, **앱 셸 + 편집 엔진 + 입력 처리 + 일부 도메인 로직**이 한 파일에 섞여 있다.

### 7.2 pygame 의존성이 너무 강함

현재 구현은 아래 요소에 깊게 묶여 있다.

- `pygame.event`
- `pygame.Surface`
- `pygame.draw`
- `pygame.mixer`
- `pygame.time.get_ticks()`
- `pygame_gui`

그래서 UI만 교체하는 수준이 아니라, 실제로는 다음을 함께 교체해야 한다.

- 입력 시스템
- 위젯 시스템
- 렌더링 시스템
- 오디오 시간 관리 방식

### 7.3 오디오 로직도 교체 비용이 큼

`audio_manager.py`는 단순 파일 로더가 아니다.

- 음악 로드
- 길이 계산
- 파형 분석
- 슬라이스 기반 재생
- pause/unpause 관리
- hitsound 채널 분리

즉 새 editor에서 오디오 시스템을 바꾸면, **재생 타이밍과 시각화 타이밍이 같이 흔들릴 가능성**이 있다.

### 7.4 테스트 부족

`tests/test.py`는 실제 기능 테스트가 아니다.

즉 지금은 기능 회귀(regression)를 자동으로 잡아줄 장치가 거의 없다.
새 editor 개발 전에 최소한 다음 항목은 테스트 가능 구조로 옮겨야 한다.

- snap 계산
- 노트 배치 규칙
- 롱노트 생성 규칙
- 삭제 판정 규칙
- JSON 저장/로드
- parser 변환 결과

---

## 8. 코드상 보이는 미완성/부족한 부분

다음 항목은 코드상 실제로 부족하거나 미완성으로 보인다.

- undo / redo 없음
- copy / paste 없음
- drag & drop 편집 없음
- 선택/다중 선택 시스템 없음
- 정식 테스트 없음
- `UIFileDialog` 관련 흐름이 실사용되지 않음
- `show_loading_screen()` 정의만 있고 실사용되지 않음
- `file_dialog` 변수는 있지만 실질적으로 사용되지 않음
- autosave 예시 파일은 있으나, 실제 autosave 로직은 분명하게 연결되어 있지 않음
- 노트 타입 편집 흐름 일부가 비어 있음

이 내용은 “현재 legacy가 이미 지원하는 기능”과 “새 editor에서 추가 개선 가능한 항목”을 구분할 때 중요하다.

---

## 9. 새 Editor로 옮길 때 반드시 보존해야 할 동작

아래는 단순히 “기능 이름”이 아니라 **실제 체감 동작** 기준의 보존 항목이다.

1. 파형 클릭으로 현재 시간 점프
2. 휠/단축키 기반 시간 이동
3. BPM + snap 기준 노트 배치 반올림
4. 레인 수 변경 시 즉시 편집 영역 재계산
5. 탭 노트 / 롱노트의 서로 다른 배치 방식
6. 우클릭 삭제의 시간 허용 오차 규칙
7. 재생 중 hitsound 발생 규칙
8. preroll 포함 재생 상태 전환
9. 노트 타입별 색상 / 롱노트 여부 / hitsound 여부
10. JSON 차트 호환성

---

## 10. 권장 마이그레이션 방향

현재 분석 기준으로는 **big-bang rewrite(한 번에 전부 갈아엎기)** 보다 아래 방향이 더 안전하다.

### 10.1 권장 방향

1. 현재 pygame editor를 **legacy editor**로 명시적으로 고정한다.
2. 새 editor는 **별도 앱**으로 시작한다.
3. 공통으로 써야 할 순수 로직은 점진적으로 `core` 성격의 모듈로 분리한다.
4. UI는 Qt 계열(`PySide6` 우선)로 새로 만든다.

### 10.2 왜 이런 방향이 좋은가

- 현재 코드는 pygame 중심 결합도가 너무 높다.
- 기존 앱을 직접 진화시키면 중간 상태가 쉽게 망가질 수 있다.
- 반대로 legacy를 기준 구현으로 남기면, 새 editor가 legacy와 비교되며 기능 누락 여부를 확인할 수 있다.

---

## 11. 새 Editor의 권장 초기 구조

아직 구현 전이지만, 현재 분석만 기준으로 보면 다음 분리가 적절하다.

### 11.1 Core

UI와 무관한 순수 로직

- 차트 데이터 모델
- 저장/불러오기
- 스냅 계산
- 노트 배치 규칙
- 롱노트 확정 규칙
- 삭제 판정 규칙
- parser/importer

### 11.2 Audio Service

- 곡 로드
- 현재 시간 조회
- play/pause/stop
- waveform 데이터 제공
- hitsound 재생

### 11.3 Editor View / UI

- 타임라인 표시
- 레인 표시
- 노트 표시
- 선택/편집 도구
- property panel
- transport controls

### 11.4 App Shell

- 파일 열기/저장
- 설정
- 플랫폼별 경로 처리
- 빌드/패키징

---

## 12. Qt 계열 선택에 대한 현재 판단

현재 목표가 다음과 같다면 Qt 계열이 적합하다.

- mac / linux / windows 대응
- 더 나은 데스크톱 UI
- 패널 기반 편집기 구조
- 속성 편집창, 리스트, 트리, 다이얼로그, 단축키 체계 강화

현재 시점에서는 **PySide6를 우선 후보**로 보는 것이 좋다.

이유:

- Qt 기반 데스크톱 툴 제작에 잘 맞는다.
- 패널형 에디터 UI를 만들기 쉽다.
- 추후 멀티플랫폼 앱 번들링 경로를 가져가기 좋다.

단, 중요한 점은 **Qt를 선택하는 것 자체가 문제 해결의 끝은 아니라는 것**이다.
진짜 어려운 부분은 UI 프레임워크 교체보다도, legacy의 편집 동작을 정확히 재현하는 데 있다.

---

## 13. 권장 개발 순서

### Phase 1. Legacy 동결 및 문서화

- 현재 editor를 legacy 기준 구현으로 고정
- 현재 문서처럼 기능/동작/구조를 계속 정리
- 기능 누락 체크리스트 작성

### Phase 2. Core 분리

- `ChartData`, `Note`, `NoteType` 정리
- 스냅/배치/삭제 규칙을 UI 밖으로 분리
- parser 및 chart 입출력 정리

### Phase 3. 새 Qt Editor 뼈대 작성

- 새 앱 창 구조
- 좌/중/우/하 패널 레이아웃
- 파일 열기/저장
- 차트 로드/표시

### Phase 4. 읽기 전용 미리보기

- waveform 표시
- 타임라인 표시
- 레인/노트 렌더링
- 재생 위치 커서 표시

### Phase 5. 편집 기능 이식

- 탭 노트 배치
- 롱노트 배치
- 삭제
- note type 관리
- BPM/offset/snap/lane 설정

### Phase 6. 빌드 / 문서 / 초보자 가이드 강화

- mac/linux/windows 빌드 가이드
- 기능별 설명 문서
- 프로젝트 구조 설명 문서

---

## 14. 지금 시점 결론

현재 legacy editor는 작아 보이지만, 실제로는 다음이 강하게 얽혀 있다.

- UI
- 입력
- 렌더링
- 시간 계산
- 오디오 재생
- hitsound 동작

그래서 새 editor 개발의 핵심은 “Qt로 바꾸는 것”보다 아래 두 가지다.

1. **legacy 동작을 정확히 문서화하고 기준을 고정하는 것**
2. **UI와 무관한 편집 규칙을 분리해서 재사용 가능한 core를 만드는 것**

즉, 가장 안전한 방향은 다음 한 줄로 요약된다.

> 현재 pygame editor는 legacy 기준 구현으로 보존하고, 새 editor는 PySide6 기반 별도 앱으로 시작하되, 공통 로직을 점진적으로 core로 분리한다.

---

## 15. 다음에 이어서 정리할 문서 후보

이 문서 다음으로 만들면 좋은 문서는 아래와 같다.

1. `legacy-feature-checklist.md`
   - 새 editor가 legacy와 동일 기능을 갖췄는지 체크하는 문서

2. `chart-format-spec.md`
   - 차트 JSON 구조를 정식 스펙으로 문서화

3. `new-editor-architecture.md`
   - 새 editor의 목표 구조와 모듈 책임 정의

4. `beginner-build-guide.md`
   - 초보자를 위한 실행/빌드 가이드
