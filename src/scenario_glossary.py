"""
scenario_glossary.py — модуль реализации Сценария 2 «Использование глоссария».
Реализован в виде класса с внедрением зависимости KnowledgeBaseLoader.
"""
import re
from difflib import get_close_matches
from typing import Optional, List, Dict, Any
from src.kb_loader import KnowledgeBaseLoader


def normalize_text(text: str) -> str:
    """Утилита: приводит строку к нижнему регистру, убирает лишние пробелы."""
    return re.sub(r'\s+', ' ', text.strip().lower())


class GlossaryScenario:
    """Сценарий 2: Поиск и просмотр терминов базы знаний."""

    def __init__(self, loader: KnowledgeBaseLoader):
        """
        Инициализация сценария.
        :param loader: Экземпляр загруженной базы знаний (внедряется из main).
        """
        self.loader = loader

    def _resolve_id(self, value: str) -> str:
        """
        Если значение — ID концепта (C001/CL001), возвращает его термин.
        Иначе возвращает исходную строку.
        """
        if re.match(r"^C(?:L)?\d{2,4}$", value.strip()):
            concept = self.loader.get_concept(value.strip().upper())
            if concept:
                return concept.get("term", value)
        return value

    def _get_pool_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Возвращает список концептов в зависимости от источника."""
        if source == "theory":
            return list(self.loader.concepts_by_id.values())
        elif source == "labs":
            return list(self.loader.concepts_by_id.values())
        else:
            return list(self.loader.concepts_by_id.values())

    def find_entry_by_label(self, term: str, source: str = "all") -> Optional[Dict[str, Any]]:
        """
        Точный поиск концепта по термину или ID.
        """
        normalized = normalize_text(term)
        
        # 1. Попытка поиска по ID (через индекс лоадера O(1))
        if re.match(r"^C(?:L)?\d{2,4}$", term.strip().upper()):
            concept = self.loader.get_concept(term.strip().upper())
            if concept:
                return self._enrich_concept(concept)

        candidates = self.loader.search_by_term(normalized)
        
        if candidates:
            if source != "all":
                for c in candidates:
                    tid = c.get("topic_id", "")
                    is_theory = tid.startswith("T")
                    if (source == "theory" and is_theory) or (source == "labs" and not is_theory):
                        return self._enrich_concept(c)
                return None
            
            return self._enrich_concept(candidates[0])

        return None

    def _enrich_concept(self, concept: Dict[str, Any]) -> Dict[str, Any]:
        """Добавляет вычисляемые поля (topic_title, source) к концепту."""
        enriched = dict(concept)
        
        tid = enriched.get("topic_id", "")
        topics = self.loader.get_topics_index()
        topic_info = topics.get(tid, {})
        
        enriched["topic_title"] = topic_info.get("title", "Неизвестный раздел")
        enriched["source"] = "theory" if tid.startswith("T") else "labs"
        
        return enriched

    def get_similar_terms(self, term: str, n: int = 5, source: str = "all") -> List[str]:
        """Нечёткий поиск похожих терминов."""
        all_terms = list(self.loader.concepts_by_term.keys())
        
        if source != "all":
            filtered_terms = []
            for t in all_terms:
                candidates = self.loader.search_by_term(t)
                if candidates:
                    tid = candidates[0].get("topic_id", "")
                    is_theory = tid.startswith("T")
                    if (source == "theory" and is_theory) or (source == "labs" and not is_theory):
                        filtered_terms.append(t)
            all_terms = filtered_terms

        return get_close_matches(term, all_terms, n=n, cutoff=0.4)

    def search_term(self, term: str, source: str = "all") -> Dict[str, Any]:
        """
        Основной метод сценария: поиск термина и формирование ответа.
        """
        if not term or not term.strip():
            return {
                "found": False,
                "term": term,
                "message": "Введён пустой запрос.",
                "similar_terms": [],
            }

        entry = self.find_entry_by_label(term, source=source)

        if entry:
            resolved_relations = {}
            raw_relations = entry.get("relations", {})
            for rel_type, targets in raw_relations.items():
                resolved_relations[rel_type] = [self._resolve_id(t) for t in targets]

            return {
                "found": True,
                "term": entry.get("term"),
                "concept_id": entry.get("concept_id"),
                "topic_id": entry.get("topic_id"),
                "topic_title": entry.get("topic_title"),
                "source": entry.get("source"),
                "definition": entry.get("definition", "Определение отсутствует."),
                "relations": resolved_relations,
                "examples": entry.get("examples", []),
            }
        else:
            similar = self.get_similar_terms(term, source=source)
            return {
                "found": False,
                "term": term,
                "message": "Термин не найден в базе знаний.",
                "similar_terms": similar,
            }

    def get_all_terms(self, source: str = "all") -> List[str]:
        """Возвращает отсортированный список всех терминов."""
        terms = list(self.loader.concepts_by_term.keys())
        return sorted(terms, key=lambda x: x.lower())

    def get_terms_by_topic(self, topic_id: str) -> List[Dict[str, Any]]:
        """Возвращает концепты указанного раздела."""
        topics = self.loader.get_topics_index()
        concept_ids = topics.get(topic_id, {}).get("concept_ids", [])
        
        result = []
        for cid in concept_ids:
            concept = self.loader.get_concept(cid)
            if concept:
                result.append(self._enrich_concept(concept))
        return result

    def get_stats(self) -> Dict[str, int]:
        """Статистика базы знаний."""
        all_concepts = list(self.loader.concepts_by_id.values())
        theory_count = sum(1 for c in all_concepts if c.get("topic_id", "").startswith("T"))
        labs_count = sum(1 for c in all_concepts if c.get("topic_id", "").startswith("L"))
        
        topics = self.loader.get_topics_index()
        theory_topics = sum(1 for tid in topics if tid.startswith("T"))
        labs_topics = sum(1 for tid in topics if tid.startswith("L"))

        return {
            "theory_concepts": theory_count,
            "labs_concepts": labs_count,
            "total": len(all_concepts),
            "theory_topics": theory_topics,
            "labs_topics": labs_topics,
        }
