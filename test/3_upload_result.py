import os
import requests
import time
import json
from workflow_utils import update_workflow_step, get_workflow_value, set_workflow_value

# 기본 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(SCRIPT_DIR, "result")

# 백엔드 서버 주소 (팀원에게 받은 주소로 변경하세요)
SERVER_BASE_URL = "https://softguard-ah9q.onrender.com"
MAX_RETRIES = 3
RETRY_DELAY = 2 

def upload_result(json_filename):
    # 경로 보정 (사용자가 파일명만 넣었을 경우 result 폴더에서 찾음)
    file_path = os.path.normpath(json_filename)
    if not os.path.exists(file_path):
        candidate_path = os.path.normpath(os.path.join(RESULT_DIR, file_path))
        if os.path.exists(candidate_path):
            file_path = candidate_path
        else:
            print(f"❌ 파일을 찾을 수 없습니다: {json_filename}")
            update_workflow_step("upload", "failed", {"error": f"파일 없음: {json_filename}"})
            return

    print(f"📤 업로드 준비 중: {file_path}")
    update_workflow_step("upload", "in_progress", {"message": "서버 업로드 중", "file": os.path.basename(file_path)})
    
    # 재시도 로직 포함
    for attempt in range(MAX_RETRIES):
        try:
            # 1. 파일에서 JSON 데이터를 읽어옵니다.
            with open(file_path, 'r', encoding='utf-8') as f:
                json_payload = json.load(f)
                
            # ⭐ 2. 백엔드 개발자 성공 코드 이식: 한글 깨짐 방지 및 명시적 바이트 인코딩
            payload_bytes = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}
                
            print(f"🚀 서버로 전송 중... ({SERVER_BASE_URL}/api/results/upload) - 시도 {attempt + 1}/{MAX_RETRIES}")
            upload_res = requests.post(
                f"{SERVER_BASE_URL}/api/results/upload", 
                headers=headers,     # ⭐ 명시적 헤더 추가
                data=payload_bytes,  # ⭐ 바이트 단위로 쪼갠 데이터 전송
                timeout=60
            )
            
            # 서버 응답 검증
            if upload_res.status_code in [200, 201]:
                print("✅ 서버 업로드 성공!")
                print(f"서버 응답: {upload_res.text}")
                update_workflow_step("upload", "completed", {
                    "file": os.path.basename(file_path),
                    "server_response": upload_res.text
                })
                return
            else:
                print(f"⚠️ 업로드 실패 (상태 코드: {upload_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                print(f"에러 내용: {upload_res.text}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 서버 통신 에러: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    print(f"❌ 최대 재시도 횟수 초과")
    update_workflow_step("upload", "failed", {"error": "최대 재시도 횟수 초과"})

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="분석 완료된 JSON 서버 업로드")
    parser.add_argument("json_file", nargs='?', help="업로드할 json 파일명 (기본값: 워크플로우 로그에서 읽음)")
    args = parser.parse_args()

    # 인자가 없으면 워크플로우 로그에서 읽기
    if args.json_file:
        json_filename = args.json_file
    else:
        json_filename = get_workflow_value("analyze", "output_result") or get_workflow_value("analyze", "analyzed_result")
        if not json_filename:
            print("❌ 분석한 파일이 없습니다. 먼저 2_analyze_video.py를 실행하세요.")
            print("또는 파일명을 인자로 제공하세요: python 3_upload_result.py result_The_00.json")
            update_workflow_step("upload", "failed", {"error": "분석된 파일 없음"})
            exit(1)
        print(f"📥 이전 분석 결과 사용: {json_filename}")

    upload_result(json_filename)