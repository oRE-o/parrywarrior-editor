import json

# 사용자 정의 노트 타입
class NoteType:
    def __init__(self, name, color, is_long_note, play_hitsound):
        self.name = name            # 이름 (str)
        self.color = color          # 구별용 색깔 (e.g., (255, 0, 0))
        self.is_long_note = is_long_note  # 롱노트 가능 여부 (bool)
        self.play_hitsound = play_hitsound # 히트음 재생 여부 (bool)

# 개별 노트
class Note:
    def __init__(self, time_ms, note_type_name, lane, end_time_ms=None):
        self.time_ms = time_ms              # 시간 (int, 밀리초)
        self.note_type_name = note_type_name  # 노트 종류 이름 (str)
        self.lane = lane                    # 레인 (int, e.g., 0 ~ 3)
        self.end_time_ms = end_time_ms      # 롱노트 끝 시간 (int, 밀리초)

# 전체 채보 데이터
class ChartData:
    def __init__(self):
        self.song_path = ""
        self.chart_path = ""
        self.bpm = 120.0
        self.offset_ms = 0
        self.num_lanes = 4 # 기본 4레인
        self.notes: list[Note] = []
        
        # 기본 노트 타입 (나중에 UI로 편집 가능하게)
        self.note_types: dict[str, NoteType] = {
            "Tap": NoteType("Tap", (255, 80, 80), False, True),
            "Long": NoteType("Long", (80, 80, 255), True, True)
        }
        
        # [테스트용] 임시 노트를 추가합니다.
        # self.add_test_data()

    def add_test_data(self):
        # 1초, 2초, 3초, 4초에 탭 노트 추가
        for i in range(1, 5):
            self.notes.append(Note(i * 1000, "Tap", i % self.num_lanes))
        
        # 5초~6초 롱노트 추가
        self.notes.append(Note(5000, "Long", 0, end_time_ms=6000))
        print("테스트용 노트 5개 추가됨")


    def save_to_json(self, path):
        """
        현재 차트 데이터를 JSON 파일로 저장합니다.
        """
        # 1. 노트와 노트 타입을 '딕셔너리'로 변환
        notes_data = [vars(note) for note in self.notes]
        types_data = {name: vars(ntype) for name, ntype in self.note_types.items()}

        # 2. 저장할 전체 데이터
        full_data = {
            "song_path": self.song_path, # (참고용으로 저장)
            "bpm": self.bpm,
            "offset_ms": self.offset_ms,
            "num_lanes": self.num_lanes,
            "note_types": types_data,
            "notes": notes_data
        }

        # 3. JSON 파일로 저장
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4)
            print(f"차트 저장 완료: {path}")
        except Exception as e:
            print(f"차트 저장 실패: {e}")

    def load_from_json(self, path):
        """
        JSON 파일에서 차트 데이터를 불러옵니다.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 1. 기본 정보 불러오기
            self.bpm = data.get("bpm", 120.0)
            self.offset_ms = data.get("offset_ms", 0)
            self.num_lanes = data.get("num_lanes", 4)
            self.song_path = data.get("song_path", "")

            # 2. 노트 타입 불러오기 (기본값 포함)
            self.note_types.clear() # 기본 'Tap', 'Long' 지우기
            types_data = data.get("note_types", {})
            if not types_data: # 저장된 타입이 없으면 기본값 복구
                self.note_types["Tap"] = NoteType("Tap", (255, 80, 80), False, True)
                self.note_types["Long"] = NoteType("Long", (80, 80, 255), True, True)
            else:
                for name, nt_dict in types_data.items():
                    self.note_types[name] = NoteType(**nt_dict)

            # 3. 노트 리스트 불러오기 (기존 테스트 데이터 지우기)
            self.notes.clear() 
            for note_dict in data.get("notes", []):
                self.notes.append(Note(**note_dict))

            print(f"차트 불러오기 완료: {path}")
            return True

        except Exception as e:
            print(f"차트 불러오기 실패: {e}")
            return False