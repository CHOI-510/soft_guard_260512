# 🚗 Soft Guard - 사고 영상 분석 AI 시스템

> **블랙박스 영상을 자동으로 분석하고 서버에 업로드하는 완전 자동화된 워크플로우 시스템**

---

## 📋 프로젝트 개요

Soft Guard는 다음 3단계의 자동화된 파이프라인으로 동작합니다:

1. **📥 Download** - 서버에서 대기 중인 영상 다운로드
2. **🧠 Analyze** - Google Gemini 2.5 Pro로 AI 분석
3. **📤 Upload** - 분석 결과를 서버에 업로드

각 단계는 **중앙 로깅 시스템(`workflow_log.json`)**을 통해 자동으로 연동되어, 수동으로 파일명을 입력할 필요가 없습니다.

---

## � 설치 및 환경 구성

### 1️⃣ 사전 요구사항

- **Windows 10/11**
- **Python 3.13+** ([다운로드](https://www.python.org/downloads/))
- **Git** (선택사항, 코드 버전 관리용)
- **VS Code** (선택사항, 코드 편집 권장)

### 2️⃣ 가상환경 생성 (처음 1회만)

```powershell
# soft_guard 폴더 생성 및 이동
mkdir soft_guard
cd soft_guard

# Python 가상환경 생성
python -m venv soft_guard

# PowerShell 실행 정책 변경 (필요시)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 3️⃣ 가상환경 활성화

**Windows PowerShell:**
```powershell
.\soft_guard\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
.\soft_guard\Scripts\activate.bat
```

**Git Bash:**
```bash
source soft_guard/Scripts/activate
```

✅ 성공하면 프롬프트 앞에 `(soft_guard)` 표시됨:
```powershell
(soft_guard) PS D:\jeong\soft_guard>
```

### 4️⃣ 필수 패키지 설치

```powershell
# 방법 1: requirements.txt 사용 (추천)
pip install -r requirements.txt

# 방법 2: 개별 설치
pip install google-genai>=0.8.6
pip install requests>=2.34.0
pip install python-dotenv>=1.0.0
```

**설치 확인:**
```powershell
pip list | grep -E "google|requests"
```

예상 출력:
```
google-genai            0.8.6
google-ai-generativelanguage  0.6.15
google-api-core         2.30.3
requests                2.34.0
python-dotenv           1.0.0
```

### 5️⃣ 폴더 구조 생성

```powershell
# video & result 폴더 자동 생성됨 (스크립트 실행 시)
# 수동으로 생성하려면:
mkdir video result
```

---

## �📁 폴더 구조

```
soft_guard/
│
├── 📂 soft_guard/              # 가상환경 폴더 (Python 3.13)
│   ├── Scripts/
│   ├── Lib/
│   ├── Include/
│   └── pyvenv.cfg
│
├── 📂 video/                   # 입력: 다운로드된 영상 저장소
│   └── (다운로드된 mp4 파일들)
│
├── 📂 result/                  # 출력: 분석 결과 JSON 저장소
│   └── result_*.json           # (자동 생성되는 분석 결과)
│
├── 📜 1_download_video.py      # 단계 1: 서버에서 영상 다운로드
├── 📜 2_analyze_video.py       # 단계 2: Gemini AI로 분석
├── 📜 3_upload_result.py       # 단계 3: 결과를 서버에 업로드
├── 📜 workflow_utils.py        # 🔧 중앙 로깅 관리 (모든 파일이 사용)
├── 📜 workflow_log.json        # 📊 워크플로우 상태 추적 (자동 생성)
└── 📜 README.md                # 이 파일
```

---

## 🚀 빠른 시작 (설치 후)

### 1️⃣ 가상환경 활성화

```powershell
# soft_guard 폴더로 이동
cd soft_guard

# 가상환경 활성화
.\soft_guard\Scripts\Activate.ps1
```

### 2️⃣ Google API 키 설정

```powershell
# Google Gemini API 키 설정 (필수)
$env:GOOGLE_API_KEY='여기에_본인의_API_키_입력'

# 확인
echo $env:GOOGLE_API_KEY
```

👉 **API 키 없으면?** [Google AI Studio](https://aistudio.google.com/app/apikey)에서 무료로 발급받을 수 있습니다.

### 3️⃣ 파이프라인 실행

```powershell
# 방법 1: 자동 모드 (추천 - 워크플로우 자동 연동)
python 1_download_video.py    # 서버에서 영상 다운로드
python 2_analyze_video.py     # 다운로드된 영상 자동 분석
python 3_upload_result.py     # 분석 결과 자동 업로드

# 방법 2: 수동 모드 (특정 파일 지정)
python 2_analyze_video.py The.mp4
python 3_upload_result.py result_The_00.json
```

---

## 📚 각 파일 상세 설명

### 🔧 `workflow_utils.py` - 중앙 로깅 시스템

**역할:** 모든 단계 간의 데이터를 `workflow_log.json`에서 관리

**주요 함수:**

| 함수 | 설명 |
|------|------|
| `init_workflow_log()` | 로그 파일 초기화 |
| `update_workflow_step(step, status, details)` | 단계 상태 업데이트 |
| `get_workflow_value(step, key)` | 이전 단계의 결과 읽기 |
| `set_workflow_value(step, key, value)` | 현재 단계 결과 저장 |

**예제:**
```python
from workflow_utils import get_workflow_value, set_workflow_value

# 이전 단계에서 저장한 파일 읽기
video_filename = get_workflow_value("download", "downloaded_video")

# 현재 단계 결과 저장 (다음 단계에서 사용)
set_workflow_value("analyze", "analyzed_result", "result_The_00.json")
```

---

### 📥 `1_download_video.py` - 서버에서 영상 다운로드

**서버 주소:** `https://softguard-ah9q.onrender.com`

**동작:**
1. 서버의 `/api/videos/pending` 에서 대기 중인 영상 목록 조회
2. 첫 번째 영상 다운로드 (`video/` 폴더에 저장)
3. 파일명을 `workflow_log.json`에 저장 (2번에서 자동 사용)

**특징:**
- ✅ 재시도 로직: 최대 3회, 2초 대기
- ✅ 서버 응답 검증: 상태 코드 + 리스트 형식 확인
- ✅ 오류 로깅: 모든 실패 상황이 `workflow_log.json`에 기록

**실행:**
```powershell
python 1_download_video.py
```

**예상 출력:**
```
📡 서버에 대기 중인 영상이 있는지 확인합니다...
🎯 타겟 영상 파일명: The.mp4
📥 다운로드 주소: https://softguard-ah9q.onrender.com/api/videos/download/The.mp4
✅ 다운로드 완료! 저장 위치: D:\jeong\soft_guard\video\The.mp4
```

---

### 🧠 `2_analyze_video.py` - Google Gemini AI로 분석

**AI 모델:** `gemini-2.5-pro` (멀티모달 분석)

**동작:**
1. `video/` 폴더에서 영상 자동 로드 (또는 CLI 인자로 지정)
2. Google Gemini에 업로드 & 처리 대기
3. AI가 11단계 프롬프트로 분석
4. 결과를 `result/` 폴더에 JSON으로 저장
5. 파일명을 `workflow_log.json`에 저장 (3번에서 자동 사용)

**자동 인식 항목:**
- ✅ 차량 종류 (승용차, 택시, 버스, 화물차, 오토바이, 자전거)
- ✅ 충돌 발생 여부 (`collision_happened`: true/false)
- ✅ 사고 유형 (`incident_type`: "collision" or "near_miss")
- ✅ 위험도 점수 (1~10점)
- ✅ 사고 발생 시간대

**특징:**
- 🚨 **Hallucination 방지:** 보행자 넘어짐 감지 시 자동으로 충돌로 판정
- 🎯 **높은 정확도:** 11단계 프롬프트로 미세한 상황까지 분석
- ⏱️ **타임아웃 방지:** 5분 이상 처리 시 자동 중단

**실행:**
```powershell
# 자동 모드 (1_download_video.py 실행 후)
python 2_analyze_video.py

# 수동 모드 (특정 파일 지정)
python 2_analyze_video.py The.mp4
```

**예상 출력:**
```
📥 이전 다운로드 파일 사용: The.mp4
🎬 영상 업로드 중: D:\jeong\soft_guard\video\The.mp4
......
🧠 AI 분석 중 (Gemini 2.5 Pro)...
✅ 분석 결과 저장 완료: D:\jeong\soft_guard\result\result_The_00.json
✅ 분석 완료. 다음 단계: python 3_upload_result.py
```

**JSON 출력 예제:**
```json
{
  "metadata": {
    "video_id": "The.mp4",
    "timestamp_in_video": "00:03-00:05"
  },
  "event_stream": {
    "event_title": "이면도로 무단횡단 아동 차량 충돌 사고",
    "risk_level": 9,
    "collision_happened": true,
    "incident_type": "collision"
  },
  "report_data": {
    "event_category": "차대사람",
    "severity_category": "중대 사고",
    "sequence_of_events": [
      "1. 아동이 우측에서 좌측으로 무단횡단 시도.",
      "2. 좌측에서 직진하던 검은색 승용차와 충돌함.",
      "3. 아동이 도로에 넘어짐."
    ]
  }
}
```

---

### 📤 `3_upload_result.py` - 분석 결과 업로드

**서버 주소:** `https://softguard-ah9q.onrender.com`

**동작:**
1. `result/` 폴더에서 분석 JSON 자동 로드 (또는 CLI 인자로 지정)
2. 서버의 `/api/results/upload`로 JSON 데이터 전송
3. 성공 여부를 `workflow_log.json`에 기록

**특징:**
- ✅ 재시도 로직: 최대 3회, 2초 대기
- ✅ 서버 응답 검증: 상태 코드 200/201만 성공으로 판정
- ✅ JSON 형식 전송: `multipart/form-data`가 아닌 `application/json` 사용

**실행:**
```powershell
# 자동 모드 (2_analyze_video.py 실행 후)
python 3_upload_result.py

# 수동 모드 (특정 파일 지정)
python 3_upload_result.py result_The_00.json
```

**예상 출력:**
```
📥 이전 분석 결과 사용: result_The_00.json
📤 업로드 준비 중: D:\jeong\soft_guard\result\result_The_00.json
🚀 서버로 전송 중... (https://softguard-ah9q.onrender.com/api/results/upload) - 시도 1/3
✅ 서버 업로드 성공!
서버 응답: {"status":"success","message":"분석 결과가 성공적으로 저장되었습니다.","videoId":"The.mp4"}
```

---

## 📊 워크플로우 로그 구조

`workflow_log.json` 자동 생성 & 업데이트:

```json
{
  "workflow_start": "2026-05-12T15:58:53.624509",
  "steps": {
    "download": {
      "status": "completed",
      "timestamp": "2026-05-12T16:20:55.096000",
      "details": {
        "downloaded_video": "The.mp4",
        "save_path": "D:\\jeong\\soft_guard\\video\\The.mp4"
      }
    },
    "analyze": {
      "status": "completed",
      "timestamp": "2026-05-12T16:29:10.692354",
      "details": {
        "input_video": "The.mp4",
        "output_result": "result_The_00.json"
      }
    },
    "upload": {
      "status": "completed",
      "timestamp": "2026-05-12T16:34:08.622255",
      "details": {
        "file": "result_The_00.json",
        "server_response": "{\"status\":\"success\"}"
      }
    }
  }
}
```

**상태 값:**
- `pending` - 대기 중
- `in_progress` - 진행 중
- `completed` - 완료
- `failed` - 실패 (에러 메시지 포함)

---

## ⚙️ Google API 키 & 추가 설정

### Google API 키 설정

#### 방법 1: 파워셸 (한 번만 설정)
```powershell
# 환경 변수 설정 (현재 세션에만 적용)
$env:GOOGLE_API_KEY='sk-proj-abc123...'

# 확인
echo $env:GOOGLE_API_KEY
```

#### 방법 2: 영구적 설정 (추천 - 관리자 권한 필요)
```powershell
# 시스템 환경 변수에 영구 등록
[System.Environment]::SetEnvironmentVariable('GOOGLE_API_KEY', 'sk-proj-abc123...', 'User')

# VS Code / 터미널 재시작 후 적용
```

#### 방법 3: .env 파일 사용 (팀 협업 시)

**파일 생성:** `soft_guard/.env`
```
GOOGLE_API_KEY=sk-proj-abc123...
SERVER_BASE_URL=https://softguard-ah9q.onrender.com
```

**파이썬 코드:**
```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
```

**주의:** `.env` 파일을 Git에 커밋하지 마세요! (`.gitignore`에 추가)
```
# .gitignore
.env
__pycache__/
*.pyc
```

---

## 📚 필수 라이브러리 정보

### 설치된 패키지

| 패키지 | 버전 | 용도 |
|--------|------|------|
| google-genai | 0.8.6+ | Google Gemini AI API |
| requests | 2.34.0+ | HTTP 통신 (다운로드/업로드) |
| python-dotenv | 1.0.0+ | .env 파일 관리 (선택) |

**설치 확인:**
```powershell
pip list
```

### requirements.txt 재생성 (나중에)

```powershell
# 현재 설치된 패키지를 requirements.txt에 저장
pip freeze > requirements.txt
```

---

## 📝 사용 예제

### 예제 1: 완전 자동화 (권장)

```powershell
# 1단계: 영상 다운로드
python 1_download_video.py

# 2단계: AI 분석 (자동으로 다운로드된 파일 사용)
python 2_analyze_video.py

# 3단계: 서버 업로드 (자동으로 분석 결과 파일 사용)
python 3_upload_result.py

# ✅ 완료! workflow_log.json에 모든 단계가 기록됨
```

### 예제 2: 특정 파일만 분석

```powershell
# 기존 영상 분석
python 2_analyze_video.py existing_video.mp4

# 기존 결과 업로드
python 3_upload_result.py result_existing_video_00.json
```

### 예제 3: 배치 처리 (여러 영상 반복)

```powershell
# PowerShell 스크립트: run_batch.ps1
foreach ($i in 1..5) {
    Write-Host "===== 라운드 $i 시작 ====="
    python 1_download_video.py
    if ($?) { python 2_analyze_video.py }
    if ($?) { python 3_upload_result.py }
    Start-Sleep -Seconds 10
}
```

실행:
```powershell
powershell -ExecutionPolicy RemoteSigned -File run_batch.ps1
```

---

## 🐛 문제 해결

### ❌ "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다"

```powershell
# 1. 환경 변수 확인
echo $env:GOOGLE_API_KEY

# 2. 설정되지 않았으면 설정
$env:GOOGLE_API_KEY='your-api-key-here'

# 3. 다시 실행
python 2_analyze_video.py
```

### ❌ "파일을 찾을 수 없습니다"

```powershell
# 1. video 또는 result 폴더 구조 확인
dir video
dir result

# 2. 파일명이 정확한지 확인
python 2_analyze_video.py The.mp4  # 정확한 파일명 입력
```

### ❌ "네트워크 오류: Connection refused"

```powershell
# 1. 인터넷 연결 확인
ping google.com

# 2. 서버 상태 확인 (브라우저에서 열기)
https://softguard-ah9q.onrender.com

# 3. 재시도 (자동 3회 재시도 포함)
python 1_download_video.py
```

### ❌ "영상 처리 시간 초과 (Timeout)"

```powershell
# 1. 더 작은 파일로 테스트
# 2. 나중에 다시 시도 (Gemini 서버 과부하 가능성)
# 3. 5분 타임아웃 제한값 증가 (2_analyze_video.py의 max_wait_time 수정)
```

### 📋 워크플로우 로그 초기화

```powershell
# 새로 시작하고 싶으면 로그 파일 삭제
rm workflow_log.json

# 다시 실행하면 새 로그 자동 생성
python 1_download_video.py
```

---

## 🎯 핵심 기능 요약

| 기능 | 설명 | 파일 |
|------|------|------|
| 자동 파일 추적 | workflow_log.json으로 단계 간 자동 연동 | workflow_utils.py |
| 재시도 로직 | 네트워크 오류 시 최대 3회 자동 재시도 | 1, 3번 |
| 응답 검증 | 서버 상태 코드 & 데이터 형식 검증 | 1, 3번 |
| AI 분석 | 11단계 프롬프트로 정밀 분석 | 2번 |
| 환각 방지 | 보행자 넘어짐 감지로 오탐지 방지 | 2번 |
| 타임아웃 | 5분 이상 무한 대기 방지 | 2번 |

---

## 📞 추가 정보

- **API 키 발급:** [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Gemini 모델 정보:** [Google Gemini Docs](https://ai.google.dev/docs)
- **프롬프트 튜닝:** `2_analyze_video.py`의 prompt 변수 수정

---

**마지막 업데이트:** 2026-05-12  
**상태:** ✅ 운영 중
