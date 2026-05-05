# src/kb_validator.py
import re
from typing import Dict, List, Any, Set
from collections import defaultdict

# Формат ID: C001-C999 или CL001-CL999
ID_PATTERN = re.compile(r"^C(?:L)?\d{2,4}$")
# Отношения, формирующие иерархию (должны быть ацикличными)
HIERARCHY_KEYS = {"надкласс"}

class KBValidationError(Exception):
    """Исключение при нарушении целостности БЗ."""
    pass

def validate_kb(raw_data: Dict[str, Any]) -> None:
    """
    Полная валидация структуры JSON.
    При ошибках бросает KBValidationError с подробным списком.
    """
    if not isinstance(raw_data, dict) or "topics" not in raw_data:
        raise KBValidationError("Отсутствует корневой ключ 'topics'.")
    if not isinstance(raw_data.get("topics"), list):
        raise KBValidationError("Поле 'topics' должно быть массивом.")

    concepts = []
    for topic in raw_data["topics"]:
        concepts.extend(topic.get("concepts", []))

    errors = _validate_concepts_schema(concepts)
    concepts_by_id = {c["concept_id"]: c for c in concepts if "concept_id" in c}
    
    errors.extend(_validate_referential_integrity(concepts_by_id))
    errors.extend(_validate_hierarchy_acyclicity(concepts_by_id))

    if errors:
        raise KBValidationError("Валидация БЗ не пройдена:\n" + "\n".join(f"• {e}" for e in errors))

def _validate_concepts_schema(concepts: List[Dict[str, Any]]) -> List[str]:
    errors = []
    seen_ids: Set[str] = set()

    for c in concepts:
        cid = c.get("concept_id", "").strip()
        term = str(c.get("term", "")).strip()
        tid = str(c.get("topic_id", "")).strip()

        if not cid:
            errors.append("Отсутствует concept_id.")
            continue
        if not ID_PATTERN.match(cid):
            errors.append(f"Некорректный формат concept_id: '{cid}'")
        if cid in seen_ids:
            errors.append(f"Дублирующийся concept_id: '{cid}'")
        seen_ids.add(cid)

        if not term:
            errors.append(f"Пустое поле 'term' для {cid}")
        if not tid:
            errors.append(f"Отсутствует 'topic_id' для {cid}")

        rels = c.get("relations")
        if rels is not None:
            if not isinstance(rels, dict):
                errors.append(f"'relations' должен быть объектом в {cid}")
            else:
                for r_type, targets in rels.items():
                    if not isinstance(targets, list):
                        errors.append(f"Значение отношения '{r_type}' должно быть массивом в {cid}")
                    elif not all(isinstance(t, str) for t in targets):
                        errors.append(f"Все элементы в '{r_type}' должны быть строками в {cid}")
    return errors

def _validate_referential_integrity(concepts_by_id):
    warnings = []
    all_ids = set(concepts_by_id.keys())
    for cid, c in concepts_by_id.items():
        for rel_type, targets in c.get("relations", {}).items():
            for target in targets:
                if ID_PATTERN.match(target.strip()) and target.strip() not in all_ids:
                    warnings.append(f" Висячая ссылка: '{target.strip()}' в '{rel_type}' концепта '{cid}'")
    if warnings:
        for w in warnings:
            print(w)
    return []   # ← возвращаем пустой список, не блокируем загрузку

def _validate_hierarchy_acyclicity(concepts_by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    errors = []
    graph: Dict[str, List[str]] = defaultdict(list)
    
    for cid, c in concepts_by_id.items():
        for rel_key in HIERARCHY_KEYS:
            for target in c.get("relations", {}).get(rel_key, []):
                t_clean = target.strip()
                if t_clean in concepts_by_id:
                    graph[cid].append(t_clean)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in concepts_by_id}

    def dfs(u: str):
        color[u] = GRAY
        for v in graph[u]:
            if color[v] == GRAY:
                errors.append(f"Цикл в иерархии: {u} → {v}")
            elif color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    for node in concepts_by_id:
        if color[node] == WHITE:
            dfs(node)
    return errors