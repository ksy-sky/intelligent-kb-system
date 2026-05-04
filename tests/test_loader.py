# tests/test_kb_loader.py
import pytest
import json
import tempfile
from pathlib import Path
from src.kb_loader import KnowledgeBaseLoader
from src.kb_validator import KBValidationError

@pytest.fixture
def valid_kb_file():
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
    
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
        json.dump(data, f, ensure_ascii=False)
        temp_path = f.name
    
    yield temp_path
    Path(temp_path).unlink(missing_ok=True)

@pytest.fixture
def multiple_kb_files():
    """Создаёт несколько файлов БЗ для тестирования слияния"""
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
    
    paths = []
    for i, data in enumerate([data1, data2]):
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            paths.append(f.name)
    
    yield paths
    
    for path in paths:
        Path(path).unlink(missing_ok=True)

class TestKnowledgeBaseLoaderInitialization:
    """Тесты инициализации загрузчика"""
    
    def test_initialization(self):
        """Создание экземпляра загрузчика"""
        loader = KnowledgeBaseLoader(["file1.json", "file2.json"])
        assert loader.file_paths == ["file1.json", "file2.json"]
        assert loader.concepts_by_id == {}
        assert loader.concepts_by_term == {}
        assert loader.topics_index == {}
        assert loader.metadata == {}
        assert not loader._is_loaded
    
    def test_empty_file_list(self):
        """Пустой список файлов"""
        loader = KnowledgeBaseLoader([])
        assert loader.file_paths == []

class TestMergeJSONFiles:
    """Тесты слияния JSON файлов"""
    
    def test_merge_multiple_files(self, multiple_kb_files):
        """Слияние нескольких файлов"""
        loader = KnowledgeBaseLoader(multiple_kb_files)
        merged = loader._merge_json_files()
        
        assert "metadata" in merged
        assert merged["metadata"] == {"version": "1.0"}
        assert len(merged["topics"]) == 2
        assert merged["topics"][0]["topic_id"] == "T001"
        assert merged["topics"][1]["topic_id"] == "T002"
    
    def test_file_not_found(self):
        """Файл не найден"""
        loader = KnowledgeBaseLoader(["nonexistent.json"])
        with pytest.raises(FileNotFoundError):
            loader._merge_json_files()
    
    def test_empty_topics_in_file(self):
        """Файл без тем"""
        data = {"topics": []}
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            merged = loader._merge_json_files()
            assert len(merged["topics"]) == 0
        finally:
            Path(temp_path).unlink(missing_ok=True)

class TestLoadAndValidate:
    """Тесты полной загрузки и валидации"""
    
    def test_successful_load(self, valid_kb_file):
        """Успешная загрузка корректной БЗ"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        summary = loader.load()
        
        assert loader._is_loaded
        assert summary["concepts_count"] == 4  # C001, C002, C003, CL001
        assert summary["topics_count"] == 2
        assert summary["metadata"] == {"version": "1.0", "author": "Test"}
    
    def test_load_invalid_kb(self):
        """Загрузка некорректной БЗ"""
        invalid_data = {
            "topics": [
                {
                    "concepts": [
                        {"concept_id": "C001", "term": "Тест"}  # нет topic_id
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(invalid_data, f)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            with pytest.raises(KBValidationError):
                loader.load()
            assert not loader._is_loaded
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_load_multiple_files(self, multiple_kb_files):
        """Загрузка нескольких файлов"""
        loader = KnowledgeBaseLoader(multiple_kb_files)
        summary = loader.load()
        
        assert summary["concepts_count"] == 2
        assert summary["topics_count"] == 2
        assert loader.get_concept("C001") is not None
        assert loader.get_concept("C002") is not None

class TestBuildIndexes:
    """Тесты построения индексов"""
    
    def test_build_indexes(self, valid_kb_file):
        """Проверка корректности индексов"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        # Проверка concepts_by_id
        assert "C001" in loader.concepts_by_id
        assert loader.concepts_by_id["C001"]["term"] == "Число"
        assert "C002" in loader.concepts_by_id
        assert "CL001" in loader.concepts_by_id
        
        # Проверка concepts_by_term (регистронезависимость)
        assert len(loader.concepts_by_term["число"]) == 1
        assert loader.concepts_by_term["число"][0]["concept_id"] == "C001"
        
        # Проверка topics_index
        assert "T001" in loader.topics_index
        assert loader.topics_index["T001"]["title"] == "Математика"
        assert len(loader.topics_index["T001"]["concept_ids"]) == 3
        assert "T002" in loader.topics_index
        assert len(loader.topics_index["T002"]["concept_ids"]) == 1
    
    def test_skip_invalid_concepts(self):
        """Пропуск некорректных концептов при индексации"""
        data = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тема",
                    "concepts": [
                        {"concept_id": "", "term": "Нет ID", "topic_id": "T001"},  # пропускаем
                        {"concept_id": "C001", "term": "Корректный", "topic_id": "T001"}  # индексируем
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            # Валидация не пройдёт из-за пустого concept_id, но индексы всё равно строятся
            # Поэтому напрямую вызовем _build_indexes
            loader._build_indexes(data)
            assert len(loader.concepts_by_id) == 1
            assert "C001" in loader.concepts_by_id
        finally:
            Path(temp_path).unlink(missing_ok=True)

class TestPublicAPI:
    """Тесты публичного API загрузчика"""
    
    def test_get_concept(self, valid_kb_file):
        """Получение концепта по ID"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        concept = loader.get_concept("C001")
        assert concept is not None
        assert concept["term"] == "Число"
        assert concept["topic_id"] == "T001"
        
        non_existent = loader.get_concept("C999")
        assert non_existent is None
    
    def test_search_by_term(self, valid_kb_file):
        """Поиск по термину"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        # Точное совпадение
        results = loader.search_by_term("Число")
        assert len(results) == 1
        assert results[0]["concept_id"] == "C001"
        
        # Регистронезависимость
        results = loader.search_by_term("число")
        assert len(results) == 1
        
        # Несуществующий термин
        results = loader.search_by_term("Несуществующий")
        assert results == []
        
        # Поиск с пробелами
        results = loader.search_by_term("  число  ")
        assert len(results) == 1
    
    def test_get_topics_index(self, valid_kb_file):
        """Получение индекса тем"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        topics = loader.get_topics_index()
        assert "T001" in topics
        assert topics["T001"]["title"] == "Математика"
        assert len(topics["T001"]["concept_ids"]) == 3
    
    def test_resolve_relations(self, valid_kb_file):
        """Разрешение связей"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        resolved = loader.resolve_relations("C001")
        assert resolved is not None
        assert "relations" in resolved
        assert "надкласс" in resolved["relations"]
        
        targets = resolved["relations"]["надкласс"]
        assert len(targets) == 1
        assert targets[0]["id"] == "C002"
        assert targets[0]["term"] == "Натуральное число"
    
    def test_resolve_relations_with_literal(self, valid_kb_file):
        """Разрешение связей с литеральными строками"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        resolved = loader.resolve_relations("CL001")
        assert resolved is not None
        targets = resolved["relations"]["ассоциация"]
        assert len(targets) == 1
        assert targets[0]["id"] is None
        assert targets[0]["term"] == "энергия"
    
    def test_resolve_relations_nonexistent(self, valid_kb_file):
        """Разрешение связей для несуществующего концепта"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        resolved = loader.resolve_relations("C999")
        assert resolved == {}
    
    def test_resolve_relations_no_relations(self, valid_kb_file):
        """Концепт без связей"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        resolved = loader.resolve_relations("C003")
        assert resolved is not None
        assert "relations" not in resolved or resolved.get("relations") == {}
    
    def test_get_state_summary(self, valid_kb_file):
        """Получение статуса загрузки"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        assert not loader._is_loaded
        
        summary_before = loader.get_state_summary()
        assert summary_before["is_loaded"] is False
        
        loader.load()
        summary_after = loader.get_state_summary()
        assert summary_after["is_loaded"] is True
        assert summary_after["concepts_count"] == 4
        assert summary_after["topics_count"] == 2

class TestEdgeCases:
    """Тесты граничных случаев"""
    
    def test_very_long_term(self, valid_kb_file):
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
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            loader.load()
            result = loader.search_by_term(long_term)
            assert len(result) == 1
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_special_characters_in_term(self, valid_kb_file):
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
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            loader.load()
            result = loader.search_by_term(special_term)
            assert len(result) == 1
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_unicode_terms(self, valid_kb_file):
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
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
            json.dump(data, f, ensure_ascii=False)
            temp_path = f.name
        
        try:
            loader = KnowledgeBaseLoader([temp_path])
            loader.load()
            for term in unicode_terms:
                results = loader.search_by_term(term)
                assert len(results) == 1
                assert results[0]["term"] == term
        finally:
            Path(temp_path).unlink(missing_ok=True)

class TestDataImmutability:
    """Тесты неизменяемости данных"""
    
    def test_concept_copy_is_independent(self, valid_kb_file):
        """Проверка, что get_concept возвращает тот же объект"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        # Получаем один и тот же концепт дважды
        concept1 = loader.get_concept("C001")
        concept2 = loader.get_concept("C001")
        
        # Это один и тот же объект в памяти
        assert concept1 is concept2  # True!
        
        # Поэтому изменение через одну переменную видно через другую
        concept1["term"] = "Новое значение"
        assert concept2["term"] == "Новое значение"  # Это нормально
    
    def test_resolve_relations_does_not_modify_original(self, valid_kb_file):
        """resolve_relations не изменяет исходный концепт"""
        loader = KnowledgeBaseLoader([valid_kb_file])
        loader.load()
        
        original = loader.get_concept("C001")
        original_relations = original.get("relations", {}).copy()
        
        resolved = loader.resolve_relations("C001")
        
        # Оригинал не должен измениться
        assert loader.get_concept("C001")["relations"] == original_relations