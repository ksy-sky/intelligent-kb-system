import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scenario_glossary import GlossaryScenario, normalize_text
from src.kb_loader import KnowledgeBaseLoader

MOCK_THEORY = [
    {"concept_id": "C001", "term": "Технология", "topic_id": "T01", "source": "theory",
     "definition": "Совокупность методов.", "relations": {"разбиение": ["C002"]}, "examples": []},
    {"concept_id": "C002", "term": "Информационная технология", "topic_id": "T01", "source": "theory",
     "definition": "Обработка данных.", "relations": {"надкласс": ["C001"]}, "examples": ["IT"]},
    {"concept_id": "C003", "term": "Онтология", "topic_id": "T02", "source": "theory",
     "definition": "Формальная спецификация.", "relations": {"используется в": ["C150"]}, "examples": []}
]
MOCK_LABS = [
    {"concept_id": "CL001", "term": "Регулярные выражения", "topic_id": "L01", "source": "labs",
     "definition": "Шаблоны поиска.", "relations": {"составные части": ["CL002"]}, "examples": []},
    {"concept_id": "CL002", "term": "Метасимвол", "topic_id": "L01", "source": "labs",
     "definition": "Спецсимвол.", "relations": {"надкласс": ["CL001"]}, "examples": []}
]

class TestGlossaryUnit(unittest.TestCase):
    """Unit-тесты модуля глоссария с использованием unittest и моков."""

    def setUp(self):
        """Настройка перед каждым тестом: создание мока лоадера и сценария."""
        self.mock_loader = MagicMock(spec=KnowledgeBaseLoader)
        all_concepts = MOCK_THEORY + MOCK_LABS
        
        def get_concept_side_effect(cid):
            return next((c for c in all_concepts if c["concept_id"] == cid), None)

        def search_by_term_side_effect(term):
            return [c for c in all_concepts if c["term"].lower() == term.lower()]

        def get_topics_index_side_effect():
            return {
                "T01": {"title": "Основы", "concept_ids": ["C001", "C002"]},
                "T02": {"title": "Semantic Web", "concept_ids": ["C003"]},
                "L01": {"title": "Регулярки", "concept_ids": ["CL001", "CL002"]}
            }

        self.mock_loader.get_concept.side_effect = get_concept_side_effect
        self.mock_loader.search_by_term.side_effect = search_by_term_side_effect
        self.mock_loader.get_topics_index.side_effect = get_topics_index_side_effect
        
        # Заполняем индексы для внутренних проверок (если класс к ним обращается напрямую)
        self.mock_loader.concepts_by_id = {c["concept_id"]: c for c in all_concepts}
        self.mock_loader.concepts_by_term = {}
        for c in all_concepts:
            self.mock_loader.concepts_by_term.setdefault(c["term"].lower(), []).append(c)

        self.scenario = GlossaryScenario(self.mock_loader)

    # 1. Утилиты
    def test_normalize_text_basic(self):
        """Проверка нормализации: нижний регистр и удаление пробелов."""
        self.assertEqual(normalize_text("  JSON  "), "json")
        self.assertEqual(normalize_text("Test   String"), "test string")

    # 2-4. Точный поиск (search_term)
    def test_search_term_exact_match_theory(self):
        """Успешный поиск термина в теоретической части."""
        result = self.scenario.search_term("Технология", source="theory")
        self.assertTrue(result["found"])
        self.assertEqual(result["concept_id"], "C001")
        self.assertIn("definition", result)

    def test_search_term_exact_match_labs(self):
        """Успешный поиск термина в лабораторной части."""
        result = self.scenario.search_term("Метасимвол", source="labs")
        self.assertTrue(result["found"])
        self.assertEqual(result["concept_id"], "CL002")

    def test_search_term_by_id(self):
        """Поиск концепта по его уникальному ID."""
        result = self.scenario.search_term("C003", source="all")
        self.assertTrue(result["found"])
        self.assertEqual(result["term"], "Онтология")

    # 5. Регистронезависимость
    def test_search_case_insensitive(self):
        """Поиск должен работать независимо от регистра ввода."""
        res1 = self.scenario.search_term("ТЕХНОЛОГИЯ", source="theory")
        res2 = self.scenario.search_term("технология", source="theory")
        self.assertTrue(res1["found"])
        self.assertTrue(res2["found"])
        self.assertEqual(res1["concept_id"], res2["concept_id"])

    # 6. Обработка пустого ввода
    def test_search_empty_input(self):
        """Обработка пустой строки или пробелов."""
        result = self.scenario.search_term("   ")
        self.assertFalse(result["found"])
        self.assertIn("пустой", result["message"].lower())

    # 7-8. Нечёткий поиск (get_similar_terms)
    def test_fuzzy_search_found(self):
        """Нечёткий поиск предлагает похожие термины при опечатке."""
        result = self.scenario.search_term("Технологи", source="theory")
        self.assertFalse(result["found"])
        self.assertGreater(len(result["similar_terms"]), 0)
        self.assertTrue(any("технология" in t.lower() for t in result["similar_terms"]))

    def test_fuzzy_search_no_match(self):
        """Нечёткий поиск возвращает пустой список для бессмысленного набора символов."""
        result = self.scenario.search_term("xyz123abc", source="theory")
        self.assertFalse(result["found"])
        self.assertEqual(result["similar_terms"], [])

    # 9. Разрешение связей (resolve_id внутри search_term)
    def test_resolved_relations(self):
        """Проверка, что ID в связях заменены на термины."""
        result = self.scenario.search_term("Технология", source="theory")
        self.assertTrue(result["found"])
        if "разбиение" in result["relations"]:
            for item in result["relations"]["разбиение"]:
                # В моках C002 -> "Информационная технология"
                self.assertIsInstance(item, str)
                self.assertFalse(item.startswith("C"), f"ID не был разрешён в термин: {item}")

    # 10. Фильтрация по источнику
    def test_source_filtering(self):
        """Поиск в theory не должен находить термины из labs."""
        result = self.scenario.search_term("Метасимвол", source="theory")
        self.assertFalse(result["found"])

    # 11-12. Вспомогательные методы (get_all_terms, get_stats)
    def test_get_all_terms_sorted(self):
        """Список всех терминов должен быть отсортирован."""
        terms = self.scenario.get_all_terms(source="all")
        self.assertIsInstance(terms, list)
        self.assertGreater(len(terms), 0)
        self.assertEqual(terms, sorted(terms, key=lambda x: x.lower()))

    def test_get_stats_structure(self):
        """Статистика должна содержать ключевые метрики."""
        stats = self.scenario.get_stats()
        self.assertIn("total", stats)
        self.assertEqual(stats["total"], 5) 
        self.assertEqual(stats["theory_concepts"], 3)
        self.assertEqual(stats["labs_concepts"], 2)

    # 13. Поиск по теме (get_terms_by_topic)
    def test_get_terms_by_topic(self):
        """Фильтрация концептов по ID темы."""
        terms = self.scenario.get_terms_by_topic("L01")
        self.assertEqual(len(terms), 2)
        for t in terms:
            self.assertEqual(t["topic_id"], "L01")

    # 14. Отсутствие термина
    def test_term_not_found_message(self):
        """Корректное сообщение при отсутствии термина."""
        result = self.scenario.search_term("несуществующий_термин", source="all")
        self.assertFalse(result["found"])
        self.assertIn("не найден", result["message"].lower())

    # 15. Интеграционный тест структуры ответа
    def test_response_structure_completeness(self):
        """Проверка наличия всех обязательных полей в успешном ответе."""
        result = self.scenario.search_term("Онтология", source="theory")
        self.assertTrue(result["found"])
        required_keys = ["term", "concept_id", "topic_id", "topic_title", "source", "definition", "relations", "examples"]
        for key in required_keys:
            self.assertIn(key, result, f"Отсутствует ключ: {key}")

if __name__ == '__main__':
    unittest.main()
