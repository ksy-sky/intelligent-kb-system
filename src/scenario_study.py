# src/scenario_study.py
"""
Сценарий 1: Самостоятельное изучение теоретического материала.
Реализует алгоритм обработки запросов, описанный в разделе 2.5 ПЗ.
"""
from typing import Dict, List, Any, Optional
from difflib import get_close_matches
from .kb_loader import KnowledgeBaseLoader


class StudyScenario:
    """Модуль глоссария, реализующий Сценарий 1."""

    def __init__(self, loader: KnowledgeBaseLoader):
        self.loader = loader

    @staticmethod
    def _normalize(text: str) -> str:
        """Нормализация входной строки (приведение к нижнему регистру, удаление лишних пробелов)."""
        return " ".join(text.lower().strip().split())

    def _detect_query_type(self, query: str) -> str:
        """
        Определение типа запроса:
        - 'topic' если запрос является идентификатором раздела (T01..T99 или L01..L99)
        - 'term' если запрос является названием термина
        """
        norm = query.strip().upper()
        if (norm.startswith("T") or norm.startswith("L")) and len(norm) >= 3 and norm[1:].isdigit():
            return "topic"
        return "term"

    def _find_entry(self, query: str) -> Optional[Dict[str, Any]]:
        """Поиск записи в базе знаний по термину или ID концепта."""
        norm = self._normalize(query)
        
        # Поиск по ID концепта (C001, CL015 и т.д.)
        if norm.upper().startswith("C") and len(norm) >= 4:
            return self.loader.get_concept(norm.upper())

        # Точный поиск по термину
        results = self.loader.search_by_term(norm)
        if results:
            return results[0]

        # Частичное совпадение (если точного нет)
        all_terms = [self._normalize(c["term"]) for c in self.loader.concepts_by_id.values()]
        matches = get_close_matches(norm, all_terms, n=3, cutoff=0.5)
        if matches:
            return {"_suggestions": matches}
        
        return None

    def _build_response(self, concept: Dict[str, Any]) -> str:
        """Формирование структурированного ответа (карточки термина)."""
        resolved = self.loader.resolve_relations(concept["concept_id"])
        relations = resolved.get("relations", {})
        
        # Иерархия
        hierarchy_lines = []
        for rel_key in ["надкласс", "составные части", "разбиение"]:
            targets = relations.get(rel_key, [])
            if targets:
                terms = [t.get("term", t.get("id", "")) for t in targets]
                hierarchy_lines.append(f"  - {rel_key.capitalize()}: {', '.join(terms)}")
        
        # Остальные связи
        other_lines = []
        for rel_key, targets in relations.items():
            if rel_key not in ["надкласс", "составные части", "разбиение"] and targets:
                terms = [t.get("term", t.get("id", "")) for t in targets]
                other_lines.append(f"  - {rel_key.capitalize()}: {', '.join(terms)}")

        # Сборка карточки
        lines = [
            f"\nПонятие: {concept.get('term', concept['concept_id'])}",
            f"ID: {concept['concept_id']} | Раздел: {concept.get('topic_id', '')}",
            "-" * 50,
            f"Определение: {concept.get('definition', 'Не задано')}",
        ]
        if hierarchy_lines:
            lines.append("\nИерархия:")
            lines.extend(hierarchy_lines)
        if other_lines:
            lines.append("\nСвязи:")
            lines.extend(other_lines)
        
        examples = concept.get("examples", [])
        if examples:
            lines.append("\nПримеры:")
            lines.extend(f"  - {ex}" for ex in examples)
            
        lines.append("-" * 50 + "\n")
        return "\n".join(lines)

    def handle_query(self, query: str) -> str:
        """Основной обработчик запроса пользователя."""
        if not query.strip():
            return "Введите запрос."

        q_type = self._detect_query_type(query)

        if q_type == "topic":
            tid = query.strip().upper()
            topics = self.loader.get_topics_index()
            topic_info = topics.get(tid)
            if not topic_info:
                return f"Раздел '{tid}' не найден."
            
            concept_ids = topic_info.get("concept_ids", [])
            if not concept_ids:
                return f"Раздел '{tid}' не содержит понятий."
                
            terms_list = [
                self.loader.get_concept(cid)["term"] 
                for cid in concept_ids 
                if self.loader.get_concept(cid)
            ]
            return (
                f"\nРаздел {tid}: {topic_info['title']}\n"
                f"Всего понятий: {len(terms_list)}\n" +
                "\n".join(f"  - {t}" for t in sorted(terms_list)) +
                f"\nВведите термин или ID для подробного изучения.\n"
            )

        # Поиск термина
        entry = self._find_entry(query)
        if not entry:
            return f"Термин '{query}' не найден в базе знаний."
        
        if "_suggestions" in entry:
            return (
                f"Точного совпадения для '{query}' нет.\n"
                f"Возможно, вы имели в виду: {', '.join(entry['_suggestions'])}"
            )

        return self._build_response(entry)