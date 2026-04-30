# src/kb_loader.py
import json
import os
from typing import Dict, List, Any, Optional
from .kb_validator import validate_kb, KBValidationError

class KnowledgeBaseLoader:
    """
    Центральный загрузчик БЗ. 
    Читает JSON, валидирует, строит in-memory индексы и предоставляет 
    быстрый доступ для сценариев (Glossary, Study, Assistant).
    """
    def __init__(self, file_paths: List[str]):
        self.file_paths = file_paths
        self.concepts_by_id: Dict[str, Dict[str, Any]] = {}
        self.concepts_by_term: Dict[str, List[Dict[str, Any]]] = {}
        self.topics_index: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, Any] = {}
        self._is_loaded = False

    def load(self) -> Dict[str, Any]:
        """Загружает, валидирует и индексирует БЗ. Вызывается один раз при старте."""
        raw_data = self._merge_json_files()
        validate_kb(raw_data)
        self._build_indexes(raw_data)
        self._is_loaded = True
        return self.get_state_summary()

    def _merge_json_files(self) -> Dict[str, Any]:
        merged = {"metadata": None, "topics": []}
        for path in self.file_paths:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Файл БЗ не найден: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("metadata"):
                merged["metadata"] = data["metadata"]
            merged["topics"].extend(data.get("topics", []))
        return merged

    def _build_indexes(self, data: Dict[str, Any]):
        self.concepts_by_id.clear()
        self.concepts_by_term.clear()
        self.topics_index.clear()

        for topic in data.get("topics", []):
            tid = str(topic.get("topic_id", "")).strip()
            if not tid:
                continue
            
            self.topics_index[tid] = {
                "title": topic.get("title", "").strip(),
                "concept_ids": []
            }

            for concept in topic.get("concepts", []):
                cid = str(concept.get("concept_id", "")).strip()
                term = str(concept.get("term", "")).strip().lower()
                if not cid:
                    continue

                # Храним копию, чтобы сценарии не мутировали исходные данные
                c_copy = {k: v for k, v in concept.items()}
                self.concepts_by_id[cid] = c_copy
                
                # Индекс по термину (регистронезависимо, допускает омонимы из разных тем)
                self.concepts_by_term.setdefault(term, []).append(c_copy)
                self.topics_index[tid]["concept_ids"].append(cid)

        self.metadata = data.get("metadata", {})

    # === PUBLIC API (вызывается другими модулями) ===
    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Сырой концепт по ID."""
        return self.concepts_by_id.get(concept_id)

    def search_by_term(self, term: str) -> List[Dict[str, Any]]:
        """Поиск концептов по термину (точное совпадение, регистронезависимо)."""
        return self.concepts_by_term.get(term.lower().strip(), [])

    def get_topics_index(self) -> Dict[str, Dict[str, Any]]:
        """Карта тем: topic_id -> {title, concept_ids}."""
        return self.topics_index

    def resolve_relations(self, concept_id: str) -> Dict[str, Any]:
        """
        Возвращает концепт с разрешёнными связями.
        ID в relations заменяются на {"id": "C001", "term": "Термин"}.
        Литеральные строки остаются как {"id": None, "term": "строка"}.
        """
        concept = self.get_concept(concept_id)
        if not concept or "relations" not in concept:
            return concept or {}

        resolved = concept.copy()
        resolved_relations = {}
        
        for rel_type, targets in concept["relations"].items():
            resolved_targets = []
            for t in targets:
                t_clean = t.strip()
                if t_clean in self.concepts_by_id:
                    target_c = self.concepts_by_id[t_clean]
                    resolved_targets.append({
                        "id": t_clean,
                        "term": target_c.get("term", t_clean)
                    })
                else:
                    resolved_targets.append({"id": None, "term": t_clean})
            resolved_relations[rel_type] = resolved_targets
            
        resolved["relations"] = resolved_relations
        return resolved

    def get_state_summary(self) -> Dict[str, Any]:
        """Возвращает статистику загрузки для логирования."""
        return {
            "concepts_count": len(self.concepts_by_id),
            "topics_count": len(self.topics_index),
            "metadata": self.metadata,
            "is_loaded": self._is_loaded
        }