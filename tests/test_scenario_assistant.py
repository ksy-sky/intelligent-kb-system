"""
Unit-тесты для модуля интеллектуального ассистента (Сценарий 3).
Целевое покрытие: 90%+.
"""

import unittest
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scenario_assistant import (
    resolve_id, format_response, IntelligentAssistant,
)

MOCK_KNOWLEDGE_BASE = [
    {
        "concept_id": "CL001", "term": "регулярные выражения",
        "topic_id": "L01", "topic_title": "Лаб. №1", "source": "labs",
        "definition": "формальный язык для шаблонов поиска",
        "relations": {"составные части": ["CL002", "CL003"], "пояснение": ["шаблоны для поиска"]},
        "examples": ["поиск по образцу", "./images/regex.png"]
    },
    {
        "concept_id": "CL002", "term": "литерал",
        "topic_id": "L01", "topic_title": "Лаб. №1", "source": "labs",
        "definition": "обычные символы в регулярных выражениях",
        "relations": {}, "examples": ["123 найдёт 123"]
    },
    {
        "concept_id": "CL003", "term": "метасимвол",
        "topic_id": "L01", "topic_title": "Лаб. №1", "source": "labs",
        "definition": "специальные символы, обозначающие шаблоны",
        "relations": {"составные части": [". (любой символ)", "^ (начало строки)", "$ (конец строки)"], "надкласс": ["CL007"]},
        "examples": ["а.с найдёт abc", "./images/meta.png"]
    },
    {
        "concept_id": "CL007", "term": "квантификатор",
        "topic_id": "L01", "topic_title": "Лаб. №1", "source": "labs",
        "definition": "символы, указывающие количество повторений",
        "relations": {"разбиение": ["CL008", "CL009"], "состав": ["* — 0+", "+ — 1+", "? — 0/1"]},
        "examples": []
    },
    {
        "concept_id": "CL011", "term": "обратная ссылка",
        "topic_id": "L01", "topic_title": "Лаб. №1", "source": "labs",
        "definition": "механизм повторного использования текста",
        "relations": {"используется в": ["CL010"], "синтаксис": ["\\1, \\2 — ссылка"]},
        "examples": ["(\\w+)\\s+\\1 найдёт повторы"]
    },
    {
        "concept_id": "CL016", "term": "информация",
        "topic_id": "L02", "topic_title": "Лаб. №2", "source": "labs",
        "definition": "сведения об окружающем мире",
        "relations": {"надкласс": ["CL017"]}, "examples": []
    },
    {
        "concept_id": "CL017", "term": "данные",
        "topic_id": "L02", "topic_title": "Лаб. №2", "source": "labs",
        "definition": "сведения о фактах, пригодные для обработки",
        "relations": {"разбиение": ["CL018"]}, "examples": []
    },
    {
        "concept_id": "CL050", "term": "линейные структуры данных",
        "topic_id": "T04", "topic_title": "Структуры данных", "source": "theory",
        "definition": "структуры с последовательным расположением",
        "relations": {"примеры": ["массив", "список", "стек", "очередь"]},
        "examples": ["массив", "связный список"]
    },
    {
        "concept_id": "CL051", "term": "нелинейные структуры данных",
        "topic_id": "T04", "topic_title": "Структуры данных", "source": "theory",
        "definition": "структуры с иерархическим расположением",
        "relations": {"примеры": ["дерево", "граф"]},
        "examples": ["деревья", "графы"]
    },
    {
        "concept_id": "CL100", "term": "метасимвол",
        "topic_id": "T04", "topic_title": "Теория №4", "source": "theory",
        "definition": "теоретическое определение метасимвола",
        "relations": {"составные части": ["| (логическое ИЛИ)", "\\ (экранирование)"]},
        "examples": ["пример из теории"]
    },
]


def create_assistant(use_llm=False):
    with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
         patch('src.scenario_assistant.load_knowledge_base', return_value=[c for c in MOCK_KNOWLEDGE_BASE if c['source'] == 'theory']), \
         patch('src.scenario_assistant.load_labs_base', return_value=[c for c in MOCK_KNOWLEDGE_BASE if c['source'] == 'labs']), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout="llama3.2:latest", returncode=0)
        return IntelligentAssistant(use_llm=use_llm)



class TestFindConcepts(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant()

    def test_exact(self):
        c = self.a._find_concepts("метасимвол")
        self.assertEqual(c[0]["term"], "метасимвол")

    def test_by_id(self):
        c = self.a._find_concepts("CL001")
        self.assertEqual(c[0]["term"], "регулярные выражения")

    def test_case_insensitive(self):
        c = self.a._find_concepts("МЕТАСИМВОЛ")
        self.assertEqual(c[0]["term"], "метасимвол")

    def test_nonexistent(self):
        self.assertEqual(len(self.a._find_concepts("несуществующий")), 0)

    def test_short_no_fuzzy(self):
        self.assertEqual(len(self.a._find_concepts("абв")), 0)

    def test_fuzzy(self):
        c = self.a._find_concepts("метосимвол")
        self.assertGreater(len(c), 0)


class TestSearchRelevantInfo(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant()

    def test_exact(self):
        c = self.a._search_relevant_info("метасимвол")
        self.assertEqual(c[0]["term"], "метасимвол")

    def test_with_stop_words(self):
        c = self.a._search_relevant_info("что такое метасимвол")
        self.assertEqual(c[0]["term"], "метасимвол")

    def test_only_stop_words(self):
        self.assertEqual(len(self.a._search_relevant_info("что такое и или")), 0)

    def test_nonexistent(self):
        self.assertEqual(len(self.a._search_relevant_info("неизвестный_термин")), 0)

    def test_fuzzy(self):
        c = self.a._search_relevant_info("метосимвол")
        self.assertGreater(len(c), 0)

    def test_phrase_linear(self):
        c = self.a._search_relevant_info("линейные структуры данных")
        self.assertEqual(c[0]["term"], "линейные структуры данных")

    def test_phrase_multiword(self):
        c = self.a._search_relevant_info("регулярные выражения")
        self.assertEqual(c[0]["term"], "регулярные выражения")

    def test_short_word_ignored(self):
        self.assertEqual(len(self.a._search_relevant_info("из")), 0)


class TestResolveId(unittest.TestCase):
    def setUp(self):
        import src.scenario_assistant as sa
        sa._loader = None
        create_assistant()

    def test_known(self):
        self.assertEqual(resolve_id("CL002"), "литерал")

    def test_unknown(self):
        self.assertEqual(resolve_id("CL999"), "CL999")

    def test_not_id(self):
        self.assertEqual(resolve_id("метасимвол"), "метасимвол")

    def test_whitespace(self):
        self.assertEqual(resolve_id("  CL001  "), "регулярные выражения")


class TestBuildContext(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant()

    def test_empty(self):
        ctx = self.a._build_context([])
        self.assertIn("не найдена", ctx.lower())

    def test_full(self):
        concepts = [c for c in MOCK_KNOWLEDGE_BASE if c["concept_id"] == "CL001"]
        ctx = self.a._build_context(concepts)
        self.assertIn("Термин:", ctx)
        self.assertIn("Определение:", ctx)
        self.assertIn("Связи:", ctx)
        self.assertIn("Примеры:", ctx)
        self.assertIn("Раздел:", ctx)

    def test_filters_file_paths_examples(self):
        ctx = self.a._build_context([MOCK_KNOWLEDGE_BASE[0]])
        self.assertNotIn("./images", ctx)
        self.assertIn("поиск по образцу", ctx)

    def test_filters_file_paths_relations(self):
        concept = {"concept_id": "CX", "term": "тест", "relations": {"связь": ["CL002", "./path"]}}
        ctx = self.a._build_context([concept])
        self.assertIn("литерал", ctx)
        self.assertNotIn("./path", ctx)

    def test_no_definition(self):
        concept = {"concept_id": "CX", "term": "без определения"}
        ctx = self.a._build_context([concept])
        self.assertIn("Термин:", ctx)
        self.assertNotIn("Определение:", ctx)


class TestFallbackSearch(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant()

    def test_empty_greeting(self):
        r = self.a._fallback_search("привет", [])
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "general")

    def test_empty_greeting_hello(self):
        r = self.a._fallback_search("здравствуй", [])
        self.assertTrue(r["success"])

    def test_empty_greeting_thanks(self):
        r = self.a._fallback_search("спасибо", [])
        self.assertTrue(r["success"])

    def test_empty_error(self):
        r = self.a._fallback_search("неизвестное", [])
        self.assertFalse(r["success"])
        self.assertEqual(r["type"], "error")

    def test_multiple_concepts(self):
        concepts = [c for c in MOCK_KNOWLEDGE_BASE if c["term"] in ["информация", "данные"]]
        r = self.a._fallback_search("сравнение", concepts)
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "general")
        self.assertIn("информация", r["message"])

    def test_single_concept(self):
        concepts = [c for c in MOCK_KNOWLEDGE_BASE if c["concept_id"] == "CL003"]
        r = self.a._fallback_search("тест", concepts)
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "definition")

    def test_no_definition(self):
        r = self.a._fallback_search("тест", [{"term": "без определения"}])
        self.assertIn("Определение отсутствует", r["message"])



class TestProcessQuestionLocal(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant(use_llm=False)

    def test_empty(self):
        self.assertFalse(self.a.process_question("")["success"])

    def test_whitespace(self):
        self.assertFalse(self.a.process_question("   ")["success"])

    def test_greeting_privet(self):
        r = self.a.process_question("привет!")
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "general")

    def test_greeting_kak_dela(self):
        r = self.a.process_question("как дела?")
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "general")

    def test_greeting_zdravstvuy(self):
        r = self.a.process_question("здравствуй")
        self.assertTrue(r["success"])

    def test_greeting_poka(self):
        r = self.a.process_question("пока")
        self.assertTrue(r["success"])

    def test_greeting_spasibo(self):
        r = self.a.process_question("спасибо")
        self.assertTrue(r["success"])

    def test_greeting_kto_ty(self):
        r = self.a.process_question("кто ты?")
        self.assertTrue(r["success"])


    def test_definition_explain(self):
        r = self.a.process_question("объясни метасимвол")
        self.assertTrue(r["success"])

    def test_definition_single_word(self):
        r = self.a.process_question("литерал")
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "definition")

    def test_composition_iz_chego(self):
        r = self.a.process_question("из чего состоит метасимвол")
        self.assertTrue(r["success"])
        self.assertIn(". (любой символ)", r["message"])

    def test_composition_sostavnye(self):
        r = self.a.process_question("составные части метасимвола")
        self.assertTrue(r["success"])

    def test_composition_chasti(self):
        r = self.a.process_question("части метасимвола")
        self.assertTrue(r["success"])

    def test_examples_linear(self):
        r = self.a.process_question("примеры линейные структуры данных")
        self.assertTrue(r["success"])
        msg = r["message"].lower()
        self.assertIn("массив", msg)
        self.assertNotIn("деревья", msg)
        self.assertNotIn("граф", msg)

    def test_examples_nonlinear(self):
        r = self.a.process_question("примеры нелинейные структуры данных")
        self.assertTrue(r["success"])
        msg = r["message"].lower()
        self.assertTrue("дерево" in msg or "деревья" in msg)

    def test_classification(self):
        r = self.a.process_question("какие виды квантификаторов?")
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "classification")

    def test_classification_perechisli(self):
        r = self.a.process_question("перечисли типы квантификаторов")
        self.assertTrue(r["success"])
        self.assertEqual(r["type"], "classification")

    def test_usage(self):
        r = self.a.process_question("где используется обратная ссылка?")
        self.assertTrue(r["success"])
        self.assertIn("используется", r["message"].lower())

    def test_usage_primenyetsa(self):
        r = self.a.process_question("где применяется обратная ссылка?")
        self.assertTrue(r["success"])

    def test_hierarchy(self):
        r = self.a.process_question("надкласс информации")
        self.assertTrue(r["success"])
        self.assertIn("данные", r["message"].lower())

    def test_hierarchy_roditel(self):
        r = self.a.process_question("родитель информации")
        self.assertTrue(r["success"])

    def test_syntax(self):
        self.assertIn("success", self.a.process_question("какой синтаксис обратная ссылка?"))

    def test_unknown_term(self):
        self.assertIn("success", self.a.process_question("что такое квантовая_запутанность?"))

    def test_no_detector_match(self):
        r = self.a.process_question("расскажи про литерал")
        self.assertTrue(r["success"])
        self.assertIn("литерал", r["message"].lower())

    def test_llm_disabled_fallback(self):
        r = self.a.process_question("опиши данные")
        self.assertTrue(r["success"])



class TestProcessQuestionOfftopic(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant(use_llm=False)

    def test_neuro(self):
        r = self.a.process_question("что такое нейросеть?")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])

    def test_blockchain(self):
        r = self.a.process_question("расскажи про блокчейн")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])

    def test_cooking(self):
        r = self.a.process_question("как приготовить борщ?")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])

    def test_animals(self):
        r = self.a.process_question("чем отличается лама от альпаки?")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])

    def test_bitcoin(self):
        r = self.a.process_question("как майнить биткоин?")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])

    def test_football(self):
        r = self.a.process_question("кто выиграл чемпионат мира?")
        self.assertIn(r.get("type", ""), ["off_topic", "error"])



class TestRelationMerging(unittest.TestCase):
    def setUp(self):
        self.a = create_assistant()

    def test_merge_relations(self):
        concepts = self.a._find_concepts("метасимвол")
        all_rel = {}
        for c in concepts:
            for k, v in c.get("relations", {}).items():
                if k not in all_rel:
                    all_rel[k] = []
                all_rel[k].extend(v)
        self.assertIn("составные части", all_rel)
        self.assertGreater(len(all_rel["составные части"]), 3)

    def test_merge_examples(self):
        concepts = self.a._find_concepts("регулярные выражения")
        all_ex = []
        for c in concepts:
            all_ex.extend(c.get("examples", []))
        self.assertGreater(len(all_ex), 0)

    def test_merge_definitions(self):
        concepts = self.a._find_concepts("метасимвол")
        self.assertGreater(len(concepts), 1)
        self.assertTrue(any(c.get("definition") for c in concepts))


class TestFormatResponse(unittest.TestCase):
    def test_success_definition(self):
        f = format_response({"success": True, "type": "def", "message": "Тест — это проверка."})
        self.assertIn("Тест — это проверка", f)

    def test_success_relations(self):
        f = format_response({"success": True, "type": "relations", "message": "Состав:\n• элемент1"})
        self.assertIn("элемент1", f)

    def test_error(self):
        f = format_response({"success": False, "type": "error", "message": "Ошибка"})
        self.assertIn("Ошибка", f)

    def test_greeting(self):
        f = format_response({"success": True, "type": "general", "message": "Здравствуйте!"})
        self.assertIn("Здравствуйте", f)


class TestOllamaInit(unittest.TestCase):
    @patch('subprocess.run')
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(stdout="llama3.2:latest", returncode=0)
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=MOCK_KNOWLEDGE_BASE):
            a = IntelligentAssistant(use_llm=True)
            self.assertTrue(a.use_llm)

    @patch('subprocess.run')
    def test_not_installed(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=MOCK_KNOWLEDGE_BASE):
            a = IntelligentAssistant(use_llm=True)
            self.assertFalse(a.use_llm)

    @patch('subprocess.run')
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ollama", timeout=5)
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=MOCK_KNOWLEDGE_BASE):
            a = IntelligentAssistant(use_llm=True)
            self.assertFalse(a.use_llm)

    @patch('subprocess.run')
    def test_model_not_found(self, mock_run):
        mock_run.return_value = MagicMock(stdout="mistral:latest", returncode=0)
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=MOCK_KNOWLEDGE_BASE):
            a = IntelligentAssistant(use_llm=True)
            self.assertFalse(a.use_llm)

    @patch('subprocess.run')
    def test_skipped_when_false(self, mock_run):
        with patch('src.scenario_assistant.load_all', return_value=MOCK_KNOWLEDGE_BASE), \
             patch('src.scenario_assistant.load_knowledge_base', return_value=[]), \
             patch('src.scenario_assistant.load_labs_base', return_value=MOCK_KNOWLEDGE_BASE):
            a = IntelligentAssistant(use_llm=False)
            self.assertFalse(a.use_llm)
            mock_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()