import os
import sys
import math
import pygame
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
pygame.init()
pygame.mixer.init() # <-- 2. 이 주석을 꼭 풀어주세요.

import pygame_gui
from pygame_gui.elements import UIPanel, UIButton, UILabel, UIHorizontalSlider, UIDropDownMenu, UITextEntryLine, UICheckBox
from pygame_gui.windows import UIFileDialog
from pygame_gui.windows.ui_colour_picker_dialog import UIColourPickerDialog
from pygame_gui.elements.ui_selection_list import UISelectionList
# [추가] 새 이벤트 타입 임포트

import audio_manager
import chart
import editor_canvas

ROOT_DIR = Path(__file__).resolve().parent.parent

def _is_frozen():
    return getattr(sys, "frozen", False)

def _get_base_dir():
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", ROOT_DIR))
    return ROOT_DIR

def _get_user_data_dir():
    if not _is_frozen():
        return ROOT_DIR / "data"
    if os.name == "nt":
        base = Path(os.getenv("APPDATA") or Path.home())
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "python-rhythm-editor"

BASE_DIR = _get_base_dir()
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = _get_user_data_dir()
CHARTS_DIR = DATA_DIR / "charts"
HITSOUND_PATH = ASSETS_DIR / "hitsound.wav"
FFMPEG_DIR = BASE_DIR / "tools" / "ffmpeg"

def _ensure_ffmpeg_on_path():
    if not FFMPEG_DIR.exists():
        return
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
    if os.name == "nt":
        try:
            os.add_dll_directory(str(FFMPEG_DIR))
        except Exception:
            pass

_ensure_ffmpeg_on_path()

def _pick_file_dialog(title, initial_dir, filetypes):
    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.askopenfilename(title=title, initialdir=initial_dir, filetypes=filetypes)
    finally:
        root.destroy()

def _save_file_dialog(title, initial_path, filetypes):
    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.asksaveasfilename(title=title, initialdir=str(Path(initial_path).parent), initialfile=Path(initial_path).name, filetypes=filetypes, defaultextension=filetypes[0][1].replace('*', '').split()[0])
    finally:
        root.destroy()

def _load_song_from_path(song_path):
    global total_time_ms, current_audio_time_ms, last_played_note_time_ms
    global is_prerolling, preroll_start_tick, preroll_start_audio_time_ms
    if audio_manager.load_song(song_path):
        total_time_ms = audio_manager.get_length_ms()
        current_audio_time_ms = 0.0
        last_played_note_time_ms = current_audio_time_ms + current_chart.offset_ms
        is_prerolling = False
        preroll_start_tick = 0
        preroll_start_audio_time_ms = 0.0
        song_name_label.set_text(song_path.split('/')[-1].split('\\')[-1])
        current_chart.song_path = song_path
    else:
        song_name_label.set_text('Load Failed!')

def _load_chart_from_path(chart_path):
    if current_chart.load_from_json(chart_path):
        bpm_entry.set_text(str(current_chart.bpm))
        offset_entry.set_text(str(current_chart.offset_ms))
        lane_dropdown.set_text(str(current_chart.num_lanes))
        new_item_list = list(current_chart.note_types.keys())
        note_type_list.set_item_list(new_item_list)
        if current_chart.song_path:
            song_name_label.set_text(current_chart.song_path.split('/')[-1].split('\\')[-1])
        else:
            song_name_label.set_text('No song loaded.')
    else:
        print('?? ???? ?? (?? ??)')

def _start_playback_from_current_time():
    global current_audio_time_ms
    global is_prerolling, preroll_start_tick, preroll_start_audio_time_ms

    if current_audio_time_ms < 0:
        audio_manager.stop()
        is_prerolling = True
        preroll_start_tick = pygame.time.get_ticks()
        preroll_start_audio_time_ms = current_audio_time_ms
    else:
        is_prerolling = False
        audio_manager.play(current_audio_time_ms)

def _pause_playback():
    global current_audio_time_ms
    global is_prerolling, preroll_start_tick, preroll_start_audio_time_ms

    if is_prerolling:
        elapsed = pygame.time.get_ticks() - preroll_start_tick
        current_audio_time_ms = preroll_start_audio_time_ms + elapsed
        is_prerolling = False
        return

    if audio_manager.is_playing:
        audio_manager.pause()
        current_audio_time_ms = audio_manager.get_pos_ms()

def _stop_playback():
    global current_audio_time_ms
    global is_prerolling, preroll_start_tick, preroll_start_audio_time_ms

    is_prerolling = False
    preroll_start_tick = 0
    preroll_start_audio_time_ms = 0.0
    audio_manager.stop()
    current_audio_time_ms = 0.0

def _round_to_nearest_snap_index(value):
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)



SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Rhythm Editor")
clock = pygame.time.Clock()
editor_canvas.init_font() # <-- 이쪽으로 (manager 생성 이후) 옮겨주세요!
manager = pygame_gui.UIManager((SCREEN_WIDTH, SCREEN_HEIGHT))
audio_manager.load_hitsound(str(HITSOUND_PATH))

# --- 2. UI 레이아웃 정의 (동일) ---
BOTTOM_PANEL_HEIGHT = 60
LEFT_PANEL_WIDTH = 200
RIGHT_PANEL_WIDTH = 250

bottom_panel_rect = pygame.Rect(0, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT, SCREEN_WIDTH, BOTTOM_PANEL_HEIGHT)
bottom_panel = UIPanel(relative_rect=bottom_panel_rect, starting_height=1, manager=manager)

left_panel_rect = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)

right_panel_rect = pygame.Rect(SCREEN_WIDTH - RIGHT_PANEL_WIDTH, 0, RIGHT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)
right_panel = UIPanel(relative_rect=right_panel_rect, starting_height=1, manager=manager)

EDITOR_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)

# --- 3. UI 요소(위젯) 생성 (수정) ---
current_chart = chart.ChartData()
# 아래쪽 패널
# [수정] Play/Pause 토글 버튼으로 변경
play_pause_button = UIButton(
    relative_rect=pygame.Rect(-50, 0, 80, 40),
    text='Play',
    manager=manager,
    container=bottom_panel,
    anchors={'centerx': 'centerx', 'centery': 'centery'}
)

stop_button = UIButton(
    relative_rect=pygame.Rect(50, 0, 80, 40),
    text='Stop',
    manager=manager,
    container=bottom_panel,
    anchors={'centerx': 'centerx', 'centery': 'centery'}
)

time_label = UILabel(
    relative_rect=pygame.Rect(-160, 0, 110, 40),
    text='0.000 / 0.000',
    manager=manager,
    container=bottom_panel,
    anchors={'center': 'center'}
)

load_song_button = UIButton(relative_rect=pygame.Rect(10, 10, 230, 40), text='Load Song', manager=manager, container=right_panel)
song_name_label = UILabel(relative_rect=pygame.Rect(10, 60, 230, 30), text='No song loaded.', manager=manager, container=right_panel)

save_chart_button = UIButton(relative_rect=pygame.Rect(10, 100, 110, 30), text='Save Chart', manager=manager, container=right_panel)
load_chart_button = UIButton(relative_rect=pygame.Rect(130, 100, 110, 30), text='Load Chart', manager=manager, container=right_panel)

bpm_label = UILabel(relative_rect=pygame.Rect(10, 140, 50, 30), text='BPM:', manager=manager, container=right_panel)
bpm_entry = UITextEntryLine(relative_rect=pygame.Rect(70, 140, 170, 30), manager=manager, container=right_panel)
bpm_entry.set_text(str(current_chart.bpm)) # UI에 현재 BPM 표시


offset_label = UILabel(relative_rect=pygame.Rect(10, 180, 60, 30), text='Offset(ms):', manager=manager, container=right_panel)
offset_entry = UITextEntryLine(relative_rect=pygame.Rect(80, 180, 160, 30), manager=manager, container=right_panel)
offset_entry.set_text(str(current_chart.offset_ms)) # UI에 현재 Offset 표시

zoom_label = UILabel(relative_rect=pygame.Rect(10, 220, 230, 30), text='Zoom (Scroll Speed)', manager=manager, container=right_panel)
scale_slider = UIHorizontalSlider(relative_rect=pygame.Rect(10, 250, 230, 30), start_value=0.5, value_range=(0.05, 2.0), manager=manager, container=right_panel)

# (Y좌표 120 -> 210 으로 변경)
snap_label = UILabel(relative_rect=pygame.Rect(10, 290, 230, 30), text='Snap Division', manager=manager, container=right_panel)
snap_options = ["4", "8", "12", "16", "24", "32"]
snap_dropdown = UIDropDownMenu(options_list=snap_options, starting_option="16", relative_rect=pygame.Rect(10, 320, 230, 40), manager=manager, container=right_panel)

lane_label = UILabel(relative_rect=pygame.Rect(10, 330, 230, 30), text='Number of Lanes (3-7)', manager=manager, container=right_panel)
lane_options = ["3", "4", "5", "6", "7"]
lane_dropdown = UIDropDownMenu(options_list=lane_options,
                               starting_option=str(current_chart.num_lanes), # 기본값 4
                               relative_rect=pygame.Rect(10, 360, 230, 40),
                               manager=manager,
                               container=right_panel)

# (Y좌표 수정: 370~: 노트 타입)
note_type_label = UILabel(relative_rect=pygame.Rect(10, 410, 230, 30), text='Note Type', manager=manager, container=right_panel)
note_type_names = list(current_chart.note_types.keys())
note_type_list = UISelectionList(relative_rect=pygame.Rect(10, 440, 230, 100), item_list=note_type_names, manager=manager, container=right_panel)

new_note_type_button = UIButton(relative_rect=pygame.Rect(10, 530, 110, 40), 
                                text='[+] New',
                                manager=manager,
                                container=right_panel)

edit_note_type_button = UIButton(relative_rect=pygame.Rect(130, 530, 110, 40), 
                                 text='[Edit Selected]',
                                 manager=manager,
                                 container=right_panel)
edit_note_type_button.disable() # (아무것도 선택 안 됐으니 일단 비활성화)
editor_title = UILabel(relative_rect=pygame.Rect(10, 10, 230, 30), text='New Note Type', manager=manager, container=right_panel)
editor_name_label = UILabel(relative_rect=pygame.Rect(10, 60, 100, 30), text='Name:', manager=manager, container=right_panel) 
editor_name_entry = UITextEntryLine(relative_rect=pygame.Rect(120, 60, 110, 30), manager=manager, container=right_panel)
editor_color_label = UILabel(relative_rect=pygame.Rect(10, 110, 100, 30), text='Color:', manager=manager, container=right_panel) 
editor_color_button = UIButton(relative_rect=pygame.Rect(120, 110, 110, 30), text='Pick Color', manager=manager, container=right_panel)

PRESET_COLORS = [
    (255, 80, 80), (80, 255, 80), (80, 80, 255), (255, 255, 80), # R, G, B, Yellow
    (80, 255, 255), (255, 80, 255), (200, 200, 200), (255, 150, 80) # Cyan, Magenta, Whiteish, Orange
]
editor_preset_buttons = []
btn_size, btn_margin = 50, 7 # (버튼 4개 너비: 50*4 + 7*3 = 221px. OK)

y_pos = 150
for i in range(4):
    x_pos = 10 + i * (btn_size + btn_margin)
    btn = UIButton(relative_rect=pygame.Rect(x_pos, y_pos, btn_size, 30), text='', manager=manager, container=right_panel)
    # 버튼 배경색을 프리셋 색깔로
    btn.colours['normal_bg'] = pygame.Color(PRESET_COLORS[i])
    btn.rebuild()
    editor_preset_buttons.append(btn)

# Row 2 (Y = 150 + 30 + 5 = 185)
y_pos = 185
for i in range(4):
    x_pos = 10 + i * (btn_size + btn_margin)
    btn = UIButton(relative_rect=pygame.Rect(x_pos, y_pos, btn_size, 30), text='', manager=manager, container=right_panel)
    # 버튼 배경색을 프리셋 색깔로
    btn.colours['normal_bg'] = pygame.Color(PRESET_COLORS[i+4])
    btn.rebuild()
    editor_preset_buttons.append(btn)


btn_size, btn_margin = 50, 7 # (버튼 4개 너비: 50*4 + 7*3 = 221px. OK)
editor_is_long_check = UICheckBox(relative_rect=pygame.Rect(10, 235, 100, 30), text='Is Long Note?', initial_state=False, manager=manager, container=right_panel)
editor_hitsound_check = UICheckBox(relative_rect=pygame.Rect(10, 275, 100, 30), text='Play Hitsound?', initial_state=True, manager=manager, container=right_panel)
editor_cancel_button = UIButton(relative_rect=pygame.Rect(10, 325, 110, 40), text='Cancel', manager=manager, container=right_panel)
editor_ok_button = UIButton(relative_rect=pygame.Rect(130, 325, 100, 40), text='OK', manager=manager, container=right_panel)
# [추가] UI 그룹화
default_ui_elements = [
    load_song_button, song_name_label, 
    save_chart_button, load_chart_button, bpm_label, bpm_entry, 
    offset_label, offset_entry,
    zoom_label, scale_slider, 
    snap_label, snap_dropdown, 
    lane_label, lane_dropdown, 
    note_type_label, note_type_list, 
    new_note_type_button,
    edit_note_type_button # <-- 이 줄을 추가!
]
editor_ui_elements = [
    editor_title, editor_name_label, editor_name_entry, 
    editor_color_label, editor_color_button, 
    editor_is_long_check, editor_hitsound_check, 
    editor_cancel_button, editor_ok_button,
    editor_name_label, editor_color_label
]
# [수정!] 1. 프리셋 버튼 8개를 리스트에 '먼저' 추가하고
editor_ui_elements.extend(editor_preset_buttons)

# [수정!] 2. '그 다음에' 리스트 전체를 숨겨주세요!
for element in editor_ui_elements:
    element.hide()

def is_text_input_focused():
    focus_set = manager.get_focus_set()
    if focus_set is None:
        return False
    return any(elem in focus_set for elem in (bpm_entry, offset_entry))

def show_loading_screen(manager, screen_rect):
    loading_window = pygame_gui.windows.UIWindow(
        rect=pygame.Rect((screen_rect.centerx-150, screen_rect.centery-50), (300, 100)),
        manager=manager,
        window_title='Loading',
        object_id='#loading_window'
    )
    loading_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((20,20), (260, 60)),
        text='Loading song, please wait...',
        manager=manager,
        container=loading_window
    )
    return loading_window


pending_long_note_start = None
last_played_note_time_ms = 0.0

# [추가] 노트 에디터용 변수
color_picker = None
editor_selected_color = (255, 255, 255) # 기본 흰색
editor_mode = "new" # <-- [신규!] 'new' 또는 'edit' 모드
editing_note_name = None # <-- [신규!] 지금 편집 중인 노트 이름

# --- [추가] 4. 에디터 상태 변수 ---
current_audio_time_ms = 0.0
total_time_ms = 0.0
file_dialog = None # 파일 대화상자 객체

# 프리롤(0ms 이전) 재생 상태
is_prerolling = False
preroll_start_tick = 0
preroll_start_audio_time_ms = 0.0

scale_pixels_per_ms = 0.5
judgement_line_y = EDITOR_RECT.height * 0.8

# [추가] 현재 스냅 설정
current_snap_division = 16
# [추가] 현재 선택된 노트 타입 (임시)

current_note_type_name = note_type_names[0] if note_type_names else None
DELETE_TIME_TOLERANCE_MS = 50

# [추가] 롱노트 배치를 위한 에디터 상태
STATE_IDLE = 0            # 기본 상태
STATE_PLACING_LONG = 1    # 롱노트의 끝점을 기다리는 상태
editor_state = STATE_IDLE

# [추가] 롱노트 시작점 정보 임시 저장
pending_long_note_start = None # e.g., {"time_ms": 1000, "lane": 0, "type_name": "Long"}
last_played_note_time_ms = 0.0

LANE_WIDTH_PIXELS = 60


# --- 5. 메인 루프 ---
running = True
while running:
    time_delta = clock.tick(60) / 1000.0

    # (1) 이벤트 처리
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        manager.process_events(event)
        # [수정] pygame-gui 이벤트 처리
        if event.type == pygame.VIDEORESIZE:
            # 1. 새 크기로 스크린 변수 업데이트
            SCREEN_WIDTH = event.w
            SCREEN_HEIGHT = event.h
            # 2. Pygame 스크린 다시 만들기
            manager.set_window_resolution((SCREEN_WIDTH, SCREEN_HEIGHT)) # <-- 이걸로 수정!
            
            # 4. [수정!] 모든 UI 위치/크기 '수동'으로 다시 계산
            
            # (1) 아래쪽 패널 (Bottom Panel)
            bottom_panel_rect = pygame.Rect(0, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT, SCREEN_WIDTH, BOTTOM_PANEL_HEIGHT)
            bottom_panel.set_dimensions((SCREEN_WIDTH, BOTTOM_PANEL_HEIGHT))
            bottom_panel.set_position((0, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT))
            
            # (2) 오른쪽 패널 (Right Panel)
            right_panel_rect = pygame.Rect(SCREEN_WIDTH - RIGHT_PANEL_WIDTH, 0, RIGHT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)
            right_panel.set_dimensions((RIGHT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT))
            right_panel.set_position((SCREEN_WIDTH - RIGHT_PANEL_WIDTH, 0))

            # (3) 왼쪽 패널 (Left Panel - Rect만)
            left_panel_rect = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)
            
            # (4) 가운데 캔버스 (Editor Rect)
            EDITOR_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, SCREEN_WIDTH - LEFT_PANEL_WIDTH - RIGHT_PANEL_WIDTH, SCREEN_HEIGHT - BOTTOM_PANEL_HEIGHT)
            
            # (5) 판정선 Y좌표
            judgement_line_y = EDITOR_RECT.height * 0.8

        if event.type == pygame.MOUSEWHEEL:
            # [수정] GUI가 마우스를 쓰고 있지 '않을' 때만 캔버스 스크롤
            if EDITOR_RECT.collidepoint(pygame.mouse.get_pos()):
                if not audio_manager.is_playing and not is_prerolling:
                    
                    # 1. Alt 키가 눌렸는지 확인
                    keys = pygame.key.get_pressed()
                    is_alt_pressed = keys[pygame.K_LALT] or keys[pygame.K_RALT]
                    
                    is_ctrl_pressed = keys[pygame.K_LCTRL]

                    # 2. 기본 스크롤 속도
                    base_scroll_speed = (1000.0 / scale_pixels_per_ms) * 0.1
                    
                    # 3. [수정] event.y를 그대로 사용해서 방향 반전 (1: 미래, -1: 과거)
                    scroll_amount_ms = event.y * base_scroll_speed 

                    # 4. Alt 키 눌렀으면 1/10로 느리게
                    if is_alt_pressed:
                        scroll_amount_ms *= 0.1 # 10배 느리게

                    if is_ctrl_pressed:
                        scroll_amount_ms *= 6 

                    # 5. [수정] -= 를 += 로 변경
                    current_audio_time_ms += scroll_amount_ms 
        if event.type == pygame.KEYDOWN:
            # 2. 텍스트 입력 중이 '아닐' 때만 단축키 작동
            if not is_text_input_focused():
                if event.key == pygame.K_SPACE:
                    if audio_manager.is_playing or is_prerolling:
                        _pause_playback()
                        play_pause_button.set_text('Play')
                    else:
                        _start_playback_from_current_time()
                        play_pause_button.set_text('Pause')

                # [??!] ?/?? = 1ms ??? (?? ? ?? ??)
                if not audio_manager.is_playing and not is_prerolling:
                    if event.key == pygame.K_UP:
                        current_audio_time_ms += 1.0
                    if event.key == pygame.K_DOWN:
                        current_audio_time_ms -= 1.0
                # [신규!] 스페이스바 = 재생/일시정지
        if event.type == pygame.MOUSEBUTTONDOWN:
            if manager.get_hovering_any_element():
                continue
            if left_panel_rect.collidepoint(event.pos):
                if event.button == 1:
                    judgement_line_y_ratio = judgement_line_y / EDITOR_RECT.height
                    judgement_line_y_in_wave_panel = left_panel_rect.top + (judgement_line_y_ratio * left_panel_rect.height)
                    new_audio_time_ms = editor_canvas.screen_y_to_time(
                        event.pos[1],
                        current_audio_time_ms,
                        scale_pixels_per_ms,
                        judgement_line_y_in_wave_panel
                    )
                    current_audio_time_ms = new_audio_time_ms
                    last_played_note_time_ms = current_audio_time_ms + current_chart.offset_ms
                    if audio_manager.is_playing or is_prerolling:
                        audio_manager.stop()
                        is_prerolling = False
                        preroll_start_tick = 0
                        preroll_start_audio_time_ms = 0.0
                        if current_audio_time_ms < 0:
                            is_prerolling = True
                            preroll_start_tick = pygame.time.get_ticks()
                            preroll_start_audio_time_ms = current_audio_time_ms
                        else:
                            audio_manager.play(current_audio_time_ms)
                        play_pause_button.set_text('Pause')
                continue
            if EDITOR_RECT.collidepoint(event.pos):
                num_lanes = current_chart.num_lanes or 1
                total_lanes_width = num_lanes * LANE_WIDTH_PIXELS
                start_x_abs = EDITOR_RECT.left + (EDITOR_RECT.width - total_lanes_width) / 2
                end_x_abs = start_x_abs + total_lanes_width
                if start_x_abs <= event.pos[0] < end_x_abs:
                    mouse_x_in_lanes = event.pos[0] - start_x_abs
                    lane = int(mouse_x_in_lanes // LANE_WIDTH_PIXELS)
                    current_note_time_ms = current_audio_time_ms + current_chart.offset_ms
                    raw_time_ms = editor_canvas.screen_y_to_time(
                        event.pos[1],
                        current_note_time_ms,
                        scale_pixels_per_ms,
                        judgement_line_y
                    )
                    beat_ms = 60000.0 / current_chart.bpm if current_chart.bpm > 0 else 500.0
                    snap_div = current_snap_division or 1
                    snap_ms = beat_ms / (snap_div / 4.0)
                    time_before_snapping = raw_time_ms
                    snap_ratio = time_before_snapping / snap_ms
                    snapped_time_ms = _round_to_nearest_snap_index(snap_ratio) * snap_ms

                    if event.button == 1:
                        if editor_state == STATE_IDLE:
                            is_occupied = False
                            for note in current_chart.notes:
                                if note.lane == lane:
                                    if note.time_ms == snapped_time_ms:
                                        is_occupied = True
                                        break
                                    if note.end_time_ms and note.time_ms < snapped_time_ms < note.end_time_ms:
                                        is_occupied = True
                                        break
                            if not is_occupied and current_note_type_name:
                                note_type = current_chart.note_types.get(current_note_type_name)
                                if note_type:
                                    if note_type.is_long_note:
                                        pending_long_note_start = {
                                            'time_ms': snapped_time_ms,
                                            'lane': lane,
                                            'type_name': current_note_type_name
                                        }
                                        editor_state = STATE_PLACING_LONG
                                    else:
                                        current_chart.notes.append(chart.Note(snapped_time_ms, current_note_type_name, lane))
                        elif editor_state == STATE_PLACING_LONG:
                            if lane == pending_long_note_start['lane']:
                                start_time = pending_long_note_start['time_ms']
                                end_time = snapped_time_ms
                                if end_time < start_time:
                                    start_time, end_time = end_time, start_time
                                if end_time == start_time:
                                    new_note = chart.Note(start_time, pending_long_note_start['type_name'], lane)
                                else:
                                    new_note = chart.Note(start_time, pending_long_note_start['type_name'], lane, end_time_ms=end_time)
                                current_chart.notes.append(new_note)
                            editor_state = STATE_IDLE
                            pending_long_note_start = None

                    if event.button == 3:
                        if editor_state == STATE_PLACING_LONG:
                            editor_state = STATE_IDLE
                            pending_long_note_start = None
                        else:
                            note_to_delete = None
                            for note in reversed(current_chart.notes):
                                if note.lane == lane:
                                    if note.end_time_ms:
                                        if (note.time_ms - DELETE_TIME_TOLERANCE_MS) <= raw_time_ms <= (note.end_time_ms + DELETE_TIME_TOLERANCE_MS):
                                            note_to_delete = note
                                            break
                                    else:
                                        if abs(note.time_ms - raw_time_ms) < DELETE_TIME_TOLERANCE_MS:
                                            note_to_delete = note
                                            break
                            if note_to_delete:
                                current_chart.notes.remove(note_to_delete)

        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == play_pause_button:
                if audio_manager.is_playing or is_prerolling:
                    _pause_playback()
                    play_pause_button.set_text('Play')
                else:
                    _start_playback_from_current_time()
                    play_pause_button.set_text('Pause')

            if event.ui_element == stop_button:
                _stop_playback()
                play_pause_button.set_text('Play')

            if event.ui_element == load_song_button:
                audio_types = [("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus *.aiff *.aif *.wma"), ("All Files", "*.*")]
                picked = _pick_file_dialog('Open Song File...', str(DATA_DIR), audio_types)
                if picked:
                    _load_song_from_path(picked)

            if event.ui_element == save_chart_button:
                import os
                default_name = os.path.splitext(os.path.basename(current_chart.song_path or "untitled"))[0] + "_chart.json"
                CHARTS_DIR.mkdir(parents=True, exist_ok=True)
                initial_path = str(CHARTS_DIR / default_name)
                chart_types = [("Chart Files", "*.json"), ("All Files", "*.*")]
                picked = _save_file_dialog('Save Chart As...', initial_path, chart_types)
                if picked:
                    current_chart.save_to_json(picked)

            if event.ui_element == load_chart_button:
                chart_types = [("Chart Files", "*.json"), ("All Files", "*.*")]
                picked = _pick_file_dialog('Open Chart File...', str(CHARTS_DIR), chart_types)
                if picked:
                    _load_chart_from_path(picked)

            if event.ui_element == new_note_type_button:
                editor_mode = 'new'
                for element in default_ui_elements:
                    element.hide()
                for element in editor_ui_elements:
                    element.show()
                editor_title.set_text('New Note Type')
                editor_name_entry.set_text('')
                editor_name_entry.enable()
                editor_selected_color = (255, 255, 255)
                editor_color_button.colours['normal_bg'] = pygame.Color(editor_selected_color)
                editor_color_button.rebuild()
                editor_is_long_check.set_state(False)
                editor_hitsound_check.set_state(True)

            if event.ui_element == edit_note_type_button:
                if editing_note_name is None:
                    pass
                else:
                    editor_mode = 'edit'
                    for element in default_ui_elements:
                        element.hide()
                    for element in editor_ui_elements:
                        element.show()
                    note_to_edit = current_chart.note_types[editing_note_name]
                    editor_title.set_text('Edit: ' + note_to_edit.name)
                    editor_name_entry.set_text(note_to_edit.name)
                    editor_name_entry.disable()
                    editor_selected_color = note_to_edit.color
                    editor_color_button.colours['normal_bg'] = pygame.Color(note_to_edit.color)
                    editor_color_button.rebuild()
                    editor_is_long_check.set_state(note_to_edit.is_long_note)
                    editor_hitsound_check.set_state(note_to_edit.play_hitsound)

            if event.ui_element == editor_cancel_button:
                for element in editor_ui_elements:
                    element.hide()
                for element in default_ui_elements:
                    element.show()

            if event.ui_element == editor_ok_button:
                if editor_mode == 'new':
                    new_name = editor_name_entry.get_text()
                    if not new_name:
                        print('??: ?? ??? ????')
                    elif new_name in current_chart.note_types:
                        print('??: ' + new_name + ' ??? ?? ???')
                    else:
                        new_type = chart.NoteType(
                            name=new_name,
                            color=editor_selected_color,
                            is_long_note=editor_is_long_check.is_checked,
                            play_hitsound=editor_hitsound_check.is_checked
                        )
                        current_chart.note_types[new_name] = new_type
                        note_type_list.set_item_list(list(current_chart.note_types.keys()))
                        for element in editor_ui_elements:
                            element.hide()
                        for element in default_ui_elements:
                            element.show()
                elif editor_mode == 'edit':
                    note_to_edit = current_chart.note_types[editing_note_name]
                    note_to_edit.color = editor_selected_color
                    note_to_edit.is_long_note = editor_is_long_check.is_checked
                    note_to_edit.play_hitsound = editor_hitsound_check.is_checked
                    for element in editor_ui_elements:
                        element.hide()
                    for element in default_ui_elements:
                        element.show()

            if event.ui_element == editor_color_button:
                if color_picker:
                    color_picker.kill()
                color_picker = UIColourPickerDialog(pygame.Rect(100, 100, 300, 300),
                                                   manager,
                                                   window_title='Pick a color...')
                editor_color_button.disable()

            for i, preset_btn in enumerate(editor_preset_buttons):
                if event.ui_element == preset_btn:
                    editor_selected_color = PRESET_COLORS[i]
                    color_obj = pygame.Color(editor_selected_color)
                    editor_color_button.colours['normal_bg'] = color_obj
                    editor_color_button.rebuild()
                    break

        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == scale_slider:
                scale_pixels_per_ms = event.value

        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == snap_dropdown:
                current_snap_division = int(event.text)
            elif event.ui_element == lane_dropdown:
                current_chart.num_lanes = int(event.text)

        if event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element == note_type_list:
                current_note_type_name = event.text
                editing_note_name = event.text
                edit_note_type_button.enable()

        if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
            if event.ui_element == bpm_entry:
                try:
                    new_bpm = float(event.text)
                    if new_bpm > 0:
                        current_chart.bpm = new_bpm
                    else:
                        bpm_entry.set_text(str(current_chart.bpm))
                except ValueError:
                    bpm_entry.set_text(str(current_chart.bpm))
            if event.ui_element == offset_entry:
                try:
                    new_offset = int(event.text)
                    current_chart.offset_ms = new_offset
                    last_played_note_time_ms = current_audio_time_ms + current_chart.offset_ms
                except ValueError:
                    offset_entry.set_text(str(current_chart.offset_ms))

        if event.type == pygame_gui.UI_COLOUR_PICKER_COLOUR_PICKED:
            if event.ui_element == color_picker:
                editor_selected_color = (event.colour.r, event.colour.g, event.colour.b)
                editor_color_button.colours['normal_bg'] = event.colour
                editor_color_button.rebuild()
                editor_color_button.enable()
                color_picker = None

        if event.type == pygame_gui.UI_WINDOW_CLOSE:
            if event.ui_element == color_picker:
                editor_color_button.enable()
                color_picker = None

    manager.update(time_delta)

    if audio_manager.is_playing or is_prerolling:
        if is_prerolling:
            elapsed = pygame.time.get_ticks() - preroll_start_tick
            current_audio_time_ms = preroll_start_audio_time_ms + elapsed
            if current_audio_time_ms >= 0:
                is_prerolling = False
                preroll_start_tick = 0
                preroll_start_audio_time_ms = 0.0
                audio_manager.play(0)
                current_audio_time_ms = 0.0
        else:
            current_audio_time_ms = audio_manager.get_pos_ms()

        hitsound_times_in_this_frame = set()
        current_note_time_ms = current_audio_time_ms + current_chart.offset_ms

        for note in current_chart.notes:
            note_type = current_chart.note_types.get(note.note_type_name)
            if not (note_type and note_type.play_hitsound):
                continue

            note_time_ms = note.time_ms
            if note_time_ms > last_played_note_time_ms and note_time_ms <= current_note_time_ms:
                hitsound_times_in_this_frame.add(note_time_ms)

            if note.end_time_ms:
                note_end_time_ms = note.end_time_ms
                if note_end_time_ms > last_played_note_time_ms and note_end_time_ms <= current_note_time_ms:
                    hitsound_times_in_this_frame.add(note_end_time_ms)

        if len(hitsound_times_in_this_frame) > 0:
            audio_manager.play_hitsound()

        if not is_prerolling and current_audio_time_ms > total_time_ms and total_time_ms > 0:
            audio_manager.stop()
            current_audio_time_ms = total_time_ms
            current_note_time_ms = current_audio_time_ms + current_chart.offset_ms
            play_pause_button.set_text('Play')

        last_played_note_time_ms = current_note_time_ms
    else:
        current_note_time_ms = current_audio_time_ms + current_chart.offset_ms
        last_played_note_time_ms = current_note_time_ms

    current_sec = current_audio_time_ms / 1000.0
    total_sec = total_time_ms / 1000.0
    time_label.set_text(f'{current_sec:.3f} / {total_sec:.3f}')


    # (3) 렌더링 (그리기)
    screen.fill((30, 30, 30))
    # pygame.draw.rect(screen, (50, 50, 50), EDITOR_RECT)
    editor_canvas.draw_canvas(screen, 
                              EDITOR_RECT, 
                              current_chart, 
                              current_note_time_ms, 
                              scale_pixels_per_ms, 
                              judgement_line_y,
                              current_snap_division,
                              editor_state,
                              pending_long_note_start,
                              LANE_WIDTH_PIXELS) # <-- [추가!] 고정 너비 전달
    
    # [추가] 2. 파형 그리기
    waveform, sr = audio_manager.get_waveform_data()

    audio_time_ms = current_audio_time_ms
    time_at_top = editor_canvas.screen_y_to_time(
        EDITOR_RECT.top, audio_time_ms, scale_pixels_per_ms, judgement_line_y
    )
    time_at_bottom = editor_canvas.screen_y_to_time(
        EDITOR_RECT.bottom, audio_time_ms, scale_pixels_per_ms, judgement_line_y
    )

    # [수정] 'left_panel.image' 대신 'screen'에 'left_panel_rect'를 넘겨줍니다.
    
    # print(waveform)
    editor_canvas.draw_waveform(screen, 
                                left_panel_rect, # <-- 여기!
                                waveform, 
                                sr, 
                                time_at_top, 
                                time_at_bottom)

    # [수정] 3. 파형 패널에도 판정선 그리기 ('screen'에)
    judgement_line_y_ratio = judgement_line_y / EDITOR_RECT.height
    judgement_line_y_in_wave_panel = left_panel_rect.top + (judgement_line_y_ratio * left_panel_rect.height)

    # [수정] 'wave_panel_surface' 대신 'screen'에 'left_panel_rect' 기준으로 그립니다.
    pygame.draw.line(screen, (255, 255, 0), 
                    (left_panel_rect.left, judgement_line_y_in_wave_panel), 
                    (left_panel_rect.right, judgement_line_y_in_wave_panel), 1)
    manager.draw_ui(screen)
    pygame.display.update()

pygame.quit()
