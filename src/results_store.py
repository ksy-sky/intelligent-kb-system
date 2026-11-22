"""
results_store.py — хранилище результатов диагностики (сценарий 4) для аналитики (сценарий 8).

Не зависит от интерфейса (консоль, Streamlit): один JSON на строку, файл только дописывается.
Роутер остаётся без состояния — хранение живёт здесь.
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(PROJECT_ROOT, "data", "results", "diagnostics.jsonl")


def save_diagnostic(student: str, result: Dict[str, Any], path: str = STORE_PATH) -> bool:
    """Сохраняет итог диагностики (data из ответа роутера на diagnose с answers).
    Возвращает False, если сохранять нечего (ошибка или цель без пререквизитов)."""
    if not result.get("prerequisites"):
        return False
    record = {
        "student": (student or "аноним").strip() or "аноним",
        "time": datetime.now().isoformat(timespec="seconds"),
        "target_id": result["target_id"],
        "prerequisites": result["prerequisites"],   # то, что реально проверялось
        "mastered": result["mastered"],
        "gaps": result["gaps"],
        "unanswered": result["unanswered"],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def load_latest(target_id: Optional[str] = None, path: str = STORE_PATH) -> List[Dict[str, Any]]:
    """Последняя запись каждого студента (по цели, если указана). Битые строки пропускаются."""
    if not os.path.exists(path):
        return []
    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if target_id and r.get("target_id") != target_id:
                continue
            latest[(r["student"], r["target_id"])] = r      # более поздняя запись перезаписывает
    return list(latest.values())


def list_targets(path: str = STORE_PATH) -> Dict[str, int]:
    """{target_id: число студентов} — для выбора цели на странице аналитики."""
    counts: Dict[str, int] = {}
    for r in load_latest(None, path):
        counts[r["target_id"]] = counts.get(r["target_id"], 0) + 1
    return counts


def to_analytics_params(records: List[Dict[str, Any]], threshold: float = 0.5) -> Dict[str, Any]:
    """Записи -> params для действия analytics. Цель сама не проверялась, поэтому в target_concepts
    только проверявшиеся пререквизиты."""
    targets: List[str] = []
    for r in records:
        for c in r["prerequisites"]:
            if c not in targets:
                targets.append(c)
    return {"student_models": [list(r["mastered"]) for r in records],
            "target_concepts": targets, "threshold": threshold}
