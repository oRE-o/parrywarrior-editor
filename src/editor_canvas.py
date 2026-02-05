import math
import pygame
import numpy as np

# Pygame 폰트 모듈 초기화
# pygame.font.init()
GRID_FONT = None
# GRID_FONT = pygame.font.SysFont('Arial', 12) # 그리드 시간 표시용 폰트
def init_font():
    """
    폰트를 초기화하는 함수. main.py에서 pygame.init() 이후에 호출됩니다.
    """
    global GRID_FONT
    # 여기서 폰트를 생성합니다.
    GRID_FONT = pygame.font.SysFont('Arial', 12)
# --- 좌표 변환 함수 ---
def time_to_screen_y(time_ms, current_time_ms, scale_pixels_per_ms, judgement_line_y):
    time_diff_ms = time_ms - current_time_ms
    pixel_diff = time_diff_ms * scale_pixels_per_ms
    return judgement_line_y - pixel_diff

def screen_y_to_time(screen_y, current_time_ms, scale_pixels_per_ms, judgement_line_y):
    # [수정] 0으로 나누기 방지
    if scale_pixels_per_ms == 0:
        return current_time_ms
    pixel_diff = judgement_line_y - screen_y
    time_diff_ms = pixel_diff / scale_pixels_per_ms
    return current_time_ms + time_diff_ms

# --- 그리기 메인 함수 ---
def draw_canvas(surface, rect, chart, current_time_ms, scale, judgement_y, snap_division, editor_state, pending_long_note_start, lane_width_pixels):
    
    """
    에디터 캔버스(가운데 영역)를 그립니다.
    surface: 그릴 대상 (pygame.display.get_surface())
    rect: 그릴 영역 (EDITOR_RECT)
    chart: ChartData 객체
    current_time_ms: 현재 시간 (스크롤 위치)
    scale: 줌 배율 (밀리초당 픽셀 수)
    judgement_y: 판정선의 화면 Y좌표
    """
    
    # 그리기 영역(EDITOR_RECT)으로 클리핑 설정 (패널 침범 방지)
    surface.set_clip(rect)

    # 1. 레인 그리기
    num_lanes = chart.num_lanes
    if num_lanes == 0: num_lanes = 1

    total_lanes_width = num_lanes * lane_width_pixels
    start_x = rect.left + (rect.width - total_lanes_width) / 2

    for i in range(num_lanes + 1):
        x = start_x + i * lane_width_pixels
        pygame.draw.line(surface, (80, 80, 80), (x, rect.top), (x, rect.bottom), 1)

    # 2. 그리드 라인 그리기 (스냅, 마디)


    if chart.bpm <= 0: chart.bpm = 120.0
    beat_duration_ms = 60000.0 / chart.bpm
    if snap_division == 0: snap_division = 1 
    snap_ms = beat_duration_ms / (snap_division / 4.0)
    if snap_ms == 0: snap_ms = 500.0

    time_at_top = screen_y_to_time(rect.top, current_time_ms, scale, judgement_y)
    time_at_bottom = screen_y_to_time(rect.bottom, current_time_ms, scale, judgement_y)
    
    start_snap_index = math.floor(time_at_bottom / snap_ms)
    current_snap_time = start_snap_index * snap_ms
    lane_width = lane_width_pixels
    grid_start_x = start_x
    grid_end_x = start_x + total_lanes_width
    
    while current_snap_time < time_at_top: # 화면 상단에 도달할 때까지
        y = time_to_screen_y(current_snap_time, current_time_ms, scale, judgement_y)
        
        # 화면 Y 영역을 벗어나면 그리지 않음 (효율화)
        if y < rect.top or y > rect.bottom:
            current_snap_time += snap_ms
            continue

        # 비트 계산 (4박자, 1박자, 나머지)
        beat_count_float = (current_snap_time / beat_duration_ms)
        beat_count_int = round(beat_count_float)

        color = (60, 60, 60) # 기본 스냅 (16비트)
        width = 1
        
        if abs(beat_count_float - beat_count_int) < 0.001: 
            if beat_count_int % 4 == 0: 
                color = (255, 100, 100)
                width = 2
                if GRID_FONT:
                    time_text = f"{current_snap_time / 1000.0:.3f}"
                    text_surf = GRID_FONT.render(time_text, True, color)
                    surface.blit(text_surf, (start_x + 5, y - text_surf.get_height() / 2)) # (start_x 기준으로 수정됨)
            else: 
                color = (150, 150, 150)
                width = 1
        pygame.draw.line(surface, color, (grid_start_x, y), (grid_end_x, y), width) # (grid_start_x 기준으로 수정됨)
        current_snap_time += snap_ms

    # 3. 노트 그리기
    for note in chart.notes:
        note_type = chart.note_types.get(note.note_type_name)
        if not note_type: continue

        # [수정] 롱노트만 그립니다.
        if note_type.is_long_note and note.end_time_ms:
            # [수정!] 롱노트 시작/끝 둘 다 offset_ms 더하기
            note_x = start_x + note.lane * lane_width_pixels
            note_start_y = time_to_screen_y(note.time_ms, current_time_ms, scale, judgement_y)

            note_end_y = time_to_screen_y(note.end_time_ms, current_time_ms, scale, judgement_y)
            note_height = note_start_y - note_end_y
            if note_height < 0: note_height = 0

            if note_start_y < rect.top or note_end_y > rect.bottom:
                continue

            pygame.draw.rect(surface, note_type.color, (note_x, note_end_y, lane_width_pixels, note_height))
            pygame.draw.rect(surface, (255,255,255), (note_x, note_end_y, lane_width_pixels, note_height), 1) 

            start_cap_height = 8 
            start_cap_y = note_start_y - start_cap_height
            darker_color = (max(0, note_type.color[0] - 60), max(0, note_type.color[1] - 60), max(0, note_type.color[2] - 60))
            pygame.draw.rect(surface, darker_color, (note_x, start_cap_y, lane_width_pixels, start_cap_height))
            pygame.draw.rect(surface, (255,255,255), (note_x, start_cap_y, lane_width_pixels, start_cap_height), 1)

    for note in chart.notes:
        note_type = chart.note_types.get(note.note_type_name)
        if not note_type: continue

        # [수정] 단노트만 그립니다. (롱노트가 아닌 것)
        if not (note_type.is_long_note and note.end_time_ms):
            # [수정!] 단노트에도 offset_ms 더하기
            note_start_y = time_to_screen_y(note.time_ms, current_time_ms, scale, judgement_y)
            note_x = start_x + note.lane * lane_width_pixels
            note_height = 8 
            if note_start_y < rect.top or note_start_y - note_height > rect.bottom:
                continue

            # [수정!] 노트 너비 적용
            pygame.draw.rect(surface, note_type.color, (note_x, note_start_y - note_height, lane_width_pixels, note_height))
            pygame.draw.rect(surface, (255,255,255), (note_x, note_start_y - note_height, lane_width_pixels, note_height), 1)
            
    if editor_state == 1 and pending_long_note_start: # STATE_PLACING_LONG
        lane = pending_long_note_start["lane"]
        note_type = chart.note_types.get(pending_long_note_start["type_name"])
        
        if note_type:
            note_x = start_x + lane * lane_width_pixels
            
            start_y = time_to_screen_y(pending_long_note_start["time_ms"], current_time_ms, scale, judgement_y)
            
            mouse_x, mouse_y = pygame.mouse.get_pos()
            if mouse_y < rect.top: mouse_y = rect.top
            if mouse_y > rect.bottom: mouse_y = rect.bottom
            
            preview_color = (*note_type.color, 150)
            # [수정!] 프리뷰 너비 적용
            preview_rect = pygame.Rect(note_x, min(start_y, mouse_y), lane_width_pixels, abs(start_y - mouse_y))
            
            s = pygame.Surface((lane_width_pixels, preview_rect.height), pygame.SRCALPHA)
            s.fill(preview_color)
            surface.blit(s, (preview_rect.x, preview_rect.y))
            pygame.draw.rect(surface, (255,255,255), preview_rect, 1)

    # [수정] 5. 고정된 판정선 그리기 (이전의 4번)
    pygame.draw.line(surface, (255, 255, 0), (grid_start_x, judgement_y), (grid_end_x, judgement_y), 3)
    surface.set_clip(None)
    
def draw_waveform(surface, rect, waveform_data, sr, time_at_top_ms, time_at_bottom_ms):
    """
    [최종 수정된 직관적인 버전]
    왼쪽 파형 패널(rect)에 파형을 그립니다. (진폭 묘사)
    """
    
    # 1. 그릴 영역 설정 및 배경 칠하기
    surface.set_clip(rect)
    surface.fill((40, 40, 40), rect) # 배경색

    # 2. 데이터 없으면 그릴 수 없음
    if waveform_data is None or len(waveform_data) == 0 or sr <= 0:
        surface.set_clip(None)
        return

    # 3. 캔버스 정보
    panel_height_px = rect.height
    panel_center_x = rect.left + rect.width / 2
    panel_half_width = rect.width / 2.0
    
    # 4. 시간 범위 계산
    # [버그 1 수정!] total_ms_in_view는 (미래 - 과거)
    total_ms_in_view = time_at_top_ms - time_at_bottom_ms
    if total_ms_in_view <= 0:
        surface.set_clip(None)
        return
        
    # (ms / px)
    ms_per_pixel = total_ms_in_view / panel_height_px
        
    # 5. Y축 픽셀 하나하나(0 ~ panel_height_px)를 순회
    for y_pixel_offset in range(int(panel_height_px)):
        
        # (1) 이 픽셀(y)이 몇 ms에 해당하는지 계산
        pixel_ratio = y_pixel_offset / panel_height_px
        current_ms = time_at_top_ms - (pixel_ratio * total_ms_in_view)
        
        start_ms = current_ms
        end_ms = current_ms - ms_per_pixel
        
        # (2) 이 시간 범위에 해당하는 샘플 인덱스
        s_idx = max(0, int((end_ms / 1000.0) * sr))
        e_idx = min(len(waveform_data), int((start_ms / 1000.0) * sr))
        
        if s_idx >= e_idx:
            continue
            
        # (3) 이 픽셀을 대표하는 샘플들
        pixel_samples = waveform_data[s_idx:e_idx]
        if len(pixel_samples) == 0:
            continue

        # (4) 최대/최소 진폭 찾기
        max_val = np.max(pixel_samples)
        min_val = np.min(pixel_samples)
        
        # (5) [버그 2 수정!] NaN/inf 값 방어 코드
        if not (np.isfinite(max_val) and np.isfinite(min_val)):
            continue # (숫자가 아니면 이 픽셀은 무시)
            
        # (6) X좌표 계산
        x_left = panel_center_x + (min_val * panel_half_width)
        x_right = panel_center_x + (max_val * panel_half_width)
        
        # (7) 실제 y 픽셀 좌표
        y = rect.top + y_pixel_offset
        
        # (8) [버그 3 수정!] 'int()'로 정수 좌표로 변환
        pygame.draw.line(surface, (100, 150, 255), (int(x_left), y), (int(x_right), y), 1)

    # 6. 클리핑 해제
    surface.set_clip(None)
