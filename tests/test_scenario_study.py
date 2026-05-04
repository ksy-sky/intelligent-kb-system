# tests/test_scenario_study.py
import pytest
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scenario_study import StudyScenario


class TestStudyModule:
    """Полный набор Unit-тестов для модуля изучения материала (Сценарий 1)."""

    # Моковые данные, имитирующие внутреннее состояние KnowledgeBaseLoader
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
        """Имитация KnowledgeBaseLoader для полной изоляции тестов."""
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

    @pytest.fixture(autouse=True)
    def setup_scenario(self):
        """Автоматически создаёт экземпляр StudyScenario с моковым загрузчиком."""
        self.loader = self.MockLoader()
        self.scenario = StudyScenario(self.loader)
        yield

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================
    def test_normalize_text(self):
        """Нормализация: trim, lower, замена множественных пробелов."""
        assert self.scenario._normalize("  JSON  ") == "json"
        assert self.scenario._normalize("Технология") == "технология"
        assert self.scenario._normalize("Test   String") == "test string"
        assert self.scenario._normalize("  C001  ") == "c001"

    def test_detect_query_type_topic_id(self):
        """Определение типа запроса: ID раздела (T01, L02 и т.д.)."""
        assert self.scenario._detect_query_type("T01") == "topic"
        assert self.scenario._detect_query_type("  l05  ") == "topic"
        assert self.scenario._detect_query_type("T99") == "topic"

    def test_detect_query_type_term(self):
        """Определение типа запроса: обычный термин или ID концепта."""
        assert self.scenario._detect_query_type("Онтология") == "term"
        assert self.scenario._detect_query_type("C001") == "term"
        assert self.scenario._detect_query_type("JSON формат") == "term"

    # ========================================================================
    # Поиск записей (_find_entry)
    # ========================================================================
    def test_find_entry_by_concept_id(self):
        """Поиск записи по ID концепта."""
        entry = self.scenario._find_entry("C001")
        assert entry is not None
        assert entry["concept_id"] == "C001"
        assert entry["term"] == "Технология"

    def test_find_entry_by_term(self):
        """Поиск записи по названию термина."""
        entry = self.scenario._find_entry("Онтология")
        assert entry is not None
        assert entry["concept_id"] == "C003"
        assert entry["definition"] == "Формальная спецификация."

    def test_find_entry_case_insensitive(self):
        """Поиск термина регистронезависим."""
        entry = self.scenario._find_entry("технология")
        assert entry is not None
        assert entry["concept_id"] == "C001"

    def test_find_entry_not_found(self):
        """Возврат None при отсутствии термина."""
        assert self.scenario._find_entry("НесуществующийТермин") is None

    def test_find_entry_with_suggestions(self):
        """При опечатке возвращает словарь с подсказками."""
        with patch('src.scenario_study.get_close_matches', return_value=["Технология"]):
            entry = self.scenario._find_entry("Технологи")
            assert entry is not None
            assert "_suggestions" in entry
            assert "Технология" in entry["_suggestions"]

    # ========================================================================
    # Основной обработчик (handle_query)
    # ========================================================================
    def test_handle_query_topic(self):
        """Обработка запроса ID раздела: возврат списка понятий."""
        result = self.scenario.handle_query("T01")
        assert "Раздел T01: Основы" in result
        assert "Всего понятий: 2" in result
        assert "Технология" in result
        assert "Информационная технология" in result

    def test_handle_query_topic_not_found(self):
        """Обработка несуществующего ID раздела."""
        result = self.scenario.handle_query("T99")
        assert "не найден" in result

    def test_handle_query_term_success(self):
        """Обработка запроса термина: возврат карточки с разрешёнными связями."""
        result = self.scenario.handle_query("Онтология")
        assert "Понятие: Онтология" in result
        assert "Определение: Формальная спецификация." in result
        assert "Используется в: C150" in result

    def test_handle_query_with_examples(self):
        """Карточка термина содержит примеры, если они есть."""
        result = self.scenario.handle_query("Информационная технология")
        assert "Примеры:" in result
        assert "IT" in result

    def test_handle_query_empty(self):
        """Обработка пустого ввода."""
        result = self.scenario.handle_query("")
        assert "Введите запрос." in result

    def test_handle_query_whitespace_only(self):
        """Обработка ввода только из пробелов."""
        result = self.scenario.handle_query("   ")
        assert "Введите запрос." in result

    def test_handle_query_not_found(self):
        """Сообщение об отсутствии термина в базе."""
        result = self.scenario.handle_query("НесуществующийТермин")
        assert "не найден в базе знаний" in result

    def test_handle_query_suggestions(self):
        """При опечатке предлагает похожие термины."""
        with patch('src.scenario_study.get_close_matches', return_value=["Технология"]):
            result = self.scenario.handle_query("Технологи")
            assert "Точного совпадения для 'Технологи' нет." in result
            assert "Возможно, вы имели в виду: Технология" in result

    def test_concept_id_vs_term_in_handle_query(self):
        """C001 определяется как term, но находится по ID благодаря _find_entry."""
        result = self.scenario.handle_query("C001")
        assert "Понятие: Технология" in result
        assert "ID: C001" in result

    # ========================================================================
    # Форматирование ответа (_build_response)
    # ========================================================================
    def test_build_response_hierarchy(self):
        """Формирование ответа включает иерархию (надкласс/подкласс)."""
        concept = self.MOCK_CONCEPTS["C002"]
        response = self.scenario._build_response(concept)
        assert "Иерархия:" in response
        assert "Надкласс: Технология" in response

    def test_build_response_other_relations(self):
        """Формирование ответа включает другие связи (разбиение, части)."""
        concept = self.MOCK_CONCEPTS["C001"]
        response = self.scenario._build_response(concept)
        assert "Связи:" in response
        assert "Разбиение: Информационная технология" in response