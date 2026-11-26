# tests/test_kb_loader.py (переписан для unittest)
import os
import unittest
import json
import tempfile
from pathlib import Path
from src.kb_loader import KnowledgeBaseLoader
from src.kb_validator import KBValidationError
from src.solver_admin import AdminSolver
from src.solver_router import SolverRouter


class TestKnowledgeBaseLoaderInitialization(unittest.TestCase):
    """Тесты инициализации загрузчика"""
    
    def test_initialization(self):
        """Создание экземпляра загрузчика"""
        loader = KnowledgeBaseLoader(["file1.json", "file2.json"])
        self.assertEqual(loader.file_paths, ["file1.json", "file2.json"])
        self.assertEqual(loader.concepts_by_id, {})
        self.assertEqual(loader.concepts_by_term, {})
        self.assertEqual(loader.topics_index, {})
        self.assertEqual(loader.metadata, {})
        self.assertFalse(loader._is_loaded)
    
    def test_empty_file_list(self):
        """Пустой список файлов"""
        loader = KnowledgeBaseLoader([])
        self.assertEqual(loader.file_paths, [])


class TestMergeJSONFiles(unittest.TestCase):
    """Тесты слияния JSON файлов"""
    
    def setUp(self):
        """Создаёт временные файлы для тестов"""
        self.temp_paths = []
    
    def tearDown(self):
        """Удаляет временные файлы"""
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_temp_json(self, data):
        """Создаёт временный JSON файл и возвращает его путь"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def test_merge_multiple_files(self):
        """Слияние нескольких файлов"""
        data1 = {
            "metadata": {"version": "1.0"},
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тема 1",
                    "concepts": [
                        {"concept_id": "C001", "term": "Термин 1", "topic_id": "T001"}
                    ]
                }
            ]
        }
        
        data2 = {
            "topics": [
                {
                    "topic_id": "T002",
                    "title": "Тема 2",
                    "concepts": [
                        {"concept_id": "C002", "term": "Термин 2", "topic_id": "T002"}
                    ]
                }
            ]
        }
        
        path1 = self._create_temp_json(data1)
        path2 = self._create_temp_json(data2)
        
        loader = KnowledgeBaseLoader([path1, path2])
        merged = loader._merge_json_files()
        
        self.assertIn("metadata", merged)
        self.assertEqual(merged["metadata"], {"version": "1.0"})
        self.assertEqual(len(merged["topics"]), 2)
        self.assertEqual(merged["topics"][0]["topic_id"], "T001")
        self.assertEqual(merged["topics"][1]["topic_id"], "T002")
    
    def test_file_not_found(self):
        """Файл не найден"""
        loader = KnowledgeBaseLoader(["nonexistent.json"])
        with self.assertRaises(FileNotFoundError):
            loader._merge_json_files()
    
    def test_empty_topics_in_file(self):
        """Файл без тем"""
        data = {"topics": []}
        path = self._create_temp_json(data)
        
        loader = KnowledgeBaseLoader([path])
        merged = loader._merge_json_files()
        self.assertEqual(len(merged["topics"]), 0)


class TestLoadAndValidate(unittest.TestCase):
    """Тесты полной загрузки и валидации"""
    
    def setUp(self):
        """Создаёт временные файлы для тестов"""
        self.temp_paths = []
    
    def tearDown(self):
        """Удаляет временные файлы"""
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_temp_json(self, data):
        """Создаёт временный JSON файл и возвращает его путь"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def _create_valid_kb_file(self):
        """Создаёт временный файл с корректной БЗ"""
        data = {
            "metadata": {"version": "1.0", "author": "Test"},
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Математика",
                    "concepts": [
                        {
                            "concept_id": "C001",
                            "term": "Число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C002"]}
                        },
                        {
                            "concept_id": "C002",
                            "term": "Натуральное число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C003"]}
                        },
                        {
                            "concept_id": "C003",
                            "term": "Целое число",
                            "topic_id": "T001",
                            "relations": {}
                        }
                    ]
                },
                {
                    "topic_id": "T002",
                    "title": "Физика",
                    "concepts": [
                        {
                            "concept_id": "CL001",
                            "term": "Масса",
                            "topic_id": "T002",
                            "relations": {"ассоциация": ["энергия"]}
                        }
                    ]
                }
            ]
        }
        return self._create_temp_json(data)
    
    def test_successful_load(self):
        """Успешная загрузка корректной БЗ"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        summary = loader.load()
        
        self.assertTrue(loader._is_loaded)
        self.assertEqual(summary["concepts_count"], 4)
        self.assertEqual(summary["topics_count"], 2)
        self.assertEqual(summary["metadata"], {"version": "1.0", "author": "Test"})
    
    def test_load_invalid_kb(self):
        """Загрузка некорректной БЗ"""
        invalid_data = {
            "topics": [
                {
                    "concepts": [
                        {"concept_id": "C001", "term": "Тест"}
                    ]
                }
            ]
        }
        file_path = self._create_temp_json(invalid_data)
        
        loader = KnowledgeBaseLoader([file_path])
        with self.assertRaises(KBValidationError):
            loader.load()
        self.assertFalse(loader._is_loaded)
    
    def test_load_multiple_files(self):
        """Загрузка нескольких файлов"""
        data1 = {
            "metadata": {"version": "1.0"},
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тема 1",
                    "concepts": [
                        {"concept_id": "C001", "term": "Термин 1", "topic_id": "T001"}
                    ]
                }
            ]
        }
        
        data2 = {
            "topics": [
                {
                    "topic_id": "T002",
                    "title": "Тема 2",
                    "concepts": [
                        {"concept_id": "C002", "term": "Термин 2", "topic_id": "T002"}
                    ]
                }
            ]
        }
        
        path1 = self._create_temp_json(data1)
        path2 = self._create_temp_json(data2)
        
        loader = KnowledgeBaseLoader([path1, path2])
        summary = loader.load()
        
        self.assertEqual(summary["concepts_count"], 2)
        self.assertEqual(summary["topics_count"], 2)
        self.assertIsNotNone(loader.get_concept("C001"))
        self.assertIsNotNone(loader.get_concept("C002"))


class TestBuildIndexes(unittest.TestCase):
    """Тесты построения индексов"""
    
    def setUp(self):
        self.temp_paths = []
    
    def tearDown(self):
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_temp_json(self, data):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def _create_valid_kb_file(self):
        data = {
            "metadata": {"version": "1.0"},
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Математика",
                    "concepts": [
                        {"concept_id": "C001", "term": "Число", "topic_id": "T001"},
                        {"concept_id": "C002", "term": "Натуральное число", "topic_id": "T001"},
                        {"concept_id": "C003", "term": "Целое число", "topic_id": "T001"}
                    ]
                },
                {
                    "topic_id": "T002",
                    "title": "Физика",
                    "concepts": [
                        {"concept_id": "CL001", "term": "Масса", "topic_id": "T002"}
                    ]
                }
            ]
        }
        return self._create_temp_json(data)
    
    def test_build_indexes(self):
        """Проверка корректности индексов"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        # Проверка concepts_by_id
        self.assertIn("C001", loader.concepts_by_id)
        self.assertEqual(loader.concepts_by_id["C001"]["term"], "Число")
        self.assertIn("C002", loader.concepts_by_id)
        self.assertIn("CL001", loader.concepts_by_id)
        
        # Проверка concepts_by_term (регистронезависимость)
        self.assertEqual(len(loader.concepts_by_term["число"]), 1)
        self.assertEqual(loader.concepts_by_term["число"][0]["concept_id"], "C001")
        
        # Проверка topics_index
        self.assertIn("T001", loader.topics_index)
        self.assertEqual(loader.topics_index["T001"]["title"], "Математика")
        self.assertEqual(len(loader.topics_index["T001"]["concept_ids"]), 3)
        self.assertIn("T002", loader.topics_index)
        self.assertEqual(len(loader.topics_index["T002"]["concept_ids"]), 1)
    
    def test_skip_invalid_concepts(self):
        """Пропуск некорректных концептов при индексации"""
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тема",
                    "concepts": [
                        {"concept_id": "", "term": "Нет ID", "topic_id": "T001"},
                        {"concept_id": "C001", "term": "Корректный", "topic_id": "T001"}
                    ]
                }
            ]
        }
        file_path = self._create_temp_json(data)
        
        loader = KnowledgeBaseLoader([file_path])
        loader._build_indexes(data)
        
        self.assertEqual(len(loader.concepts_by_id), 1)
        self.assertIn("C001", loader.concepts_by_id)


class TestPublicAPI(unittest.TestCase):
    """Тесты публичного API загрузчика"""
    
    def setUp(self):
        self.temp_paths = []
    
    def tearDown(self):
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_valid_kb_file(self):
        data = {
            "metadata": {"version": "1.0", "author": "Test"},
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Математика",
                    "concepts": [
                        {
                            "concept_id": "C001",
                            "term": "Число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C002"]}
                        },
                        {
                            "concept_id": "C002",
                            "term": "Натуральное число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C003"]}
                        },
                        {
                            "concept_id": "C003",
                            "term": "Целое число",
                            "topic_id": "T001",
                            "relations": {}
                        }
                    ]
                },
                {
                    "topic_id": "T002",
                    "title": "Физика",
                    "concepts": [
                        {
                            "concept_id": "CL001",
                            "term": "Масса",
                            "topic_id": "T002",
                            "relations": {"ассоциация": ["энергия"]}
                        }
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def test_get_concept(self):
        """Получение концепта по ID"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        concept = loader.get_concept("C001")
        self.assertIsNotNone(concept)
        self.assertEqual(concept["term"], "Число")
        self.assertEqual(concept["topic_id"], "T001")
        
        non_existent = loader.get_concept("C999")
        self.assertIsNone(non_existent)
    
    def test_search_by_term(self):
        """Поиск по термину"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        # Точное совпадение
        results = loader.search_by_term("Число")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["concept_id"], "C001")
        
        # Регистронезависимость
        results = loader.search_by_term("число")
        self.assertEqual(len(results), 1)
        
        # Несуществующий термин
        results = loader.search_by_term("Несуществующий")
        self.assertEqual(results, [])
        
        # Поиск с пробелами
        results = loader.search_by_term("  число  ")
        self.assertEqual(len(results), 1)
    
    def test_get_topics_index(self):
        """Получение индекса тем"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        topics = loader.get_topics_index()
        self.assertIn("T001", topics)
        self.assertEqual(topics["T001"]["title"], "Математика")
        self.assertEqual(len(topics["T001"]["concept_ids"]), 3)
    
    def test_resolve_relations(self):
        """Разрешение связей"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        resolved = loader.resolve_relations("C001")
        self.assertIsNotNone(resolved)
        self.assertIn("relations", resolved)
        self.assertIn("надкласс", resolved["relations"])
        
        targets = resolved["relations"]["надкласс"]
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["id"], "C002")
        self.assertEqual(targets[0]["term"], "Натуральное число")
    
    def test_resolve_relations_with_literal(self):
        """Разрешение связей с литеральными строками"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        resolved = loader.resolve_relations("CL001")
        self.assertIsNotNone(resolved)
        targets = resolved["relations"]["ассоциация"]
        self.assertEqual(len(targets), 1)
        self.assertIsNone(targets[0]["id"])
        self.assertEqual(targets[0]["term"], "энергия")
    
    def test_resolve_relations_nonexistent(self):
        """Разрешение связей для несуществующего концепта"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        resolved = loader.resolve_relations("C999")
        self.assertEqual(resolved, {})
    
    def test_resolve_relations_no_relations(self):
        """Концепт без связей"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        resolved = loader.resolve_relations("C003")
        self.assertIsNotNone(resolved)
        self.assertTrue("relations" not in resolved or resolved.get("relations") == {})
    
    def test_get_state_summary(self):
        """Получение статуса загрузки"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        self.assertFalse(loader._is_loaded)
        
        summary_before = loader.get_state_summary()
        self.assertFalse(summary_before["is_loaded"])
        
        loader.load()
        summary_after = loader.get_state_summary()
        self.assertTrue(summary_after["is_loaded"])
        self.assertEqual(summary_after["concepts_count"], 4)
        self.assertEqual(summary_after["topics_count"], 2)


class TestEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""
    
    def setUp(self):
        self.temp_paths = []
    
    def tearDown(self):
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_temp_json(self, data):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def test_very_long_term(self):
        """Очень длинный термин"""
        long_term = "A" * 1000
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тест",
                    "concepts": [
                        {
                            "concept_id": "C001",
                            "term": long_term,
                            "topic_id": "T001"
                        }
                    ]
                }
            ]
        }
        file_path = self._create_temp_json(data)
        
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        result = loader.search_by_term(long_term)
        self.assertEqual(len(result), 1)
    
    def test_special_characters_in_term(self):
        """Специальные символы в термине"""
        special_term = "Тест!@#$%^&*()_+"
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тест",
                    "concepts": [
                        {
                            "concept_id": "C001",
                            "term": special_term,
                            "topic_id": "T001"
                        }
                    ]
                }
            ]
        }
        file_path = self._create_temp_json(data)
        
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        result = loader.search_by_term(special_term)
        self.assertEqual(len(result), 1)
    
    def test_unicode_terms(self):
        """Юникодные термины"""
        unicode_terms = ["Русский", "English", "日本語", "中文", "한국어"]
        concepts = [
            {"concept_id": f"C{i:03d}", "term": term, "topic_id": "T001"}
            for i, term in enumerate(unicode_terms, 1)
        ]
        
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Мультиязычная тема",
                    "concepts": concepts
                }
            ]
        }
        file_path = self._create_temp_json(data)
        
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        for term in unicode_terms:
            results = loader.search_by_term(term)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["term"], term)


class TestDataImmutability(unittest.TestCase):
    """Тесты неизменяемости данных"""
    
    def setUp(self):
        self.temp_paths = []
    
    def tearDown(self):
        for path in self.temp_paths:
            Path(path).unlink(missing_ok=True)
    
    def _create_temp_json(self, data):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            self.temp_paths.append(f.name)
            return f.name
    
    def _create_valid_kb_file(self):
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Математика",
                    "concepts": [
                        {
                            "concept_id": "C001",
                            "term": "Число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C002"]}
                        },
                        {
                            "concept_id": "C002",
                            "term": "Натуральное число",
                            "topic_id": "T001",
                            "relations": {"надкласс": ["C003"]}
                        },
                        {
                            "concept_id": "C003",
                            "term": "Целое число",
                            "topic_id": "T001",
                            "relations": {}
                        }
                    ]
                }
            ]
        }
        return self._create_temp_json(data)
    
    def test_concept_copy_is_independent(self):
        """Проверка, что get_concept возвращает тот же объект"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        # Получаем один и тот же концепт дважды
        concept1 = loader.get_concept("C001")
        concept2 = loader.get_concept("C001")
        
        # Это один и тот же объект в памяти
        self.assertIs(concept1, concept2)
        
        # Изменение через одну переменную видно через другую
        concept1["term"] = "Новое значение"
        self.assertEqual(concept2["term"], "Новое значение")
    
    def test_resolve_relations_does_not_modify_original(self):
        """resolve_relations не изменяет исходный концепт"""
        file_path = self._create_valid_kb_file()
        loader = KnowledgeBaseLoader([file_path])
        loader.load()
        
        original_relations = loader.get_concept("C001").get("relations", {}).copy()
        
        loader.resolve_relations("C001")
        
        # Оригинал не должен измениться
        self.assertEqual(loader.get_concept("C001")["relations"], original_relations)


def _kb_dict(extra_concepts=None):
    """Небольшая корректная БЗ в формате JSON-файлов проекта."""
    concepts = [
        {"concept_id": "C001", "term": "Число", "topic_id": "T001", "relations": {"надкласс": ["C002"]}},
        {"concept_id": "C002", "term": "Целое число", "topic_id": "T001", "relations": {}},
    ]
    concepts.extend(extra_concepts or [])
    return {"metadata": {"version": "1.0"}, "topics": [{"topic_id": "T001", "title": "Математика", "concepts": concepts}]}


class _AdminDirMixin:
    """Временная директория data_dir для AdminSolver / роутера (сценарий 7)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = self._tmp.name

    def write_json(self, name, data):
        path = os.path.join(self.data_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path


class TestAdminSolver(_AdminDirMixin, unittest.TestCase):
    """AdminSolver.run_validation: все ветки ответа."""

    def solver(self, loader_class=KnowledgeBaseLoader):
        return AdminSolver(loader_class, self.data_dir)

    def test_default_data_dir_is_stored(self):
        solver = AdminSolver(KnowledgeBaseLoader)
        self.assertEqual(solver.data_dir, "data")
        self.assertIs(solver.kb_loader_class, KnowledgeBaseLoader)

    def test_directory_not_found(self):
        missing = os.path.join(self.data_dir, "no_such_dir")
        result = AdminSolver(KnowledgeBaseLoader, missing).run_validation()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "DIR_NOT_FOUND")
        self.assertIn(missing, result["message"])

    def test_empty_directory(self):
        result = self.solver().run_validation()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "NO_FILES")

    def test_directory_without_json_files(self):
        with open(os.path.join(self.data_dir, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("не json")
        self.assertEqual(self.solver().run_validation()["error_code"], "NO_FILES")

    def test_successful_validation(self):
        self.write_json("kb.json", _kb_dict())
        with open(os.path.join(self.data_dir, "readme.txt"), "w", encoding="utf-8") as f:
            f.write("посторонний файл игнорируется")
        result = self.solver().run_validation()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["files_checked"], 1)
        self.assertEqual(result["stats"]["concepts_count"], 2)
        self.assertIn("прошла", result["message"])

    def test_several_files_are_passed_to_loader_sorted(self):
        seen = {}

        class RecordingLoader:
            def __init__(self, paths):
                seen["paths"] = list(paths)

            def load(self):
                return {"concepts_count": 0}

        for name in ("b.json", "a.json", "c.json"):
            self.write_json(name, {})
        result = self.solver(RecordingLoader).run_validation()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["files_checked"], 3)
        self.assertEqual([os.path.basename(p) for p in seen["paths"]], ["a.json", "b.json", "c.json"])

    def test_validation_error_is_reported(self):
        dup = [{"concept_id": "C001", "term": "Дубликат", "topic_id": "T001", "relations": {}}]
        self.write_json("kb.json", _kb_dict(dup))
        result = self.solver().run_validation()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "VALIDATION_FAILED")
        self.assertTrue(result["details"])
        self.assertEqual(result["files_checked"], 1)

    def test_validation_error_raised_by_loader_class(self):
        class FailingLoader:
            def __init__(self, paths):
                pass

            def load(self):
                raise KBValidationError("цикл C001 -> C002")

        self.write_json("kb.json", {})
        result = self.solver(FailingLoader).run_validation()
        self.assertEqual(result["error_code"], "VALIDATION_FAILED")
        self.assertIn("цикл", result["details"])

    def test_broken_json_is_critical_error(self):
        with open(os.path.join(self.data_dir, "broken.json"), "w", encoding="utf-8") as f:
            f.write("{не json")
        result = self.solver().run_validation()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "CRITICAL_ERROR")
        self.assertIn("Критическая ошибка", result["message"])
        self.assertEqual(result["files_checked"], 1)

    def test_unexpected_loader_exception_is_critical_error(self):
        class CrashingLoader:
            def __init__(self, paths):
                raise RuntimeError("нет доступа")

        self.write_json("kb.json", {})
        result = self.solver(CrashingLoader).run_validation()
        self.assertEqual(result["error_code"], "CRITICAL_ERROR")
        self.assertIn("нет доступа", result["message"])


class TestAdminThroughRouter(_AdminDirMixin, unittest.TestCase):
    """Действие admin через API-шлюз (то, что вызывает страница «Валидация»)."""

    def make_router(self):
        loader = KnowledgeBaseLoader([self.write_json("kb.json", _kb_dict())])
        loader.load()
        return SolverRouter(loader, data_dir=self.data_dir)

    def test_success(self):
        resp = self.make_router().handle_request({"action": "admin", "params": {}})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["action"], "admin")
        self.assertEqual(resp["data"]["files_checked"], 1)
        self.assertEqual(resp["data"]["stats"]["concepts_count"], 2)
        self.assertIn("прошла", resp["explanation"]["summary"])
        self.assertIsNone(resp["error"])

    def test_validation_failure_becomes_router_error(self):
        router = self.make_router()
        dup = [{"concept_id": "C001", "term": "Дубликат", "topic_id": "T001", "relations": {}}]
        self.write_json("kb.json", _kb_dict(dup))
        resp = router.handle_request({"action": "admin"})
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error"]["code"], "VALIDATION_FAILED")
        self.assertTrue(resp["error"]["details"])
        self.assertIsNone(resp["data"])

    def test_missing_directory_error_code_is_propagated(self):
        router = self.make_router()
        router.solvers["admin"].data_dir = os.path.join(self.data_dir, "gone")
        resp = router.handle_request({"action": "admin", "params": {}})
        self.assertEqual(resp["error"]["code"], "DIR_NOT_FOUND")

    def test_no_files_error_code_is_propagated(self):
        router = self.make_router()
        router.solvers["admin"].data_dir = tempfile.mkdtemp(dir=self.data_dir)
        resp = router.handle_request({"action": "admin", "params": {}})
        self.assertEqual(resp["error"]["code"], "NO_FILES")

    def test_error_without_code_uses_defaults(self):
        router = self.make_router()
        router.solvers["admin"].run_validation = lambda: {"status": "error"}
        resp = router.handle_request({"action": "admin", "params": {}})
        self.assertEqual(resp["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(resp["error"]["message"], "Ошибка валидации")


if __name__ == '__main__':
    unittest.main()
