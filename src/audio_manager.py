import pygame
import librosa
import numpy as np

# --- 1. 믹서 초기화 ---
try:
    # 버퍼 512, 주파수 44100Hz 고정
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.init()
    pygame.init()
    
    # [수정] 채널 0번과 1번을 "예약"해서 자동 할당이 건드리지 못하게 함
    pygame.mixer.set_reserved(2)
    print(f"오디오 시스템 초기화 완료: {pygame.mixer.get_init()}")
except Exception as e:
    print(f"초기화 실패: {e}")

# --- 전역 변수 ---
current_song_path = ""
is_playing = False

start_time_offset = 0.0 
paused_time = 0.0        
total_song_length_ms = 0.0

# 데이터 분리 (시각화용 / 재생용)
current_waveform = None    # main.py 그래프용 (float32)
current_waveform_sr = 44100
_audio_buffer = None       # 재생 전용 (int16)

# --- [핵심] 채널 고정 할당 ---
# 음악은 0번, 효과음은 1번 채널을 전용으로 씁니다.
MUSIC_CHANNEL = pygame.mixer.Channel(0)
HITSOUND_CHANNEL = pygame.mixer.Channel(1)

# 히트사운드 객체
hitsound = None

def load_hitsound(path):
    global hitsound
    try:
        hitsound = pygame.mixer.Sound(path)
        hitsound.set_volume(1.0) # 볼륨 확보
        print(f"히트사운드 로드 성공")
    except Exception as e:
        print(f"히트사운드 로드 실패: {e}")
        hitsound = None

def play_hitsound():
    """전용 채널(1번)에서 타격음을 재생합니다."""
    if hitsound:
        # 음악 채널(0번)을 건드리지 않고 독립적으로 재생
        HITSOUND_CHANNEL.play(hitsound)

def load_song(path):
    global current_song_path, is_playing, total_song_length_ms, paused_time
    global current_waveform, current_waveform_sr, _audio_buffer
    
    try:
        # 1. 길이 계산
        temp_sound = pygame.mixer.Sound(path)
        total_song_length_ms = temp_sound.get_length() * 1000.0
        
        # 2. 파형 분석 (SR 고정)
        mix_freq, mix_size, mix_channels = pygame.mixer.get_init()
        print(f"파형 분석 시작 (Target SR: {mix_freq})...")
        
        current_waveform, current_waveform_sr = librosa.load(path, sr=mix_freq, mono=True)
        
        # 3. 재생용 버퍼 생성 (int16)
        _audio_buffer = (current_waveform * 32767).astype(np.int16)
        
        current_song_path = path
        is_playing = False
        paused_time = 0.0
        print(f"로드 완료: {len(current_waveform)} 샘플")
        return True
    except Exception as e: 
        print(f"로드 실패: {e}")
        return False

def get_waveform_data():
    """시각화용 원본 파형 반환"""
    return current_waveform, current_waveform_sr

def play(start_offset_ms=0.0):
    """음악을 전용 채널(0번)에서 재생"""
    global is_playing, start_time_offset, paused_time, _audio_buffer
    
    if _audio_buffer is None: return

    # [수정] 전체 mixer.stop() 대신 음악 채널만 정지
    # 이제 키음(Channel 1)은 꺼지지 않습니다.
    MUSIC_CHANNEL.stop()

    try:
        start_sec = start_offset_ms / 1000.0
        start_index = int(start_sec * current_waveform_sr)
        
        if start_index >= len(_audio_buffer):
            return

        sliced_data = _audio_buffer[start_index:]
        
        # 스테레오 변환
        audio_data_stereo = np.column_stack((sliced_data, sliced_data))
        audio_data_stereo = np.ascontiguousarray(audio_data_stereo)

        sound_obj = pygame.sndarray.make_sound(audio_data_stereo)
        sound_obj.set_volume(0.7)
        
        # [수정] 0번 채널에 강제 할당하여 재생
        MUSIC_CHANNEL.play(sound_obj)
        
        start_time_offset = pygame.time.get_ticks() - start_offset_ms
        paused_time = 0.0
        is_playing = True
        
    except Exception as e:
        print(f"재생 오류: {e}")
        is_playing = False

def stop():
    global is_playing, paused_time
    
    # 음악 채널만 정지
    MUSIC_CHANNEL.stop()
    
    is_playing = False
    paused_time = 0.0 

def pause():
    global is_playing, paused_time, start_time_offset
    if not is_playing: return
    
    # 음악 채널만 일시정지
    MUSIC_CHANNEL.pause()
        
    is_playing = False
    paused_time = (pygame.time.get_ticks() - start_time_offset)

def unpause():
    global is_playing, start_time_offset, paused_time
    if not current_song_path: return
    
    # 음악 채널만 다시 재생
    MUSIC_CHANNEL.unpause()
    
    # 만약 채널이 멈춰있었다면(소리 끝남 등) 다시 play 시도 (안전장치)
    if not MUSIC_CHANNEL.get_busy() and paused_time < total_song_length_ms:
         play(paused_time)
         return

    is_playing = True
    start_time_offset = pygame.time.get_ticks() - paused_time
    paused_time = 0.0

def get_pos_ms():
    if is_playing:
        return (pygame.time.get_ticks() - start_time_offset)
    else:
        return paused_time

def get_length_ms():
    return total_song_length_ms