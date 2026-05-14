import os
import time
import json
import argparse
import google.genai as genai
from workflow_utils import update_workflow_step, get_workflow_value, set_workflow_value

# 1. 기본 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(SCRIPT_DIR, "video")
RESULT_DIR = os.path.join(SCRIPT_DIR, "result")
os.makedirs(RESULT_DIR, exist_ok=True)

# 2. API 설정 및 예외 처리 (조기 종료)
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("🚨 [오류] GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")
    print("파워셸에서 다음 명령어를 실행하세요: $env:GOOGLE_API_KEY='선생님의_API_키'")
    exit(1)

client = genai.Client(api_key=api_key)

def get_next_filename(video_path, extension="json", result_dir=RESULT_DIR):
    """result_{video_filename}_{index:02d}.json 형태로 다음 저장할 파일명을 결정함"""
    # 1. 경로에서 파일명만 추출 (예: C:/data/TS.mp4 -> TS.mp4)
    file_base_with_ext = os.path.basename(video_path)
    # 2. 확장자 제거 (예: TS.mp4 -> TS)
    video_name_only = os.path.splitext(file_base_with_ext)[0]
    
    index = 0
    while True:
        # result/result_TS_00.json 형식으로 조합
        filename = os.path.join(result_dir, f"result_{video_name_only}_{index:02d}.{extension}")
        if not os.path.exists(filename):
            return filename
        index += 1

def save_json_result(data_text, video_path, result_dir=RESULT_DIR):
    """분석 결과 저장 (파일명에 영상 이름 포함) - ⭐ 파일명 반환"""
    filename = get_next_filename(video_path, result_dir=result_dir)
    
    try:
        json_data = json.loads(data_text)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 분석 결과 저장 완료: {filename}")
        return os.path.basename(filename)  # ⭐ 파일명만 반환
    except json.JSONDecodeError:
        print("❌ JSON 형식이 아니어서 텍스트로 저장합니다.")
        with open(f"{filename}.txt", 'w', encoding='utf-8') as f:
            f.write(data_text)
        return os.path.basename(filename) + ".txt"

def analyze_accident_video(video_path):
    print(f"🎬 영상 업로드 중: {video_path}")
    
    try:
        video_file = client.files.upload(file=video_path)
    except Exception as e:
        print(f"❌ 영상 업로드 실패: {e}")
        print("   - 경로가 올바른지 확인: ", video_path)
        print("   - 네트워크 문제이거나 Gemini 업로드 제한일 수 있습니다.")
        update_workflow_step("analyze", "failed", {"error": f"영상 업로드 실패: {str(e)}", "video_path": video_path})
        exit(1)
    
    # 영상 처리 대기 (무한 대기 방지용 5분 타임아웃 추가)
    max_wait_time = 300
    start_time = time.time()
    
    while video_file.state == "PROCESSING":
        if time.time() - start_time > max_wait_time:
            print("\n❌ 영상 처리 시간 초과 (Timeout). 나중에 다시 시도하세요.")
            update_workflow_step("analyze", "failed", {"error": "영상 처리 시간 초과 (Timeout)"})
            exit(1)
            
        print(".", end="", flush=True)
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state == "FAILED":
        print("\n❌ 구글 서버에서 영상 처리를 실패했습니다.")
        update_workflow_step("analyze", "failed", {"error": "구글 서버에서 영상 처리 실패"})
        exit(1)

    print("\n🧠 AI 분석 중 (Gemini 2.5 Pro)...")
    prompt = """
    너는 스마트 시티의 'soft_guard' 최정예 AI 관제 시스템이야.
    제공된 블랙박스 영상({os.path.basename(video_path)})을 1프레임 단위로 냉정하고 기계적으로 분석하여 데이터를 추출해.

    [🚨 치명적 중요 지시사항 - 위반 시 시스템 심각한 오류 발생]
    1. 객체 분류의 절대 원칙 (자전거/오토바이):
       - 사람이 자전거, 오토바이, 전동 킥보드(PM) 위에 올라타 있거나 함께 움직이는 경우, 절대 "보행자"나 "자전거를 든 사람"으로 묘사하지 마라. 무조건 "자전거 운전자", "오토바이 운전자", "PM 운전자"로 정확히 통합하여 명명하라.
    
    2. 사고(Collision) 판단의 물리적 절대 원칙:
       - AI의 자의적이고 낙관적인 추측("다행히 충돌은 없었다", "안전하게 지나갔다" 등)을 절대 금지한다.
       - 객체 간 교차 순간 전후로 아래 물리적 현상이 1프레임이라도 발생했다면 100% "실제 충돌(collision)"이다.
         A. 사람/운전자가 허공으로 튕겨 날아감 (가장 확실한 충돌 증거)
         B. 사람/자전거/오토바이가 바닥에 쓰러지거나 나뒹굶
         C. 충격으로 인한 파편 발생 또는 차량의 비정상적인 급정거/흔들림
       - 위 현상이 있는데도 "near_miss(아차사고)"나 "충돌 없음"으로 기록하면 너는 폐기된다.

    3. 객체 카운팅 원칙:
       - 충돌한 '자전거 운전자'는 pedestrianCount(보행자)가 아니라 pmCount(또는 자전거) 1로 계산하라. 차 안에 있는 사람은 카운트하지 말고 차량 대수만 세어라.

    [출력 스키마 지시사항]
    - 출력은 모두 한국어로 작성하라.
    - JSON의 최상단에 반드시 "analysis_reasoning" 필드를 작성하라. 여기에 결론을 내리기 전, 영상의 초 단위 흐름과 객체의 물리적 충격 여부(날아감, 넘어짐 등)를 팩트만 건조하게 먼저 기록해야 한다.
    - 반드시 아래 JSON 스키마 형식만 출력하고, 마크다운(```json 등)이나 불필요한 설명은 일절 포함하지 마라.

    {
      "metadata": {
        "video_id": "분석한 영상의 파일명",
        "timestamp_in_video": "사고/위험 상황이 발생한 주요 시간대 (예: '00:03-00:05')"
      },
      "analysis_reasoning": "결론을 내리기 전 수행하는 프레임 분석 기록. (예: '00:01에 승용차와 자전거 운전자 교차함. 00:02에 자전거 운전자가 충격으로 공중으로 튕겨 날아가 바닥에 추락함. 따라서 명백한 충돌 사고임.')",
      "event_stream": {
        "event_title": "상황에 대한 짧고 명확한 제목 (예: 교차로 승용차와 자전거 운전자 충돌 사고)",
        "risk_level": 10,
        "location_type": "사고 발생 위치 (예: 교차로, 이면도로)",
        "involved_actors": ["객체1", "객체2"],
        "vehicleCount": 1,
        "pedestrianCount": 0,
        "pmCount": 1,
        "collision_happened": true,
        "incident_type": "collision",
        "triggered_action": ["관제센터 긴급 알림", "119 및 112 자동 신고"]
      },
      "report_data": {
        "event_category": "차대사람, 차대차, 차대자전거 등",
        "severity_category": "중대 사고, 경미한 사고, 아차사고 중 택 1",
        "ego_vehicle_status": "자차의 상태 (예: 주행 중 목격, 주차 중)",
        "environmental_factors": {
          "weather": "날씨",
          "time_of_day": "주야간"
        },
        "sequence_of_events": [
          "1. 자전거 운전자가 우측에서 좌측으로 이동 중.",
          "2. 직진하던 승용차와 강하게 충돌함.",
          "3. 자전거 운전자가 충격으로 튕겨 날아가 도로에 추락함."
        ],
        "root_cause": "팩트 기반의 위험 상황 근본 원인"
      }
    }
    """

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
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="사고 영상 분석 AI (Gemini 2.5 Pro)")
    parser.add_argument("video_file", nargs='?', help="분석할 영상 파일명 (기본값: 워크플로우 로그에서 읽음)")
    args = parser.parse_args()

    update_workflow_step("analyze", "in_progress", {"message": "영상 분석 시작"})

    # 인자가 없으면 워크플로우 로그에서 읽기
    if args.video_file:
        video_filename = args.video_file
    else:
        video_filename = get_workflow_value("download", "downloaded_video")
        if not video_filename:
            print("❌ 다운로드한 파일이 없습니다. 먼저 1_download_video.py를 실행하세요.")
            print("또는 파일명을 인자로 제공하세요: python 2_analyze_video.py ac7.mp4")
            update_workflow_step("analyze", "failed", {"error": "다운로드된 파일 없음"})
            exit(1)
        print(f"📥 이전 다운로드 파일 사용: {video_filename}")

    video_path = os.path.normpath(os.path.join(VIDEO_DIR, video_filename))
    
    if os.path.exists(video_path):
        json_result = analyze_accident_video(video_path)
        saved_filename = save_json_result(json_result, video_path)  # ⭐ 파일명 반환
        
        # ⭐ 분석 결과 파일명을 워크플로우 로그에 저장 (3번에서 사용)
        set_workflow_value("analyze", "output_result", saved_filename)
        update_workflow_step("analyze", "completed", {
            "input_video": video_filename,
            "output_result": saved_filename
        })
        print(f"✅ 분석 완료. 다음 단계: python 3_upload_result.py")
    else:
        print(f"❌ 영상을 찾을 수 없습니다: {video_path}")
        update_workflow_step("analyze", "failed", {"error": f"파일 없음: {video_path}"})
        exit(1)