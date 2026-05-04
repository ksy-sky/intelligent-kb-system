# tests/test_scenario_study.py
import unittest
import os
import sys
from unittest.mock import patch

# Добавляем корень проекта в sys.path для корректных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scenario_study import StudyScenario


class TestStudyModule(unittest.TestCase):
    """Unit-тесты для Сценария 1 на стандартной библиотеке unittest."""

    # Моковые данные, имитирующие состояние KnowledgeBaseLoader
    MOCK_CONCEPTS = {
        "C001": {"concept_id": "C001", "term": "Технология", "topic_id": "T01", "definition": "Совокупность методов.", "relations": {"разбиение": ["C002"]}, "examples": []},
        "C002": {"concept_id": "C002", "term": "Информационная технология", "topic_id": "T01", "definition": "Обработка данных.", "relations": {"надкласс": ["C001"]}, "examples": ["IT"]},
        "C003": {"concept_id": "C003", "term": "Онтология", "topic_id": "T02", "definition": "Формальная спецификация.", "relations": {"используется в": ["C150"]}, "examples": []},
        "CL001": {"concept_id": "CL001", "term": "Регулярные выражения", "topic_id": "L01", "definition": "Шаблоны поиска.", "relations": {"составные части": ["CL002"]}, "examples": []}
    }

    MOCK_TOPICS = {
        "T01": {"title": "Основы", "concept_ids": ["C001", "C002"]},
        "T02": {"title": "Semantic Web", "concept_ids": ["C003"]},
        "L01": {"title": "Регулярки", "concept_ids": ["CL001"]}
    }

    class MockLoader:
        """Имитация KnowledgeBaseLoader для изоляции тестов."""
        def __init__(self):
            self.concepts_by_id = TestStudyModule.MOCK_CONCEPTS

        def get_concept(self, cid):
            return self.concepts_by_id.get(cid)

        def search_by_term(self, term):
            term_lower = term.lower().strip()
            return [c for c in self.concepts_by_id.values() if c["term"].lower() == term_lower]

        def get_topics_index(self):
            return TestStudyModule.MOCK_TOPICS

        def resolve_relations(self, cid):
            concept = self.get_concept(cid)
            if not concept:
                return {}
            resolved = concept.copy()
            resolved_relations = {}
            for rel_type, targets in concept.get("relations", {}).items():
                resolved_targets = []
                for t in targets:
                    t_clean = t.strip()
                    if t_clean in self.concepts_by_id:
                        resolved_targets.append({"id": t_clean, "term": self.concepts_by_id[t_clean]["term"]})
                    else:
                        resolved_targets.append({"id": None, "term": t_clean})
                resolved_relations[rel_type] = resolved_targets
            resolved["relations"] = resolved_relations
            return resolved

    def setUp(self):
        """Вызывается перед каждым тестом (аналог pytest.fixture)."""
        self.loader = self.MockLoader()
        self.scenario = StudyScenario(self.loader)

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================
    def test_normalize_text(self):
        self.assertEqual(self.scenario._normalize("  JSON  "), "json")
        self.assertEqual(self.scenario._normalize("Технология"), "технология")
        self.assertEqual(self.scenario._normalize("Test   String"), "test string")
        self.assertEqual(self.scenario._normalize("  C001  "), "c001")

    def test_detect_query_type_topic_id(self):
        self.assertEqual(self.scenario._detect_query_type("T01"), "topic")
        self.assertEqual(self.scenario._detect_query_type("  l05  "), "topic")
        self.assertEqual(self.scenario._detect_query_type("T99"), "topic")

    def test_detect_query_type_term(self):
        self.assertEqual(self.scenario._detect_query_type("Онтология"), "term")
        self.assertEqual(self.scenario._detect_query_type("C001"), "term")
        self.assertEqual(self.scenario._detect_query_type("JSON формат"), "term")

    # ========================================================================
    # Поиск записей (_find_entry)
    # ========================================================================
    def test_find_entry_by_concept_id(self):
        entry = self.scenario._find_entry("C001")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["concept_id"], "C001")
        self.assertEqual(entry["term"], "Технология")

    def test_find_entry_by_term(self):
        entry = self.scenario._find_entry("Онтология")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["concept_id"], "C003")
        self.assertEqual(entry["definition"], "Формальная спецификация.")

    def test_find_entry_case_insensitive(self):
        entry = self.scenario._find_entry("технология")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["concept_id"], "C001")

    def test_find_entry_not_found(self):
        self.assertIsNone(self.scenario._find_entry("НесуществующийТермин"))

    def test_find_entry_with_suggestions(self):
        with patch('src.scenario_study.get_close_matches', return_value=["Технология"]):
            entry = self.scenario._find_entry("Технологи")
            self.assertIsNotNone(entry)
            self.assertIn("_suggestions", entry)
            self.assertIn("Технология", entry["_suggestions"])

    # ========================================================================
    # Основной обработчик (handle_query)
    # ========================================================================
    def test_handle_query_topic(self):
        result = self.scenario.handle_query("T01")
        self.assertIn("Раздел T01: Основы", result)
        self.assertIn("Всего понятий: 2", result)
        self.assertIn("Технология", result)
        self.assertIn("Информационная технология", result)

    def test_handle_query_topic_not_found(self):
        result = self.scenario.handle_query("T99")
        self.assertIn("не найден", result)

    def test_handle_query_term_success(self):
        result = self.scenario.handle_query("Онтология")
        self.assertIn("Понятие: Онтология", result)
        self.assertIn("Определение: Формальная спецификация.", result)
        self.assertIn("Используется в: C150", result)

    def test_handle_query_with_examples(self):
        result = self.scenario.handle_query("Информационная технология")
        self.assertIn("Примеры:", result)
        self.assertIn("IT", result)

    def test_handle_query_empty(self):
        result = self.scenario.handle_query("")
        self.assertIn("Введите запрос.", result)

    def test_handle_query_whitespace_only(self):
        result = self.scenario.handle_query("   ")
        self.assertIn("Введите запрос.", result)

    def test_handle_query_not_found(self):
        result = self.scenario.handle_query("НесуществующийТермин")
        self.assertIn("не найден в базе знаний", result)

    def test_handle_query_suggestions(self):
        with patch('src.scenario_study.get_close_matches', return_value=["Технология"]):
            result = self.scenario.handle_query("Технологи")
            self.assertIn("Точного совпадения для 'Технологи' нет.", result)
            self.assertIn("Возможно, вы имели в виду: Технология", result)

    def test_concept_id_vs_term_in_handle_query(self):
        result = self.scenario.handle_query("C001")
        self.assertIn("Понятие: Технология", result)
        self.assertIn("ID: C001", result)

    # ========================================================================
    # Форматирование ответа (_build_response)
    # ========================================================================
    def test_build_response_hierarchy(self):
        concept = self.MOCK_CONCEPTS["C002"]
        response = self.scenario._build_response(concept)
        self.assertIn("Иерархия:", response)
        self.assertIn("Надкласс: Технология", response)

    def test_build_response_hierarchy_with_breakdown(self):
        concept = self.MOCK_CONCEPTS["C001"]
        response = self.scenario._build_response(concept)
        self.assertIn("Иерархия:", response)
        self.assertIn("Разбиение: Информационная технология", response)

    def test_build_response_other_relations(self):
        # C003 имеет связь "используется в", которая попадает в раздел "Связи:"
        concept = self.MOCK_CONCEPTS["C003"]
        response = self.scenario._build_response(concept)
        self.assertIn("Связи:", response)
        self.assertIn("Используется в: C150", response)


if __name__ == "__main__":
    unittest.main()