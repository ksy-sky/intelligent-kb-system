# tests/test_scenario_assistant.py
"""
Unit-тесты для модуля интеллектуального ассистента (Сценарий 3).
Тестирует поиск определений, связей, классификаций, примеров и т.д.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Тестовые данные — копия реальной структуры из glossary_labs.json
MOCK_KNOWLEDGE_BASE = [
    {
        "concept_id": "CL001",
        "term": "регулярные выражения",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1: Регулярные выражения",
        "source": "labs",
        "definition": "это специальный формальный язык для описания шаблонов поиска и обработки текста",
        "relations": {
            "пояснение": [
                "регулярные выражения — это специальные шаблоны, используемые для поиска, сопоставления и манипулирования строковыми данными.",
                "Регулярные выражения позволяют описать множество строк с помощью одного компактного выражения, используя специальные символы и конструкции."
            ],
            "составные части": ["CL002", "CL003"]
        },
        "examples": [
            "Если обычный поиск в текстовом редакторе ищет точное совпадение слова (например, кот), то регулярные выражения позволяют искать по образцу (например, любое слово, которое начинается с 'к' и заканчивается на 'т')."
        ]
    },
    {
        "concept_id": "CL002",
        "term": "литерал",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1: Регулярные выражения",
        "source": "labs",
        "definition": "это обычные символы в регулярных выражениях, которые интерпретируются буквально",
        "relations": {
            "пояснение": [
                "Самый простой тип регулярного выражения — это регулярные выражения, состоящие только из литералов."
            ]
        },
        "examples": [
            "выражение 123 найдёт точно последовательность 123 например в числе 123456."
        ]
    },
    {
        "concept_id": "CL003",
        "term": "метасимвол",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1: Регулярные выражения",
        "source": "labs",
        "definition": "специальные символы в регулярных выражениях, которые обозначают шаблоны, а не конкретные символы.",
        "relations": {
            "составные части": [
                ". (любой символ кроме новой строки)",
                "^ (начало строки)",
                "$ (конец строки)",
                "* (0 или более повторений)",
                "+ (1 или более повторений)",
                "? (0 или 1 повторение)",
                "{n} (ровно n повторений)",
                "{n,m} (от n до m повторений)",
                "[ ] (символьный класс)",
                "( ) (группа)",
                "| (логическое ИЛИ)",
                "\\ (экранирование)"
            ]
        },
        "examples": [
            "а.с найдёт abc, axc",
            "ab* найдёт a, ab, abb, abbb"
        ]
    },
    {
        "concept_id": "CL016",
        "term": "информация",
        "topic_id": "L02",
        "topic_title": "Лабораторная №2: Текстовые форматы данных",
        "source": "labs",
        "definition": "сведения об окружающем мире, которые осмыслены и могут быть восприняты человеком или системой.",
        "relations": {},
        "examples": []
    },
    {
        "concept_id": "CL017",
        "term": "данные",
        "topic_id": "L02",
        "topic_title": "Лабораторная №2: Текстовые форматы данных",
        "source": "labs",
        "definition": "представленные в определённой форме сведения о фактах, событиях, процессах, пригодные для хранения, обработки и передачи.",
        "relations": {
            "разбиение": ["CL018"]
        },
        "examples": []
    },
    {
        "concept_id": "CL007",
        "term": "квантификатор",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1: Регулярные выражения",
        "source": "labs",
        "definition": "специальные символы, которые указывают, сколько раз должен повторяться предыдущий символ или группа.",
        "relations": {
            "разбиение": ["CL008", "CL009"],
            "состав": [
                "* — 0 или более повторений",
                "+ — 1 или более повторений",
                "? — 0 или 1 повторение"
            ]
        },
        "examples": [
            "colou?r найдёт 'color' и 'colour'."
        ]
    },
    {
        "concept_id": "CL011",
        "term": "обратная ссылка",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1: Регулярные выражения",
        "source": "labs",
        "definition": "механизм повторного использования текста, захваченного группой, внутри того же регулярного выражения или при замене.",
        "relations": {
            "синтаксис": [
                "\\1, \\2, \\3 — ссылка по номеру группы",
                "\\k<name> — ссылка по имени именованной группы"
            ],
            "используется в": ["CL010"]
        },
        "examples": [
            "(\\w+)\\s+\\1 найдёт повторяющиеся слова ('the the', 'оно оно')."
        ]
    },
]


def create_assistant():
    """Создаёт экземпляр ассистента с мок-данными."""
    from src.scenario_assistant import IntelligentAssistant
    
    with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
         patch('src.scenario_assistant.load_knowledge_base', return_value=[c for c in MOCK_KNOWLEDGE_BASE if c['source'] == 'theory']), \
         patch('src.scenario_assistant.load_labs_base', return_value=[c for c in MOCK_KNOWLEDGE_BASE if c['source'] == 'labs']):
        assistant = IntelligentAssistant(use_llm=False)
        return assistant


class TestFindConcepts(unittest.TestCase):
    """Тесты поиска концептов."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_find_exact_term(self):
        """Точное совпадение термина."""
        concepts = self.assistant._find_concepts("регулярные выражения")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "регулярные выражения")
    
    def test_find_by_id(self):
        """Поиск по ID."""
        concepts = self.assistant._find_concepts("CL001")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "регулярные выражения")
    
    def test_find_case_insensitive(self):
        """Регистронезависимый поиск."""
        concepts = self.assistant._find_concepts("МЕТАСИМВОЛ")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "метасимвол")
    
    def test_find_nonexistent(self):
        """Несуществующий термин."""
        concepts = self.assistant._find_concepts("несуществующий_термин_xyz")
        self.assertEqual(len(concepts), 0)


class TestSearchRelevantInfo(unittest.TestCase):
    """Тесты поиска релевантной информации."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_search_single_word(self):
        """Поиск по одному слову."""
        concepts = self.assistant._search_relevant_info("метасимвол")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "метасимвол")
    
    def test_search_phrase(self):
        """Поиск по фразе."""
        concepts = self.assistant._search_relevant_info("регулярные выражения")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "регулярные выражения")
    
    def test_search_with_stop_words(self):
        """Поиск с стоп-словами."""
        concepts = self.assistant._search_relevant_info("что такое метасимвол")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "метасимвол")
    
    def test_search_nonexistent(self):
        """Поиск несуществующего."""
        concepts = self.assistant._search_relevant_info("абсолютно_неизвестный_термин_xyz")
        self.assertEqual(len(concepts), 0)


class TestProcessQuestion(unittest.TestCase):
    """Тесты обработки вопросов."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_empty_question(self):
        """Пустой вопрос."""
        response = self.assistant.process_question("")
        self.assertFalse(response["success"])
        self.assertIn("Пожалуйста", response["message"])
    
    def test_definition_what_is(self):
        """Вопрос 'что такое X'."""
        response = self.assistant.process_question("что такое метасимвол?")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
        self.assertIn("метасимвол", response["message"].lower())
        self.assertIn("специальные символы", response["message"].lower())
    
    def test_definition_single_word(self):
        """Просто одно слово — определение."""
        response = self.assistant.process_question("литерал")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
        self.assertIn("литерал", response["message"].lower())
        self.assertIn("обычные символы", response["message"].lower())
    
    def test_composition(self):
        """Вопрос про составные части."""
        response = self.assistant.process_question("составные части метасимвола")
        self.assertTrue(response["success"])
        self.assertIn("•", response["message"])  # Список элементов
        self.assertIn(". (любой символ", response["message"])
    
    def test_what_consists_of(self):
        """Вопрос 'из чего состоит'."""
        response = self.assistant.process_question("из чего состоит метасимвол")
        self.assertTrue(response["success"])
        self.assertIn("•", response["message"])
    
    def test_classification(self):
        """Вопрос про классификацию."""
        response = self.assistant.process_question("какие виды квантификаторов?")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "classification")
    
    def test_usage(self):
        """Вопрос 'где используется'."""
        response = self.assistant.process_question("где используется обратная ссылка?")
        self.assertTrue(response["success"])
        self.assertIn("используется", response["message"].lower())
    
    def test_examples(self):
        """Запрос примеров."""
        response = self.assistant.process_question("примеры регулярных выражений")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "examples")
        self.assertIn("обычный поиск", response["message"])
    
    def test_hierarchy(self):
        """Вопрос про надклассы (для терминов, где они есть)."""
        # В мок-данных нет надклассов, но тест проверяет что не падает
        response = self.assistant.process_question("надкласс информации")
        self.assertIsNotNone(response)
    
    def test_greeting(self):
        """Приветствие."""
        response = self.assistant.process_question("привет!")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "general")
        self.assertIn("ПиОИвИС", response["message"])
    
    def test_how_are_you(self):
        """Отвлечённый вопрос."""
        response = self.assistant.process_question("как дела?")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "general")
    
    def test_unknown_term(self):
        """Неизвестный термин."""
        response = self.assistant.process_question("что такое квантовая_запутанность_xyz?")
        # Может вернуть False (не найдено) или попытаться через LLM
        self.assertIn("success", response)
    
    def test_syntax_question(self):
        """Вопрос про синтаксис."""
        response = self.assistant.process_question("какой синтаксис обратная ссылка?")
        # Должен найти термин и либо показать определение, либо отправить в LLM
        self.assertIn("success", response)


class TestBuildContext(unittest.TestCase):
    """Тесты построения контекста для LLM."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_context_with_definition(self):
        """Контекст с определением."""
        concepts = [MOCK_KNOWLEDGE_BASE[0]]  # регулярные выражения
        context = self.assistant._build_context(concepts)
        self.assertIn("регулярные выражения", context)
        self.assertIn("Определение:", context)
    
    def test_context_with_relations(self):
        """Контекст со связями."""
        concepts = [MOCK_KNOWLEDGE_BASE[2]]  # метасимвол
        context = self.assistant._build_context(concepts)
        self.assertIn("составные части", context)
    
    def test_context_with_examples(self):
        """Контекст с примерами."""
        concepts = [MOCK_KNOWLEDGE_BASE[0]]  # регулярные выражения
        context = self.assistant._build_context(concepts)
        self.assertIn("Примеры:", context)
    
    def test_empty_context(self):
        """Пустой контекст."""
        context = self.assistant._build_context([])
        self.assertIn("не найдена", context.lower())


class TestFallbackSearch(unittest.TestCase):
    """Тесты запасного поиска без LLM."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_fallback_with_concepts(self):
        """Запасной поиск с найденными терминами."""
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        response = self.assistant._fallback_search("тест", concepts)
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
    
    def test_fallback_multiple_concepts(self):
        """Запасной поиск с несколькими терминами."""
        concepts = [MOCK_KNOWLEDGE_BASE[3], MOCK_KNOWLEDGE_BASE[4]]  # информация, данные
        response = self.assistant._fallback_search("сравнение данные и информация", concepts)
        self.assertTrue(response["success"])
        # Должен предложить уточнить или сравнить
        self.assertIn(response["type"], ["general", "comparison", "definition"])
    

class TestFormatResponse(unittest.TestCase):
    """Тесты форматирования ответов."""
    
    def test_format_success_definition(self):
        """Форматирование успешного определения."""
        from src.scenario_assistant import format_response
        response = {
            "success": True,
            "type": "definition",
            "message": "Тест — это проверка."
        }
        formatted = format_response(response)
        self.assertIn("Тест — это проверка", formatted)
    
    def test_format_success_relations(self):
        """Форматирование связей."""
        from src.scenario_assistant import format_response
        response = {
            "success": True,
            "type": "relations",
            "message": "Состав:\n• элемент1\n• элемент2"
        }
        formatted = format_response(response)
        self.assertIn("элемент1", formatted)
        self.assertIn("элемент2", formatted)
    
    def test_format_error(self):
        """Форматирование ошибки."""
        from src.scenario_assistant import format_response
        response = {
            "success": False,
            "type": "error",
            "message": "Не удалось найти."
        }
        formatted = format_response(response)
        self.assertIn("Не удалось найти", formatted)
    
    def test_format_greeting(self):
        """Форматирование приветствия."""
        from src.scenario_assistant import format_response
        response = {
            "success": True,
            "type": "general",
            "message": "Здравствуйте! Я ассистент."
        }
        formatted = format_response(response)
        self.assertIn("Здравствуйте", formatted)


class TestRelationMerging(unittest.TestCase):
    """Тесты объединения данных из нескольких источников."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_merge_definitions(self):
        """Определение берётся из первого источника."""
        # В мок-данных у метасимвола есть definition
        concepts = self.assistant._find_concepts("метасимвол")
        self.assertGreater(len(concepts), 0)
        self.assertTrue(any(c.get("definition") for c in concepts))
    
    def test_merge_relations(self):
        """Связи объединяются."""
        concepts = self.assistant._find_concepts("метасимвол")
        all_relations = {}
        for c in concepts:
            for k, v in c.get("relations", {}).items():
                if k not in all_relations:
                    all_relations[k] = []
                all_relations[k].extend(v)
        self.assertIn("составные части", all_relations)
    
    def test_merge_examples(self):
        """Примеры объединяются."""
        concepts = self.assistant._find_concepts("регулярные выражения")
        all_examples = []
        for c in concepts:
            all_examples.extend(c.get("examples", []))
        self.assertGreater(len(all_examples), 0)


if __name__ == '__main__':
    unittest.main()