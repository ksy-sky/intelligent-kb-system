"""Общая тестовая БЗ для тестов сценариев 4, 5, 6 (небольшая, детерминированная, без файлов).

Иерархия:
    C001 Данные
     ├─ C002 Информация ── C004 Факт
     └─ C003 Знания
    C006 Фрагмент  «используется в» C004   (значит C006 — пререквизит для C004)
    C007 Гибрид    надкласс: C002 и C003   (множественное наследование)
    C005 Изолированное — без связей, другой раздел
    C008 Целое  «составные части»: C009 Часть
    CL001 / C010 — омонимы «Ссылка» (теория и лаба)
"""
import copy
from typing import Dict, List

BASE_CONCEPTS: Dict[str, dict] = {
    "C001": {"concept_id": "C001", "term": "Данные", "topic_id": "T01",
             "definition": "Сведения, представленные в формализованном виде для обработки.",
             "examples": ["таблица значений"], "relations": {}},
    "C002": {"concept_id": "C002", "term": "Информация", "topic_id": "T01",
             "definition": "Осмысленные данные, снижающие неопределённость у получателя.",
             "examples": ["новость"], "relations": {"надкласс": ["C001"], "свойства": ["полезность", "достоверность"]}},
    "C003": {"concept_id": "C003", "term": "Знания", "topic_id": "T01",
             "definition": "Проверенная и структурированная информация, пригодная для решения задач.",
             "examples": [], "relations": {"надкласс": ["C001"], "свойства": ["достоверность", "системность"]}},
    "C004": {"concept_id": "C004", "term": "Факт", "topic_id": "T01",
             "definition": "Единичное подтверждённое утверждение о событии или объекте.",
             "examples": ["вода кипит при 100 градусах"], "relations": {"надкласс": ["C002"]}},
    "C005": {"concept_id": "C005", "term": "Изолированное понятие", "topic_id": "T02",
             "definition": "Понятие без каких-либо связей с остальной базой знаний.",
             "examples": [], "relations": {}},
    "C006": {"concept_id": "C006", "term": "Фрагмент", "topic_id": "T02",
             "definition": "Небольшая часть текста, взятая для анализа отдельно от целого.",
             "examples": [], "relations": {"используется в": ["C004"]}},
    "C007": {"concept_id": "C007", "term": "Гибрид", "topic_id": "T01",
             "definition": "Понятие, наследующее свойства сразу двух надклассов.",
             "examples": [], "relations": {"надкласс": ["C002", "C003"]}},
    "C008": {"concept_id": "C008", "term": "Целое", "topic_id": "T03",
             "definition": "Объект, состоящий из нескольких взаимосвязанных частей.",
             "examples": [], "relations": {"составные части": ["C009"]}},
    "C009": {"concept_id": "C009", "term": "Часть", "topic_id": "T03",
             "definition": "Элемент, входящий в состав более крупного объекта.",
             "examples": [], "relations": {}},
    "C010": {"concept_id": "C010", "term": "Ссылка", "topic_id": "T03",
             "definition": "Указатель на другой объект в структуре данных.",
             "examples": [], "relations": {}},
    "CL001": {"concept_id": "CL001", "term": "Ссылка", "topic_id": "L01",
              "definition": "Группа, на которую можно сослаться в регулярном выражении.",
              "examples": [], "relations": {}},
    "C011": {"concept_id": "C011", "term": "Без определения", "topic_id": "T02",
             "definition": "", "examples": [], "relations": {"надкласс": ["C001"]}},
}


def make_concepts(**overrides) -> Dict[str, dict]:
    """Копия БЗ; overrides = {id: dict | None}: dict обновляет концепт, None удаляет."""
    concepts = copy.deepcopy(BASE_CONCEPTS)
    for cid, patch in overrides.items():
        if patch is None:
            concepts.pop(cid, None)
        elif cid in concepts:
            concepts[cid].update(patch)
        else:
            concepts[cid] = {"concept_id": cid, "term": cid, "topic_id": "T01",
                             "definition": "", "examples": [], "relations": {}, **patch}
    return concepts


class FakeLoader:
    """Минимальная замена KnowledgeBaseLoader для решателей и роутера."""

    def __init__(self, concepts: Dict[str, dict] = None, labs: Dict[str, List[str]] = None):
        self.concepts_by_id = concepts if concepts is not None else make_concepts()
        self.concepts_by_term: Dict[str, List[str]] = {}
        for cid, c in self.concepts_by_id.items():
            self.concepts_by_term.setdefault(c["term"].lower(), []).append(cid)
        self.topics_index = {
            "T01": {"title": "Основы"}, "T02": {"title": "Разное"},
            "T03": {"title": "Структуры"}, "L01": {"title": "Лаба 1"},
        }
        self._labs = labs or {}

    def search_by_term(self, term):
        return [self.concepts_by_id[i] for i in self.concepts_by_term.get(term.lower(), [])]

    def get_topics_index(self):
        return self.topics_index

    def get_related_labs(self, cid):
        return list(self._labs.get(cid, []))

    def get_concept(self, cid):
        return self.concepts_by_id.get(cid)
