import os
import time
import json
import requests
from datetime import datetime
import google.genai as genai

# ==========================================
# 1. 환경 및 기본 경로 설정
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(SCRIPT_DIR, "video")
RESULT_DIR = os.path.join(SCRIPT_DIR, "result")
WORKFLOW_LOG = os.path.join(SCRIPT_DIR, "workflow_log.json")

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

SERVER_BASE_URL = "https://softguard-ah9q.onrender.com"
MAX_RETRIES = 3
RETRY_DELAY = 2

client = None

# ==========================================
# 2. 워크플로우 유틸리티 (workflow_utils.py)
# ==========================================
def init_workflow_log():
    if not os.path.exists(WORKFLOW_LOG):
        log_data = {"workflow_start": datetime.now().isoformat(), "steps": {}}
        with open(WORKFLOW_LOG, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

def update_workflow_step(step_name, status, details=None):
    init_workflow_log()
    with open(WORKFLOW_LOG, "r", encoding="utf-8") as f:
        log_data = json.load(f)
    log_data["steps"][step_name] = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    with open(WORKFLOW_LOG, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def get_workflow_value(step_name, key):
    if not os.path.exists(WORKFLOW_LOG):
        return None
    with open(WORKFLOW_LOG, "r", encoding="utf-8") as f:
        log_data = json.load(f)
    if step_name in log_data["steps"] and key in log_data["steps"][step_name].get("details", {}):
        return log_data["steps"][step_name]["details"][key]
    return None

def set_workflow_value(step_name, key, value):
    init_workflow_log()
    with open(WORKFLOW_LOG, "r", encoding="utf-8") as f:
        log_data = json.load(f)
    if step_name not in log_data["steps"]:
        log_data["steps"][step_name] = {"details": {}}
    if log_data["steps"][step_name].get("details") is None:
        log_data["steps"][step_name]["details"] = {}
    log_data["steps"][step_name]["details"][key] = value
    with open(WORKFLOW_LOG, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

# ==========================================
# 3. Step 1: 다운로드 모듈
# ==========================================
def step1_download_video():
    print("📡 [Step 1] 서버에 대기 중인 영상이 있는지 확인합니다...")
    update_workflow_step("download", "in_progress", {"message": "서버에서 영상 목록 조회 중"})
    
    try:
        pending_videos = None
        for attempt in range(MAX_RETRIES):
            try:
                list_res = requests.get(f"{SERVER_BASE_URL}/api/videos/pending", timeout=60)
                if list_res.status_code != 200:
                    print(f"⚠️ 목록 조회 실패 (상태 코드: {list_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
                    continue
                
                pending_videos = list_res.json()
                if not isinstance(pending_videos, list):
                    print(f"❌ 서버 응답 형식 오류 (리스트 예상): {type(pending_videos)}")
                    update_workflow_step("download", "failed", {"error": f"잘못된 응답 형식: {type(pending_videos)}"})
                    return None
                break
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 네트워크 오류: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
                else:
                    update_workflow_step("download", "failed", {"error": f"네트워크 오류: {str(e)}"})
                    return None
        
        if pending_videos is None:
            print(f"❌ 최대 재시도 횟수 초과")
            update_workflow_step("download", "failed", {"error": "최대 재시도 횟수 초과"})
            return None
        
        if not pending_videos:
            update_workflow_step("download", "completed", {"message": "대기 영상 없음"})
            return None

        def parse_pending(item):
            event_id = None
            if isinstance(item, dict):
                video_url = item.get('videoUrl', '')
                event_id = item.get('eventId')
                if not video_url: return None, None, None
                target = video_url.split('/')[-1]
                url = video_url if video_url.startswith("http") else f"{SERVER_BASE_URL}/api/videos/download/{target}"
            else:
                target = item
                url = f"{SERVER_BASE_URL}/api/videos/download/{target}"
            return target, url, event_id

        selected_target = None
        selected_url = None
        selected_event_id = None

        # 💡 이미 처리된 영상(로컬 폴더 증거 기반)은 무조건 패스
        for item in pending_videos:
            target, url, ev_id = parse_pending(item)
            if not target:
                continue
            
            # result 폴더에 이미 해당 영상의 json 파일이 존재하는지 검사
            video_name_only = os.path.splitext(target)[0]
            already_processed = False
            for f in os.listdir(RESULT_DIR):
                if f.startswith(f"result_{video_name_only}_") and f.endswith(".json"):
                    already_processed = True
                    break
            
            if already_processed:
                continue # 처리된 영상 조용히 스킵
            
            # 처리 안 된 새로운 영상을 찾으면 타겟팅!
            selected_target = target
            selected_url = url
            selected_event_id = ev_id
            break

        if selected_target is None:
            update_workflow_step("download", "completed", {"message": "모두 처리됨"})
            return None

        target_video = selected_target
        download_url = selected_url
        print(f"🎯 타겟 영상 파일명: {target_video}")

        # 만약 video 폴더에 파일이 이미 온전히 있다면 다운로드도 패스
        save_path = os.path.join(VIDEO_DIR, target_video)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            print(f"✅ 영상 파일이 이미 로컬에 존재합니다. 다운로드 생략: {save_path}")
            set_workflow_value("download", "downloaded_video", target_video)
            set_workflow_value("download", "event_id", selected_event_id)
            update_workflow_step("download", "completed", {"downloaded_video": target_video, "save_path": save_path, "event_id": selected_event_id})
            return target_video

        print(f"📥 다운로드 주소: {download_url}")

        for attempt in range(MAX_RETRIES):
            try:
                dl_res = requests.get(download_url, stream=True, timeout=120)
                if dl_res.status_code == 200:
                    with open(save_path, 'wb') as f:
                        for chunk in dl_res.iter_content(chunk_size=8192):
                            if chunk: f.write(chunk)
                    print(f"✅ 다운로드 완료! 저장 위치: {save_path}")
                    set_workflow_value("download", "downloaded_video", target_video)
                    set_workflow_value("download", "event_id", selected_event_id)
                    update_workflow_step("download", "completed", {"downloaded_video": target_video, "save_path": save_path, "event_id": selected_event_id})
                    return target_video
                else:
                    print(f"⚠️ 다운로드 실패 (상태 코드: {dl_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 네트워크 오류: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
        
        print(f"❌ 최대 재시도 횟수 초과")
        update_workflow_step("download", "failed", {"error": "다운로드 최대 재시도 횟수 초과"})
        return None
            
    except Exception as e:
        print(f"🚨 예기치 않은 오류: {e}")
        update_workflow_step("download", "failed", {"error": str(e)})
        return None

# ==========================================
# 4. Step 2: 분석 모듈
# ==========================================
def get_next_filename(video_path, extension="json", result_dir=RESULT_DIR):
    file_base_with_ext = os.path.basename(video_path)
    video_name_only = os.path.splitext(file_base_with_ext)[0]
    index = 0
    while True:
        filename = os.path.join(result_dir, f"result_{video_name_only}_{index:02d}.{extension}")
        if not os.path.exists(filename):
            return filename
        index += 1

def save_json_result(data_text, video_path, result_dir=RESULT_DIR):
    filename = get_next_filename(video_path, result_dir=result_dir)
    try:
        json_data = json.loads(data_text)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 분석 결과 저장 완료: {filename}")
        return os.path.basename(filename)
    except json.JSONDecodeError:
        print("❌ JSON 형식이 아니어서 텍스트로 저장합니다.")
        with open(f"{filename}.txt", 'w', encoding='utf-8') as f:
            f.write(data_text)
        return os.path.basename(filename) + ".txt"

def analyze_accident_video(video_path):
    print(f"🎬 영상 업로드 중: {video_path}")
    global client
    try:
        video_file = client.files.upload(file=video_path)
    except Exception as e:
        print(f"❌ 영상 업로드 실패: {e}")
        update_workflow_step("analyze", "failed", {"error": f"영상 업로드 실패: {str(e)}", "video_path": video_path})
        return None
    
    max_wait_time = 300
    start_time = time.time()
    while video_file.state == "PROCESSING":
        if time.time() - start_time > max_wait_time:
            print("\n❌ 영상 처리 시간 초과 (Timeout). 나중에 다시 시도하세요.")
            update_workflow_step("analyze", "failed", {"error": "영상 처리 시간 초과 (Timeout)"})
            return None
        print(".", end="", flush=True)
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state == "FAILED":
        print("\n❌ 구글 서버에서 영상 처리를 실패했습니다.")
        update_workflow_step("analyze", "failed", {"error": "구글 서버에서 영상 처리 실패"})
        return None

    print("\n🧠 AI 분석 중 (Gemini 2.5 Pro)...")
    prompt = """
    너는 스마트 시티의 'soft_guard' AI 관제 시스템이야.
    제공된 블랙박스 영상({os.path.basename(video_path)})을 1프레임 단위로 정밀하게 분석하여 데이터를 추출해줘.
    
    [중요 지시사항]
    0. 출력 내용은 모두 한국어로 작성하라. JSON 값과 문장도 한국어로 작성하고, 가능한 경우 JSON 키도 한국어로 사용하라.
    1. 화면에 등장하는 차량의 종류(일반 승용차, 택시, 버스, 화물차, 오토바이, 자전거)를 절대 혼동하지 말고 정확히 식별할 것.
    2. 버스는 절대 SUV 또는 승용차로 쓰지 마. (승객석이 보이면 버스)
    3. 영상 속 교통 신호, 차로 방향을 명확히 분석하라.
    4. 🚨 [치명적 중요] 사고 순간의 환각(Hallucination) 절대 금지: 객체 간의 거리가 매우 가깝게 교차한 직후, **보행자가 바닥에 넘어지거나, 튕겨 나가거나, 쓰러져 있는 모습**이 1프레임이라도 포착된다면 이는 100% "실제 충돌(collision)"이다.
    5. 충돌 순간이 차량에 가려져 보이지 않더라도, 보행자가 넘어졌다면 절대 "안전하게 건넜다"거나 "아차사고(near_miss)"라고 왜곡해서 작성하지 마라.
    6. 차량이 갑자기 급정거를 하고 보행자의 자세가 무너지는 것도 충돌의 강력한 증거다. 끝까지 보행자의 상태를 추적하라.
    7. 실제 충돌(넘어짐 등)이 발생하면 "collision_happened": true, "incident_type": "collision"으로 기재하고, risk_score는 8~10점 사이로 높게 부여하라.
    8. 접촉이 전혀 없고 양측 모두 정상적으로 주행/보행을 이어갈 때만 "near_miss"를 사용하라.
    9. 객체의 움직임과 결과를 팩트 기반으로만 냉정하게 기술하라.
    10. 반드시 아래의 JSON 스키마 형식에 맞춰서 출력하고, 마크다운(```json)이나 다른 설명은 절대 포함하지 마.

    [JSON 스키마]
    {
      "metadata": {
        "video_id": "분석한 영상의 파일명",
        "timestamp_in_video": "사고/위험 상황이 발생한 시간대 (예: '00:03-00:05')"
      },
      "event_stream": {
        "event_title": "상황에 대한 짧고 명확한 제목 (예: 이면도로 무단횡단 아동 차량 충돌 사고)",
        "risk_level": 10,
        "location_type": "사고 발생 위치 (예: 이면도로)",
        "involved_actors": ["객체1", "객체2"],
        "vehicleCount": 2,
        "pedestrianCount": 1,
        "pmCount": 0,
        "collision_happened": true,
        "incident_type": "collision",
        "triggered_action": ["관제센터 긴급 알림", "119 자동 신고 대기"]
      },
      "report_data": {
        "event_category": "차대사람, 차대차 등 (참여한 행위자 수량 포함)",
        "severity_category": "중대 사고, 경미한 사고, 아차사고 중 택 1",
        "ego_vehicle_status": "자차의 상태",
        "environmental_factors": {
          "weather": "날씨",
          "time_of_day": "주야간"
        },
        "sequence_of_events": [
          "1. 아동이 우측에서 좌측으로 무단횡단 시도.",
          "2. 좌측에서 직진하던 검은색 승용차 1대와 충돌함.",
          "3. 아동이 도로에 넘어짐."
        ],
        "root_cause": "위험 상황의 근본 원인"
      }
    }
    """
    
    prompt = prompt.replace("{os.path.basename(video_path)}", os.path.basename(video_path))
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro", 
            contents=[video_file, prompt],
            config={"response_mime_type": "application/json"}
        )
        return response.text
    except Exception as e:
        print(f"❌ AI 분석 중 에러 발생: {e}")
        update_workflow_step("analyze", "failed", {"error": f"AI 분석 실패: {str(e)}"})
        return None

def step2_analyze_video(video_filename):
    print(f"🧠 [Step 2] AI 영상 분석 시작: {video_filename}")
    global client
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("🚨 [오류] GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
        return None
    if not client:
        client = genai.Client(api_key=api_key)

    video_path = os.path.normpath(os.path.join(VIDEO_DIR, video_filename))
    if not os.path.exists(video_path):
        print(f"❌ 영상을 찾을 수 없습니다: {video_path}")
        update_workflow_step("analyze", "failed", {"error": f"파일 없음: {video_path}"})
        return None

    update_workflow_step("analyze", "in_progress", {"message": "영상 분석 시작"})
    json_result = analyze_accident_video(video_path)
    
    if json_result:
        saved_filename = save_json_result(json_result, video_path)
        set_workflow_value("analyze", "output_result", saved_filename)
        update_workflow_step("analyze", "completed", {
            "input_video": video_filename,
            "output_result": saved_filename
        })
        return saved_filename
    return None

# ==========================================
# 5. Step 3: 업로드 모듈
# ==========================================
def step3_upload_result(json_filename):
    print(f"📤 [Step 3] 분석 결과 서버 업로드 시작: {json_filename}")
    file_path = os.path.normpath(json_filename)
    if not os.path.exists(file_path):
        candidate_path = os.path.normpath(os.path.join(RESULT_DIR, file_path))
        if os.path.exists(candidate_path):
            file_path = candidate_path
        else:
            print(f"❌ 파일을 찾을 수 없습니다: {json_filename}")
            update_workflow_step("upload", "failed", {"error": f"파일 없음: {json_filename}"})
            return False

    update_workflow_step("upload", "in_progress", {"message": "서버 업로드 중", "file": os.path.basename(file_path)})
    
    for attempt in range(MAX_RETRIES):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_payload = json.load(f)
                
            event_id = get_workflow_value("download", "event_id")
            if event_id is not None:
                if "metadata" not in json_payload:
                    json_payload["metadata"] = {}
                json_payload["metadata"]["event_id"] = event_id
                print(f"✅ JSON 데이터에 event_id({event_id}) 주입 완료!")

            payload_bytes = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}
                
            print(f"🚀 서버로 전송 중... ({SERVER_BASE_URL}/api/results/upload) - 시도 {attempt + 1}/{MAX_RETRIES}")
            upload_res = requests.post(
                f"{SERVER_BASE_URL}/api/results/upload", 
                headers=headers,
                data=payload_bytes,
                timeout=60
            )
            
            if upload_res.status_code in [200, 201]:
                print("✅ 서버 업로드 성공!")
                print(f"서버 응답: {upload_res.text}")
                update_workflow_step("upload", "completed", {
                    "file": os.path.basename(file_path),
                    "server_response": upload_res.text
                })
                return True
            else:
                print(f"⚠️ 업로드 실패 (상태 코드: {upload_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                print(f"에러 내용: {upload_res.text}")
                if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
                    
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 서버 통신 에러: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1: time.sleep(RETRY_DELAY)
    
    print(f"❌ 최대 재시도 횟수 초과")
    update_workflow_step("upload", "failed", {"error": "최대 재시도 횟수 초과"})
    return False

# ==========================================
# 6. 통합 메인 함수 (24시간 무한 루프 적용)
# ==========================================
def main():
    print("==================================================")
    print("🚀 SoftGuard 24시간 자동화 파이프라인 가동 시작!")
    print("==================================================")

    while True:
        try:
            # 1. 다운로드 확인
            video_filename = step1_download_video()
            
            if not video_filename:
                # 처리할 영상이 없으면 현재 시각 출력 후 1분(60초) 대기
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n({now_str}) 새로 업로드된 영상 없음 대기중...")
                time.sleep(60)
                continue

            # 2. 영상 분석
            json_filename = step2_analyze_video(video_filename)
            if not json_filename:
                print("🛑 분석 중 오류 발생. 10초 대기 후 다음 사이클로 넘어갑니다.")
                time.sleep(10)
                continue

            # 3. 결과 업로드
            is_success = step3_upload_result(json_filename)
            if not is_success:
                print("🛑 업로드 중 오류 발생. 10초 대기 후 다음 사이클로 넘어갑니다.")
                time.sleep(10)
                continue

            # 💡 영상 처리 1건 완벽 성공 직후
            # 대기열에 밀린 영상이 더 있을 수 있으므로 5분 쉬지 않고 5초만 쉬고 바로 다음 대기열을 확인합니다.
            print("\n🔄 1건 처리 완료! 대기열에 남은 영상이 있는지 5초 후 즉시 재확인합니다...")
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 사용자에 의해 무한 루프가 안전하게 종료되었습니다.")
            break
        except Exception as e:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n({now_str}) 🚨 시스템 예외 발생: {e}")
            print("5분 후 다시 시도합니다...")
            time.sleep(300)

if __name__ == "__main__":
    main()