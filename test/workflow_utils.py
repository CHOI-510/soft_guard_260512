import json
import os
from datetime import datetime

# ⭐ 여기를 절대 경로로 수정했습니다!
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_LOG = os.path.join(SCRIPT_DIR, "workflow_log.json")

def init_workflow_log():
    """워크플로우 로그 초기화"""
    if not os.path.exists(WORKFLOW_LOG):
        log_data = {
            "workflow_start": datetime.now().isoformat(),
            "steps": {}
        }
        with open(WORKFLOW_LOG, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

def update_workflow_step(step_name, status, details=None):
    """워크플로우 스텝 업데이트"""
    init_workflow_log()
    
    with open(WORKFLOW_LOG, "r", encoding="utf-8") as f:
        log_data = json.load(f)
    
    log_data["steps"][step_name] = {
        "status": status,  # "pending", "in_progress", "completed", "failed"
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    
    with open(WORKFLOW_LOG, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def get_workflow_value(step_name, key):
    """워크플로우에서 특정 값 조회"""
    if not os.path.exists(WORKFLOW_LOG):
        return None
    
    with open(WORKFLOW_LOG, "r", encoding="utf-8") as f:
        log_data = json.load(f)
    
    if step_name in log_data["steps"] and key in log_data["steps"][step_name].get("details", {}):
        return log_data["steps"][step_name]["details"][key]
    return None

def set_workflow_value(step_name, key, value):
    """워크플로우에 특정 값 저장"""
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