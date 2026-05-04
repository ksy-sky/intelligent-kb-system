import pytest
import os
import sys
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario, normalize_text

@pytest.fixture(scope="module")
def loader():
    """Создает и загружает KnowledgeBaseLoader один раз для всех тестов."""
    kb_files = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "glossary.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "glossary_labs.json")
    ]
    _loader = KnowledgeBaseLoader(kb_files)
    _loader.load()
    return _loader

@pytest.fixture
def scenario(loader):
    """Создает экземпляр сценария глоссария."""
    return GlossaryScenario(loader)

class TestGlossaryScenario:
    """Набор из 15 тестов для проверки Сценария 2 (Глоссарий)."""

    # 1. Утилиты
    def test_normalize_text_basic(self, scenario):
        """Проверка нормализации: нижний регистр и удаление пробелов."""
        assert normalize_text("  JSON  ") == "json"
        assert normalize_text("Test   String") == "test string"

    # 2-4. Точный поиск (find_entry_by_label / search_term)
    def test_search_term_exact_match_theory(self, scenario):
        """Успешный поиск термина в теоретической части."""
        result = scenario.search_term("онтология", source="theory")
        assert result["found"] is True
        assert result["concept_id"] == "C158"
        assert "definition" in result

    def test_search_term_exact_match_labs(self, scenario):
        """Успешный поиск термина в лабораторной части."""
        result = scenario.search_term("регулярные выражения", source="labs")
        assert result["found"] is True
        assert result["concept_id"] == "CL001"

    def test_search_term_by_id(self, scenario):
        """Поиск концепта по его уникальному ID."""
        result = scenario.search_term("C158", source="all")
        assert result["found"] is True
        assert result["term"].lower() == "онтология"

    # 5. Регистронезависимость
    def test_search_case_insensitive(self, scenario):
        """Поиск должен работать независимо от регистра ввода."""
        res1 = scenario.search_term("ОНТОЛОГИЯ", source="theory")
        res2 = scenario.search_term("онтология", source="theory")
        assert res1["found"] is res2["found"] is True
        assert res1["concept_id"] == res2["concept_id"]

    # 6. Обработка пустого ввода
    def test_search_empty_input(self, scenario):
        """Обработка пустой строки или пробелов."""
        result = scenario.search_term("")
        assert result["found"] is False
        assert "пустой" in result["message"].lower()

    # 7-8. Нечёткий поиск (get_similar_terms)
    def test_fuzzy_search_found(self, scenario):
        """Нечёткий поиск предлагает похожие термины при опечатке."""
        result = scenario.search_term("онтологи", source="theory")
        assert result["found"] is False
        assert len(result["similar_terms"]) > 0
        assert any("онтология" in t.lower() for t in result["similar_terms"])

    def test_fuzzy_search_no_match(self, scenario):
        """Нечёткий поиск возвращает пустой список для бессмысленного набора символов."""
        result = scenario.search_term("xyz123abc", source="theory")
        assert result["found"] is False
        assert result["similar_terms"] == []

    # 9. Разрешение связей (resolve_id внутри search_term)
    def test_resolved_relations(self, scenario):
        """Проверка, что ID в связях заменены на термины."""
        result = scenario.search_term("онтология", source="theory")
        assert result["found"] is True
        if "разбиение" in result["relations"]:
            for item in result["relations"]["разбиение"]:
                assert isinstance(item, str)
                # ID формата C001/CL001 не должны оставаться в связях
                assert not re.match(r"^C(?:L)?\d{2,4}$", item.strip()), \
                    f"ID не был разрешён в термин: {item}"



    # 10. Фильтрация по источнику
    def test_source_filtering(self, scenario):
        """Поиск в theory не должен находить термины из labs."""
        result = scenario.search_term("регулярные выражения", source="theory")
        assert result["found"] is False

    # 11-12. Вспомогательные методы (get_all_terms, get_stats)
    def test_get_all_terms_sorted(self, scenario):
        """Список всех терминов должен быть отсортирован."""
        terms = scenario.get_all_terms(source="all")
        assert isinstance(terms, list)
        assert len(terms) > 0
        assert terms == sorted(terms, key=lambda x: x.lower())

    def test_get_stats_structure(self, scenario):
        """Статистика должна содержать ключевые метрики."""
        stats = scenario.get_stats()
        assert "total" in stats
        assert "theory_concepts" in stats
        assert "labs_concepts" in stats
        assert stats["total"] == stats["theory_concepts"] + stats["labs_concepts"]

    # 13. Поиск по теме (get_terms_by_topic)
    def test_get_terms_by_topic(self, scenario):
        """Фильтрация концептов по ID темы."""
        terms = scenario.get_terms_by_topic("T07") # Тема про ИИ
        assert isinstance(terms, list)
        if terms:
            assert all(t["topic_id"] == "T07" for t in terms)

    # 14. Отсутствие термина
    def test_term_not_found_message(self, scenario):
        """Корректное сообщение при отсутствии термина."""
        result = scenario.search_term("несуществующий_термин_курсовой", source="all")
        assert result["found"] is False
        assert "не найден" in result["message"].lower()

    # 15. Интеграционный тест структуры ответа
    def test_response_structure_completeness(self, scenario):
        """Проверка наличия всех обязательных полей в успешном ответе."""
        result = scenario.search_term("технология", source="theory")
        assert result["found"] is True
        required_keys = ["term", "concept_id", "topic_id", "topic_title", "source", "definition", "relations", "examples"]
        for key in required_keys:
            assert key in result, f"Отсутствует ключ: {key}"