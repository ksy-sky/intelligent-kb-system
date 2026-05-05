"""
Unit-тесты для модуля интеллектуального ассистента (Сценарий 3).
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
                "регулярные выражения — это специальные шаблоны.",
            ],
            "составные части": ["CL002", "CL003"],
            "используется в": ["текстовые редакторы", "языки программирования"]
        },
        "examples": [
            "Пример использования регулярных выражений."
        ]
    },
    {
        "concept_id": "CL002",
        "term": "литерал",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1",
        "source": "labs",
        "definition": "это обычные символы в регулярных выражениях",
        "relations": {
            "пояснение": ["Самый простой тип регулярного выражения."]
        },
        "examples": ["выражение 123 найдёт последовательность 123"]
    },
    {
        "concept_id": "CL003",
        "term": "метасимвол",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1",
        "source": "labs",
        "definition": "специальные символы в регулярных выражениях",
        "relations": {
            "составные части": [
                ". (любой символ кроме новой строки)",
                "^ (начало строки)",
                "$ (конец строки)",
                "* (0 или более повторений)",
            ],
            "надкласс": ["CL001"]
        },
        "examples": ["а.с найдёт abc, axc"]
    },
    {
        "concept_id": "CL016",
        "term": "информация",
        "topic_id": "L02",
        "topic_title": "Лабораторная №2",
        "source": "labs",
        "definition": "сведения об окружающем мире",
        "relations": {},
        "examples": []
    },
    {
        "concept_id": "CL017",
        "term": "данные",
        "topic_id": "L02",
        "topic_title": "Лабораторная №2",
        "source": "labs",
        "definition": "представленные в определённой форме сведения",
        "relations": {
            "разбиение": ["CL018"],
            "надкласс": ["CL016"]
        },
        "examples": []
    },
    {
        "concept_id": "CL007",
        "term": "квантификатор",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1",
        "source": "labs",
        "definition": "специальные символы, которые указывают, сколько раз должен повторяться предыдущий символ",
        "relations": {
            "разбиение": ["CL008", "CL009"],
            "состав": ["* — 0 или более", "+ — 1 или более"],
            "пояснение": ["По умолчанию квантификаторы жадные."]
        },
        "examples": ["colou?r найдёт 'color' и 'colour'."]
    },
    {
        "concept_id": "CL011",
        "term": "обратная ссылка",
        "topic_id": "L01",
        "topic_title": "Лабораторная №1",
        "source": "labs",
        "definition": "механизм повторного использования текста",
        "relations": {
            "синтаксис": [
                "\\1, \\2, \\3 — ссылка по номеру группы",
            ],
            "используется в": ["CL010"]
        },
        "examples": ["(\\w+)\\s+\\1 найдёт повторяющиеся слова"]
    },
    {
        "concept_id": "C080",
        "term": "регулярное выражение",
        "topic_id": "T04",
        "topic_title": "Текстовая информация и кодирование",
        "source": "theory",
        "definition": "regular expression",
        "relations": {
            "используется в": ["текстовый редактор", "язык программирования"],
            "составные части": ["PHP", "Perl"]
        },
        "examples": []
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
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_find_exact_term(self):
        concepts = self.assistant._find_concepts("регулярные выражения")
        self.assertGreater(len(concepts), 0)
        self.assertEqual(concepts[0]["term"], "регулярные выражения")
    
    def test_find_by_id(self):
        concepts = self.assistant._find_concepts("CL001")
        self.assertGreater(len(concepts), 0)
    
    def test_find_case_insensitive(self):
        concepts = self.assistant._find_concepts("МЕТАСИМВОЛ")
        self.assertGreater(len(concepts), 0)
    
    def test_find_nonexistent(self):
        concepts = self.assistant._find_concepts("несуществующий_термин_xyz")
        self.assertEqual(len(concepts), 0)
    
    def test_find_multiple_sources(self):
        """Термин есть и в теории, и в лабах."""
        concepts = self.assistant._find_concepts("регулярное выражение")
        self.assertGreater(len(concepts), 0)


class TestSearchRelevantInfo(unittest.TestCase):
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_search_single_word(self):
        concepts = self.assistant._search_relevant_info("метасимвол")
        self.assertGreater(len(concepts), 0)
    
    def test_search_phrase(self):
        concepts = self.assistant._search_relevant_info("регулярные выражения")
        self.assertGreater(len(concepts), 0)
    
    def test_search_with_stop_words(self):
        concepts = self.assistant._search_relevant_info("что такое метасимвол")
        self.assertGreater(len(concepts), 0)
    
    def test_search_nonexistent(self):
        concepts = self.assistant._search_relevant_info("абсолютно_неизвестный_термин_xyz")
        self.assertEqual(len(concepts), 0)
    


class TestProcessQuestion(unittest.TestCase):
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_empty_question(self):
        response = self.assistant.process_question("")
        self.assertFalse(response["success"])
    
    def test_definition_what_is(self):
        response = self.assistant.process_question("что такое метасимвол?")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
    
    def test_definition_single_word(self):
        response = self.assistant.process_question("литерал")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
    
    def test_composition(self):
        response = self.assistant.process_question("составные части метасимвола")
        self.assertTrue(response["success"])
        self.assertIn("•", response["message"])
    
    def test_what_consists_of(self):
        response = self.assistant.process_question("из чего состоит метасимвол")
        self.assertTrue(response["success"])
    
    def test_classification(self):
        response = self.assistant.process_question("какие виды квантификаторов?")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "classification")
    
    def test_usage(self):
        response = self.assistant.process_question("где используется обратная ссылка?")
        self.assertTrue(response["success"])
        self.assertIn("используется", response["message"].lower())
    
    def test_examples(self):
        response = self.assistant.process_question("примеры регулярных выражений")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "examples")
    
    def test_hierarchy(self):
        response = self.assistant.process_question("надкласс метасимвола")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "hierarchy")
    
    def test_greeting(self):
        response = self.assistant.process_question("привет!")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "general")
    
    def test_how_are_you(self):
        response = self.assistant.process_question("как дела?")
        self.assertTrue(response["success"])
    
    def test_unknown_term(self):
        response = self.assistant.process_question("что такое квантовая_запутанность_xyz?")
        self.assertIn("success", response)
    
    def test_syntax_question(self):
        response = self.assistant.process_question("какой синтаксис обратная ссылка?")
        self.assertIn("success", response)
    
    def test_relations_all(self):
        """Запрос всех связей."""
        response = self.assistant.process_question("связи метасимвола")
        self.assertTrue(response["success"])
    
    def test_comparison(self):
        """Запрос на сравнение."""
        response = self.assistant.process_question("в чем разница между данными и информацией?")
        self.assertIn("success", response)
    
    def test_whitespace_question(self):
        """Вопрос из пробелов."""
        response = self.assistant.process_question("   ")
        self.assertFalse(response["success"])


class TestBuildContext(unittest.TestCase):
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_context_with_definition(self):
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        context = self.assistant._build_context(concepts)
        self.assertIn("регулярные выражения", context)
        self.assertIn("Определение:", context)
    
    def test_context_with_relations(self):
        concepts = [MOCK_KNOWLEDGE_BASE[2]]
        context = self.assistant._build_context(concepts)
        self.assertIn("составные части", context)
    
    def test_context_with_examples(self):
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        context = self.assistant._build_context(concepts)
        self.assertIn("Примеры:", context)
    
    def test_empty_context(self):
        context = self.assistant._build_context([])
        self.assertIn("не найдена", context.lower())


class TestFallbackSearch(unittest.TestCase):
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_fallback_with_concepts(self):
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        response = self.assistant._fallback_search("тест", concepts)
        self.assertTrue(response["success"])
    
    def test_fallback_multiple_concepts(self):
        concepts = [MOCK_KNOWLEDGE_BASE[3], MOCK_KNOWLEDGE_BASE[4]]
        response = self.assistant._fallback_search("сравнение данные и информация", concepts)
        self.assertTrue(response["success"])
    
    def test_fallback_empty(self):
        response = self.assistant._fallback_search("неизвестное_xyz", [])
        self.assertFalse(response["success"])


class TestFormatResponse(unittest.TestCase):
    def test_format_success_definition(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "definition", "message": "Тест — это проверка."}
        formatted = format_response(response)
        self.assertIn("Тест — это проверка", formatted)
    
    def test_format_success_relations(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "relations", "message": "Состав:\n• элемент1\n• элемент2"}
        formatted = format_response(response)
        self.assertIn("элемент1", formatted)
    
    def test_format_error(self):
        from src.scenario_assistant import format_response
        response = {"success": False, "type": "error", "message": "Не удалось найти."}
        formatted = format_response(response)
        self.assertIn("Не удалось найти", formatted)
    
    def test_format_greeting(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "general", "message": "Здравствуйте!"}
        formatted = format_response(response)
        self.assertIn("Здравствуйте", formatted)
    
    def test_format_classification(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "classification", "message": "Виды: ..."}
        formatted = format_response(response)
        self.assertIn("Виды", formatted)
    
    def test_format_comparison(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "comparison", "message": "Сравнение: ..."}
        formatted = format_response(response)
        self.assertIn("Сравнение", formatted)
    
    def test_format_examples(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "examples", "message": "Примеры: ..."}
        formatted = format_response(response)
        self.assertIn("Примеры", formatted)
    
    def test_format_hierarchy(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "hierarchy", "message": "Надклассы: ..."}
        formatted = format_response(response)
        self.assertIn("Надклассы", formatted)
    
    def test_format_unknown_type(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "unknown_type", "message": "Что-то"}
        formatted = format_response(response)
        self.assertIsInstance(formatted, str)


class TestRelationMerging(unittest.TestCase):
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_merge_definitions(self):
        concepts = self.assistant._find_concepts("метасимвол")
        self.assertGreater(len(concepts), 0)
    
    def test_merge_relations(self):
        concepts = self.assistant._find_concepts("метасимвол")
        all_relations = {}
        for c in concepts:
            for k, v in c.get("relations", {}).items():
                if k not in all_relations:
                    all_relations[k] = []
                all_relations[k].extend(v)
        self.assertIn("составные части", all_relations)
    
    def test_merge_examples(self):
        concepts = self.assistant._find_concepts("регулярные выражения")
        all_examples = []
        for c in concepts:
            all_examples.extend(c.get("examples", []))
        self.assertGreater(len(all_examples), 0)


class TestLLMInteraction(unittest.TestCase):
    """Тесты взаимодействия с LLM (мокаем ollama)."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    @patch('src.scenario_assistant.ollama.generate')
    def test_ask_llm_definition(self, mock_generate):
        """Тест запроса определения через LLM."""
        mock_generate.return_value = {
            "response": '{"success": true, "type": "definition", "message": "Метасимвол — это специальный символ."}'
        }
        self.assistant.use_llm = True
        concepts = [MOCK_KNOWLEDGE_BASE[2]]  # метасимвол
        response = self.assistant._ask_llm("что такое метасимвол?", concepts)
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
    
    @patch('src.scenario_assistant.ollama.generate')
    def test_ask_llm_comparison(self, mock_generate):
        """Тест запроса сравнения через LLM."""
        mock_generate.return_value = {
            "response": '{"success": true, "type": "comparison", "message": "Данные — это..., а информация — это..."}'
        }
        self.assistant.use_llm = True
        concepts = [MOCK_KNOWLEDGE_BASE[3], MOCK_KNOWLEDGE_BASE[4]]
        response = self.assistant._ask_llm("в чем разница между данными и информацией?", concepts)
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "comparison")
    
    @patch('src.scenario_assistant.ollama.generate')
    def test_ask_llm_json_parse_error(self, mock_generate):
        """Тест обработки некорректного JSON от LLM."""
        mock_generate.return_value = {
            "response": 'не json ответ'
        }
        self.assistant.use_llm = True
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        response = self.assistant._ask_llm("вопрос", concepts)
        # Должен упасть в fallback
        self.assertIn("success", response)
    
    @patch('src.scenario_assistant.ollama.generate')
    def test_ask_llm_empty_response(self, mock_generate):
        """Тест пустого ответа от LLM."""
        mock_generate.return_value = {
            "response": '{"success": true, "type": "definition", "message": ""}'
        }
        self.assistant.use_llm = True
        concepts = [MOCK_KNOWLEDGE_BASE[0]]
        response = self.assistant._ask_llm("вопрос", concepts)
        self.assertIn("success", response)


class TestInitOllama(unittest.TestCase):
    """Тесты инициализации с Ollama."""
    
    @patch('src.scenario_assistant.subprocess.run')
    def test_init_ollama_available(self, mock_run):
        """Ollama доступен."""
        mock_run.return_value = MagicMock(stdout="llama3.2:latest", returncode=0)
        from src.scenario_assistant import IntelligentAssistant
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=[]):
            assistant = IntelligentAssistant(use_llm=True)
            self.assertTrue(assistant.use_llm)
    
    @patch('src.scenario_assistant.subprocess.run')
    def test_init_ollama_not_installed(self, mock_run):
        """Ollama не установлен."""
        mock_run.side_effect = FileNotFoundError()
        from src.scenario_assistant import IntelligentAssistant
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=[]):
            assistant = IntelligentAssistant(use_llm=True)
            self.assertFalse(assistant.use_llm)

class TestFindConceptsFuzzy(unittest.TestCase):
    """Тесты нечёткого поиска (покрытие 113-114)."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    
    def test_find_short_term_no_fuzzy(self):
        """Короткий термин не ищется нечётко."""
        concepts = self.assistant._find_concepts("абв")
        self.assertEqual(len(concepts), 0)


class TestProcessQuestionEdgeCases(unittest.TestCase):
    """Граничные случаи process_question (покрытие 367, 387, 397, 446, 465)."""
    
    def setUp(self):
        self.assistant = create_assistant()
    
    def test_need_definition_with_merged_definition(self):
        """Покрытие строки 367."""
        response = self.assistant.process_question("объясни метасимвол")
        self.assertTrue(response["success"])
        self.assertEqual(response["type"], "definition")
    
    
    def test_process_with_llm_enabled(self):
        """LLM включена (строка 240)."""
        self.assistant.use_llm = True
        with patch('src.scenario_assistant.ollama.generate') as mock_gen:
            mock_gen.return_value = {
                "response": '{"success": true, "type": "definition", "message": "Тест."}'
            }
            response = self.assistant.process_question("что такое метасимвол?")
            self.assertTrue(response["success"])
    
    def test_process_llm_fallback(self):
        """LLM включена, но термин не найден (строка 446)."""
        self.assistant.use_llm = True
        with patch('src.scenario_assistant.ollama.generate') as mock_gen:
            mock_gen.return_value = {
                "response": '{"success": false, "type": "error", "message": "Не знаю."}'
            }
            response = self.assistant.process_question("что такое неизвестное_xyz?")
            self.assertIn("success", response)
    
    def test_no_llm_no_definition(self):
        """LLM выключена, определение не найдено (строка 465)."""
        response = self.assistant.process_question("термин_без_определения_xyz")
        self.assertFalse(response["success"])


class TestFormatResponseAllTypes(unittest.TestCase):
    """Покрытие всех типов в format_response (строка 671)."""
    
    def test_format_unknown_type(self):
        from src.scenario_assistant import format_response
        response = {"success": True, "type": "unknown_xyz", "message": "test"}
        formatted = format_response(response)
        self.assertIn("test", formatted)


class TestRunScenarioAssistant(unittest.TestCase):
    """Тест функции запуска (покрытие 706-741)."""
    
    @patch('builtins.input', side_effect=['q'])
    @patch('builtins.print')
    def test_run_and_quit(self, mock_print, mock_input):
        """Запуск и немедленный выход."""
        from src.scenario_assistant import run_scenario3_assistant
        try:
            run_scenario3_assistant()
        except SystemExit:
            pass
        self.assertTrue(True)  # Не упало — уже хорошо
    
    @patch('builtins.input', side_effect=['что такое метасимвол?', 'q'])
    @patch('builtins.print')
    def test_run_with_question(self, mock_print, mock_input):
        """Запуск с одним вопросом."""
        from src.scenario_assistant import run_scenario3_assistant
        try:
            run_scenario3_assistant()
        except SystemExit:
            pass
        self.assertTrue(True)
    
    @patch('builtins.input', side_effect=['', 'q'])
    @patch('builtins.print')
    def test_run_empty_input(self, mock_print, mock_input):
        """Пустой ввод."""
        from src.scenario_assistant import run_scenario3_assistant
        try:
            run_scenario3_assistant()
        except SystemExit:
            pass
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()