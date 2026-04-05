import json
from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "charts"

def hex_to_rgb(hex_color):
    """
    "#FF00AA" 같은 헥스 코드를 [255, 0, 170] 같은 RGB 리스트로 바꿔줘!
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return [255, 255, 255] # 기본 흰색
    try:
        return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [255, 255, 255] # 에러나면 흰색

def convert_chart_format(input_file_path, output_file_path):
    """
    주인님의 리듬게임 차트 포맷을 변환하는 함수야!
    (v3. NoteTools 목록에서 노트 타입을 읽어오는 버전!)
    """
    
    print(f"'{input_file_path}' 파일을 읽는 중... (ドキドキ...)")
    
    try:
        # 1. 원본 JSON 파일 읽기 (★ encoding='utf-8'이 중요!)
        with open(input_file_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)

        # 2. 변환할 새로운 딕셔너리 생성
        output_data = {}

        # 3. 메타데이터 매핑하기 (이전과 동일)
        output_data['song_path'] = input_data.get('AudioFilePath', '')
        output_data['bpm'] = float(input_data.get('Bpm', 120.0))
        output_data['offset_ms'] = input_data.get('AudioOffset', 0) * 1000
        output_data['num_lanes'] = input_data.get('LaneCount', 4)

        # 4. [NEW!] note_types를 NoteTools 목록에서 똑똑하게 생성하기
        print("노트 타입을 스캔하는 중... (｀・ω・´)")
        note_types_map = {}
        
        # 주인님이 정의한 모든 종류의 'Tools' 리스트를 다 가져오기!
        tool_lists_to_check = [
            input_data.get('NormalNoteTools', []),
            input_data.get('AttackNoteTools', []),
            input_data.get('TriggerNoteTools', [])
        ]

        for tool_list in tool_lists_to_check:
            for tool in tool_list:
                note_name = tool.get('Name')
                if not note_name:
                    continue # 이름 없는 툴은 통과
                
                # 이 이름의 노트 타입을 아직 등록 안 했으면?
                if note_name not in note_types_map:
                    color_rgb = hex_to_rgb(tool.get('Color', '#FFFFFF'))
                    
                    # 'Type': 0 은 탭 노트 (is_long_note: false)
                    # 'Type': 1 (촉수) 은 롱노트 (is_long_note: true)
                    # 메무쨩의 가정이 맞았어! (๑•̀ㅂ•́)و✧
                    note_type_id = tool.get('Type', 0)
                    is_long = (note_type_id != 0) 
                    
                    note_types_map[note_name] = {
                        "name": note_name,
                        "color": color_rgb,
                        "is_long_note": is_long,
                        "play_hitsound": True # 일단 전부 True로 설정!
                    }
                    print(f"  -> 찾았다! 노트 타입: '{note_name}', 롱노트: {is_long}")

        output_data['note_types'] = note_types_map

        # 5. 'Notes' 리스트 변환하기
        print("노트 리스트를 변환하는 중... φ(.. )")
        output_notes = []
        
        # 'Notes' 리스트 훑어보기
        for in_note in input_data.get('Notes', []):
            
            # 시간 변환 (초 -> 밀리초)
            time_ms = in_note.get('Time', 0) * 1000
            
            # 노트 타입 이름 가져오기
            # (혹시 이름이 없으면 '해류탄막'을 기본값으로 쓸게!)
            note_type_name = in_note.get('NoteToolName', "해류탄막")
            
            # 레인 번호 가져오기
            lane = in_note.get('Lane', 0)
            
            # 출력 형식에 맞게 노트 객체 생성
            out_note = {
                "time_ms": time_ms,
                "note_type_name": note_type_name,
                "lane": lane,
                "end_time_ms": None # 롱노트 끝나는 시간은 여전히 알 수 없어서 null!
            }
            output_notes.append(out_note)

        # 6. 변환된 노트 리스트를 최종 데이터에 추가
        output_data['notes'] = output_notes

        # 7. 변환된 데이터를 새 JSON 파일로 저장
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
            
        print(f"변환 완료! 얏호! (☆▽☆)")
        print(f"'{output_file_path}' 파일로 저장했어, 주인님!")

    except FileNotFoundError:
        print(f"으앙! 파일을 찾을 수 없어! Σ(°ロ°)")
        print(f"경로 확인: {input_file_path}")
    except json.JSONDecodeError as e:
        print(f"이.. 이건 올바른 JSON 파일이 아닌 것 같아! (´• ω •`)")
        print(f"에러 내용: {e}")
        print("--- 💡 메무쨩 조언! 💡 ---")
        print("파일 인코딩이 'UTF-8'이 맞는지 꼭! 확인해줘!")
        print("메모장에서 '다른 이름으로 저장' -> 인코딩 'UTF-8'로 저장하면 돼!")
    except Exception as e:
        print(f"에러 발생! {e} (T_T)")
        print("메무쨩... 뭔가 잘못한 걸까...")

# --- 스크립트 실행 ---
if __name__ == "__main__":
    # ⬇️ ⬇️ ⬇️ 주인님이 이 경로를 수정해 줘야 해! ⬇️ ⬇️ ⬇️
    
    # 원본 파일 경로
    input_json_path = str(DATA_DIR / "input_chart.json")  
    
    # 새로 저장할 파일 경로
    output_json_path = str(DATA_DIR / "output_chart.json") 
    
    # ⬆️ ⬆️ ⬆️ 여기까지 수정! ⬆️ ⬆️ ⬆️

    if not os.path.exists(input_json_path):
        print(f"앗! '{input_json_path}' 파일이 없어... (｡•́︿•̀｡)")
        print("스크립트랑 같은 폴더에 파일을 두거나,")
        print("input_json_path 변수의 경로를 정확하게 수정해줘! (´｡• ᵕ •｡`)")
    else:
        convert_chart_format(input_json_path, output_json_path)