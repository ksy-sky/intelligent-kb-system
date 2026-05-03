import pytest
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scenario_glossary import (
    normalize_text,
    load_knowledge_base,
    load_labs_base,
    load_all,
    find_entry_by_label,
    resolve_id,
    get_similar_terms,
    search_term,
    get_all_terms,
    get_terms_by_topic,
    get_stats
)

class TestGlossaryModule:
    """Полный набор Unit-тестов для модуля глоссария (Сценарий 2)."""

    # Моковые данные, имитирующие структуру JSON-файлов
    MOCK_THEORY = [
        {"concept_id": "C001", "term": "Технология", "topic_id": "T01", "topic_title": "Основы", "source": "theory", "definition": "Совокупность методов.", "relations": {"разбиение": ["C002"]}, "examples": []},
        {"concept_id": "C002", "term": "Информационная технология", "topic_id": "T01", "topic_title": "Основы", "source": "theory", "definition": "Обработка данных.", "relations": {"надкласс": ["C001"]}, "examples": ["IT"]},
        {"concept_id": "C003", "term": "Онтология", "topic_id": "T02", "topic_title": "Semantic Web", "source": "theory", "definition": "Формальная спецификация.", "relations": {"используется в": ["C150"]}, "examples": []}
    ]
    MOCK_LABS = [
        {"concept_id": "CL001", "term": "Регулярные выражения", "topic_id": "L01", "topic_title": "Регулярки", "source": "labs", "definition": "Шаблоны поиска.", "relations": {"составные части": ["CL002"]}, "examples": []},
        {"concept_id": "CL002", "term": "Метасимвол", "topic_id": "L01", "topic_title": "Регулярки", "source": "labs", "definition": "Спецсимвол.", "relations": {"надкласс": ["CL001"]}, "examples": []}
    ]

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Автоматически мок загрузку и сброс кэша перед каждым тестом."""
        with patch('src.scenario_glossary.load_knowledge_base', return_value=self.MOCK_THEORY), \
             patch('src.scenario_glossary.load_labs_base', return_value=self.MOCK_LABS):
            
            import src.scenario_glossary as sg
            sg._knowledge_base = None
            sg._labs_base = None
            yield

    def test_normalize_text(self):
        """Нормализация: trim, lower, замена множественных пробелов."""
        assert normalize_text("  JSON  ") == "json"
        assert normalize_text("Технология") == "технология"
        assert normalize_text("Test   String") == "test string"
        assert normalize_text("  C001  ") == "c001"

    def test_find_entry_exact_match(self):
        """Поиск по точному названию."""
        entry = find_entry_by_label("Технология", source="theory")
        assert entry is not None
        assert entry["concept_id"] == "C001"
        assert entry["definition"] == "Совокупность методов."

    def test_find_entry_case_insensitive(self):
        """Поиск регистронезависимый."""
        entry = find_entry_by_label("технология", source="theory")
        assert entry is not None
        assert entry["concept_id"] == "C001"

    def test_find_entry_by_id(self):
        """Поиск по concept_id."""
        entry = find_entry_by_label("C002", source="theory")
        assert entry is not None
        assert entry["term"] == "Информационная технология"

    def test_find_entry_in_labs(self):
        """Поиск в лабораторных работах."""
        entry = find_entry_by_label("Метасимвол", source="labs")
        assert entry is not None
        assert entry["concept_id"] == "CL002"

    def test_find_entry_not_found(self):
        """Возврат None при отсутствии термина."""
        assert find_entry_by_label("НесуществующийТермин", source="all") is None

    def test_resolve_id_valid(self):
        """Преобразование ID в термин."""
        assert resolve_id("C001") == "Технология"
        assert resolve_id("CL002") == "Метасимвол"

    def test_resolve_id_invalid(self):
        """Несуществующий ID возвращается как есть."""
        assert resolve_id("C999") == "C999"
        assert resolve_id("ПростоТекст") == "ПростоТекст"

    def test_get_similar_terms(self):
        """Нечеткий поиск находит похожие термины."""
        similar = get_similar_terms("Технологи", n=2, source="theory")
        
        assert len(similar) > 0
        assert "Технология" in similar

    def test_get_similar_terms_empty(self):
        """Нечеткий поиск не находит ничего при сильном различии."""
        similar = get_similar_terms("XYZ123", n=3, source="theory")
        assert similar == []

    def test_search_term_success(self):
        """Успешный поиск: полная карточка с resolved relations."""
        result = search_term("Онтология", source="theory")
        assert result["found"] is True
        assert result["term"] == "Онтология"
        assert result["definition"] == "Формальная спецификация."
        assert "используется в" in result["relations"]
        assert result["relations"]["используется в"] == ["C150"] 
        assert result["examples"] == []

    def test_search_term_with_examples(self):
        """Проверка возврата примеров."""
        result = search_term("Информационная технология", source="theory")
        assert result["found"] is True
        assert result["examples"] == ["IT"]

    def test_search_term_empty_input(self):
        """Обработка пустого ввода."""
        result = search_term("")
        assert result["found"] is False
        assert "пустой" in result["message"].lower()
        assert result["similar_terms"] == []

    def test_search_term_whitespace_only(self):
        """Обработка ввода только из пробелов."""
        result = search_term("   ")
        assert result["found"] is False
        assert "пустой" in result["message"].lower()

    def test_search_term_not_found_with_suggestions(self):
        """При отсутствии термина предлагается список похожих."""
        result = search_term("Техналогия", source="theory")
        assert result["found"] is False
        assert len(result["similar_terms"]) > 0
        assert "Технология" in result["similar_terms"]

    def test_search_term_across_sources(self):
        """Поиск по всем источникам (source='all')."""
        res_theory = search_term("Технология", source="all")
        res_labs = search_term("Регулярные выражения", source="all")
        assert res_theory["found"] is True
        assert res_labs["found"] is True

    def test_get_all_terms(self):
        """Получение отсортированного списка всех терминов."""
        terms = get_all_terms(source="all")
        assert isinstance(terms, list)
        assert "Технология" in terms
        assert "Регулярные выражения" in terms
        assert "Метасимвол" in terms
        assert terms == sorted(terms, key=lambda x: x.lower())

    def test_get_terms_by_topic(self):
        """Фильтрация терминов по topic_id."""
        terms_l01 = get_terms_by_topic("L01")
        assert len(terms_l01) == 2
        assert all(t["term"] in ["Регулярные выражения", "Метасимвол"] for t in terms_l01)
        
        terms_t02 = get_terms_by_topic("T02")
        assert len(terms_t02) == 1
        assert terms_t02[0]["term"] == "Онтология"

    def test_get_stats(self):
        """Проверка статистики базы знаний."""
        stats = get_stats()
        assert stats["theory_concepts"] == 3
        assert stats["labs_concepts"] == 2
        assert stats["total"] == 5
        assert stats["theory_topics"] == 2  
        assert stats["labs_topics"] == 1    

    def test_load_knowledge_base_caching(self):
        """Повторный вызов возвращает те же данные (кэш работает)."""
        result1 = load_knowledge_base()
        result2 = load_knowledge_base()
        assert result1 is result2  
    
    def test_load_labs_base_caching(self):
        """Повторный вызов возвращает те же данные (кэш работает)."""
        result1 = load_labs_base()
        result2 = load_labs_base()
        assert result1 is result2

    def test_load_all_combines_sources(self):
        """load_all объединяет теорию и лабы."""
        all_data = load_all()
        assert len(all_data) == 5
        ids = [c["concept_id"] for c in all_data]
        assert "C001" in ids
        assert "CL001" in ids