"""Candidate persistence helpers for BOSS resume screening."""
import json
import os
import shutil


CANDIDATES_FILE = "candidates_all.json"
BACKUP_FILE = CANDIDATES_FILE + ".bak"


def load_candidates_all():
    """加载候选人数据；主文件损坏时自动尝试从 .bak 恢复。"""
    if os.path.exists(CANDIDATES_FILE):
        try:
            with open(CANDIDATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"加载候选人数据失败：{e}")
            restored = _load_candidates_backup()
            if restored is not None:
                try:
                    shutil.copy2(BACKUP_FILE, CANDIDATES_FILE)
                    print(f"已从 {BACKUP_FILE} 恢复候选人数据")
                except OSError as restore_error:
                    print(f"恢复候选人备份失败：{restore_error}")
                return restored
    return []


def _load_candidates_backup():
    """加载备份文件；不存在或损坏时返回 None。"""
    if not os.path.exists(BACKUP_FILE):
        return None
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"加载候选人备份失败：{e}")
        return None


def get_greeted_geek_ids(candidates_all):
    """从 candidates_all 中提取已打招呼的 geek_id 集合。"""
    return set(c['geek_id'] for c in candidates_all if c.get('greet_sent') is True)


def save_candidates_all(candidates_all):
    """保存 candidates_all.json，支持去重、中断恢复和 .bak 备份。"""
    unique_candidates = _dedupe_candidates(candidates_all)

    if os.path.exists(CANDIDATES_FILE):
        try:
            shutil.copy2(CANDIDATES_FILE, BACKUP_FILE)
        except OSError as e:
            print(f"备份候选人数据失败：{e}")

    tmp_file = CANDIDATES_FILE + ".tmp"
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(unique_candidates, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, CANDIDATES_FILE)
    print(f"已更新 {CANDIDATES_FILE} (共 {len(unique_candidates)} 个唯一候选人)")


def _dedupe_candidates(candidates_all):
    """按 (geek_id, job_name) 去重，并合并打招呼状态。"""
    seen = {}

    for c in candidates_all:
        geek_id = c.get('geek_id')
        job_name = c.get('job_name', '')
        if geek_id:
            key = (geek_id, job_name)
            if key not in seen:
                seen[key] = c
            else:
                old_c = seen[key]
                if c.get('match_score', 0) > old_c.get('match_score', 0) or c.get('greet_sent', False):
                    if old_c.get('greet_sent', False) and not c.get('greet_sent', False):
                        c['greet_sent'] = True
                    if old_c.get('greeting_in_progress', False):
                        c['greeting_in_progress'] = True
                    seen[key] = c

    unique_candidates = list(seen.values())

    for c in unique_candidates:
        if c.get('greeting_in_progress') and c.get('greet_sent'):
            del c['greeting_in_progress']

    return unique_candidates


def is_already_greeted(candidates_all, geek_id, job_name=None):
    """检查是否已打过招呼，支持 (geek_id, job_name) 复合键。"""
    for c in candidates_all:
        if c.get('geek_id') == geek_id and c.get('greet_sent') is True:
            if job_name is not None:
                if c.get('job_name', '') == job_name:
                    return True
            else:
                return True
    return False
