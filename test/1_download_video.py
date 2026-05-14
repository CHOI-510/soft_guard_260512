import os
import requests
import time
from workflow_utils import update_workflow_step, set_workflow_value

# 기본 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(SCRIPT_DIR, "video")
os.makedirs(VIDEO_DIR, exist_ok=True)

# 백엔드 서버 주소 (팀원에게 받은 주소로 변경하세요)
SERVER_BASE_URL = "https://softguard-ah9q.onrender.com"
MAX_RETRIES = 3
RETRY_DELAY = 2

def download_pending_video():
    print("📡 서버에 대기 중인 영상이 있는지 확인합니다...")
    update_workflow_step("download", "in_progress", {"message": "서버에서 영상 목록 조회 중"})
    
    try:
        # 1. 대기 목록 조회 (재시도 로직 포함)
        pending_videos = None
        for attempt in range(MAX_RETRIES):
            try:
                list_res = requests.get(f"{SERVER_BASE_URL}/api/videos/pending", timeout=60)
                
                if list_res.status_code != 200:
                    print(f"⚠️ 목록 조회 실패 (상태 코드: {list_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                    continue
                
                # 서버 응답 검증
                pending_videos = list_res.json()
                if not isinstance(pending_videos, list):
                    print(f"❌ 서버 응답 형식 오류 (리스트 예상): {type(pending_videos)}")
                    update_workflow_step("download", "failed", {"error": f"잘못된 응답 형식: {type(pending_videos)}"})
                    return None
                break
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 네트워크 오류: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    update_workflow_step("download", "failed", {"error": f"네트워크 오류: {str(e)}"})
                    return None
        
        if pending_videos is None:
            print(f"❌ 최대 재시도 횟수 초과")
            update_workflow_step("download", "failed", {"error": "최대 재시도 횟수 초과"})
            return None
        
        if not pending_videos:
            print("💤 현재 서버에 대기 중인 새 영상이 없습니다.")
            update_workflow_step("download", "completed", {"message": "대기 영상 없음"})
            return None

        print("🔎 서버에서 받은 pending_videos 목록:")
        for idx, item in enumerate(pending_videos, start=1):
            if isinstance(item, dict):
                print(f"  {idx}. dict videoUrl={item.get('videoUrl')} eventId={item.get('eventId')}")
            else:
                print(f"  {idx}. {item}")

        last_downloaded = get_workflow_value("download", "downloaded_video")
        if last_downloaded:
            print(f"⏳ 마지막으로 다운로드한 영상: {last_downloaded}")
        
        # ==========================================
        # 💡 [수정된 부분] 딕셔너리 데이터 분해 로직
        # ==========================================
        last_downloaded = get_workflow_value("download", "downloaded_video")
        selected_item = None
        selected_target = None
        selected_url = None

        def parse_pending(item):
            if isinstance(item, dict):
                video_url = item.get('videoUrl', '')
                if not video_url:
                    return None, None
                target = video_url.split('/')[-1]
                url = video_url if video_url.startswith("http") else f"{SERVER_BASE_URL}/api/videos/download/{target}"
            else:
                target = item
                url = f"{SERVER_BASE_URL}/api/videos/download/{target}"
            return target, url

        for item in pending_videos:
            target, url = parse_pending(item)
            if not target:
                continue
            if last_downloaded and target == last_downloaded and os.path.exists(os.path.join(VIDEO_DIR, target)):
                print(f"⏭ 기존에 다운로드한 영상 건너뜀: {target}")
                continue
            selected_item = item
            selected_target = target
            selected_url = url
            break

        if selected_item is None:
            if last_downloaded and os.path.exists(os.path.join(VIDEO_DIR, last_downloaded)):
                print(f"💤 새 영상 없음. 기존 다운로드된 영상 사용: {last_downloaded}")
                update_workflow_step("download", "completed", {
                    "message": "새 영상 없음, 기존 영상 사용",
                    "downloaded_video": last_downloaded,
                    "save_path": os.path.join(VIDEO_DIR, last_downloaded)
                })
                return last_downloaded
            print("❌ 새 영상이 없고 기존 다운로드 파일도 없습니다.")
            update_workflow_step("download", "failed", {"error": "새 영상 없음, 기존 다운로드 파일 없음"})
            return None

        target_video = selected_target
        download_url = selected_url

        print(f"🎯 타겟 영상 파일명: {target_video}")
        print(f"📥 다운로드 주소: {download_url}")
        # ==========================================

        # 2. 영상 다운로드 (재시도 로직 포함)
        for attempt in range(MAX_RETRIES):
            try:
                # 위에서 만든 download_url을 사용해 다운로드 요청
                dl_res = requests.get(download_url, stream=True, timeout=120)
                
                if dl_res.status_code == 200:
                    save_path = os.path.join(VIDEO_DIR, target_video)
                    with open(save_path, 'wb') as f:
                        for chunk in dl_res.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"✅ 다운로드 완료! 저장 위치: {save_path}")
                    
                    # ⭐ 워크플로우 로그에 '파일 이름(target_video)'만 저장 (2, 3번 스크립트가 이 이름을 씀)
                    set_workflow_value("download", "downloaded_video", target_video)
                    update_workflow_step("download", "completed", {
                        "downloaded_video": target_video,
                        "save_path": save_path
                    })
                    return target_video
                else:
                    print(f"⚠️ 다운로드 실패 (상태 코드: {dl_res.status_code}) - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        
            except requests.exceptions.RequestException as e:
                print(f"⚠️ 네트워크 오류: {e} - 재시도 중... ({attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
        
        print(f"❌ 최대 재시도 횟수 초과")
        update_workflow_step("download", "failed", {"error": "다운로드 최대 재시도 횟수 초과"})
        return None
            
    except Exception as e:
        print(f"🚨 예기치 않은 오류: {e}")
        update_workflow_step("download", "failed", {"error": str(e)})
        return None

if __name__ == "__main__":
    download_pending_video()