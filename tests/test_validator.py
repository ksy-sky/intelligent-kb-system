# tests/test_kb_validator.py (переписан для unittest)
import unittest
import sys
from pathlib import Path
import io
from contextlib import redirect_stdout, redirect_stderr

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kb_validator import (
    validate_kb, 
    KBValidationError, 
    _validate_concepts_schema,
    _validate_referential_integrity,
    _validate_hierarchy_acyclicity,
    ID_PATTERN
)


class TestIDPattern(unittest.TestCase):
    """Тесты для проверки формата ID"""
    
    def test_valid_concept_ids(self):
        """Проверка корректных ID концептов"""
        valid_ids = ["C001", "C999", "C1234", "CL001", "CL999", "CL1234", "C12", "C99"]
        for cid in valid_ids:
            self.assertIsNotNone(ID_PATTERN.match(cid), f"ID {cid} должен быть валидным")
    
    def test_invalid_concept_ids(self):
        """Проверка некорректных ID концептов"""
        invalid_ids = [
            "C", "C0", "C00000", "C100000",
            "CL", "CL0", "CL00000", "CL100000",
            "D001", "1C001", "C-001", "c001",
            "", "   ", "C01a", "C12.3", "C 001"
        ]
        for cid in invalid_ids:
            self.assertIsNone(ID_PATTERN.match(cid), f"ID {cid} должен быть невалидным")


class TestValidateConceptsSchema(unittest.TestCase):
    """Тесты для _validate_concepts_schema"""
    
    def test_empty_concepts_list(self):
        """Пустой список концептов"""
        errors = _validate_concepts_schema([])
        self.assertEqual(errors, [])
    
    def test_valid_concept(self):
        """Корректный концепт"""
        concepts = [{
            "concept_id": "C001",
            "term": "Тестовый термин",
            "topic_id": "T001",
            "relations": {
                "надкласс": ["C002"],
                "ассоциация": ["термин"]
            }
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertEqual(errors, [])
    
    def test_missing_concept_id(self):
        """Отсутствует concept_id"""
        concepts = [{
            "term": "Тест",
            "topic_id": "T001"
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Отсутствует concept_id" in e for e in errors))
    
    def test_empty_concept_id(self):
        """Пустой concept_id"""
        concepts = [{
            "concept_id": "   ",
            "term": "Тест",
            "topic_id": "T001"
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Отсутствует concept_id" in e for e in errors))
    
    def test_invalid_concept_id_format(self):
        """Неверный формат ID"""
        concepts = [{
            "concept_id": "INVALID",
            "term": "Тест",
            "topic_id": "T001"
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Некорректный формат" in e for e in errors))
    
    def test_duplicate_concept_id(self):
        """Дублирующийся ID"""
        concepts = [
            {"concept_id": "C001", "term": "Термин1", "topic_id": "T001"},
            {"concept_id": "C001", "term": "Термин2", "topic_id": "T001"}
        ]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Дублирующийся" in e for e in errors))
    
    def test_empty_term(self):
        """Пустой term"""
        concepts = [{
            "concept_id": "C001",
            "term": "",
            "topic_id": "T001"
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Пустое поле 'term'" in e for e in errors))
    
    def test_missing_topic_id(self):
        """Отсутствует topic_id"""
        concepts = [{
            "concept_id": "C001",
            "term": "Тест"
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("Отсутствует 'topic_id'" in e for e in errors))
    
    def test_invalid_relations_type(self):
        """relations не является словарём"""
        concepts = [{
            "concept_id": "C001",
            "term": "Тест",
            "topic_id": "T001",
            "relations": ["надкласс", "C002"]
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("объектом" in e for e in errors))
    
    def test_invalid_targets_type(self):
        """targets не является списком"""
        concepts = [{
            "concept_id": "C001",
            "term": "Тест",
            "topic_id": "T001",
            "relations": {
                "надкласс": "C002"
            }
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("массивом" in e for e in errors))
    
    def test_invalid_target_element_type(self):
        """Элемент targets не строка"""
        concepts = [{
            "concept_id": "C001",
            "term": "Тест",
            "topic_id": "T001",
            "relations": {
                "надкласс": ["C002", 123]
            }
        }]
        errors = _validate_concepts_schema(concepts)
        self.assertTrue(any("строками" in e for e in errors))


class TestValidateReferentialIntegrity(unittest.TestCase):
    """Тесты для _validate_referential_integrity"""
    
    def test_no_warnings_for_valid_references(self):
        """Нет предупреждений для корректных ссылок"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"надкласс": ["C002"]}},
            "C002": {"concept_id": "C002", "relations": {}}
        }
        
        with io.StringIO() as buf:
            with redirect_stdout(buf):
                errors = _validate_referential_integrity(concepts)
                output = buf.getvalue()
            
            self.assertEqual(output, "")
            self.assertEqual(errors, [])
    
    def test_warning_for_dangling_reference(self):
        """Предупреждение для висячей ссылки"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"надкласс": ["C999"]}}
        }
        
        with io.StringIO() as buf:
            with redirect_stdout(buf):
                errors = _validate_referential_integrity(concepts)
                output = buf.getvalue()
            
            self.assertIn("Висячая ссылка", output)
            self.assertIn("C999", output)
            self.assertEqual(errors, [])
    
    def test_multiple_dangling_references(self):
        """Несколько висячих ссылок"""
        concepts = {
            "C001": {
                "concept_id": "C001", 
                "relations": {
                    "надкласс": ["C999", "C888"],
                    "ассоциация": ["C777"]
                }
            }
        }
        
        with io.StringIO() as buf:
            with redirect_stdout(buf):
                errors = _validate_referential_integrity(concepts)
                output = buf.getvalue()
            
            self.assertEqual(output.count("Висячая ссылка"), 3)
            self.assertEqual(errors, [])
    
    def test_literal_strings_not_warned(self):
        """Литеральные строки (не ID) не вызывают предупреждений"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"ассоциация": ["некоторый текст"]}}
        }
        
        with io.StringIO() as buf:
            with redirect_stdout(buf):
                errors = _validate_referential_integrity(concepts)
                output = buf.getvalue()
            
            self.assertNotIn("Висячая ссылка", output)
            self.assertEqual(errors, [])


class TestValidateHierarchyAcyclicity(unittest.TestCase):
    """Тесты для _validate_hierarchy_acyclicity"""
    
    def test_no_cycles_in_simple_hierarchy(self):
        """Нет циклов в простой иерархии"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"надкласс": ["C002"]}},
            "C002": {"concept_id": "C002", "relations": {"надкласс": ["C003"]}},
            "C003": {"concept_id": "C003", "relations": {}}
        }
        errors = _validate_hierarchy_acyclicity(concepts)
        self.assertEqual(errors, [])
    
    def test_cycle_detected(self):
        """Обнаружение цикла"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"надкласс": ["C002"]}},
            "C002": {"concept_id": "C002", "relations": {"надкласс": ["C003"]}},
            "C003": {"concept_id": "C003", "relations": {"надкласс": ["C001"]}}
        }
        errors = _validate_hierarchy_acyclicity(concepts)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Цикл" in e for e in errors))
    
    def test_self_cycle(self):
        """Сам цикл (концепт ссылается на себя)"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"надкласс": ["C001"]}}
        }
        errors = _validate_hierarchy_acyclicity(concepts)
        self.assertGreater(len(errors), 0)
        self.assertIn("C001", errors[0])
    
    def test_multiple_relations_only_hierarchy_checked(self):
        """Проверяются только иерархические отношения (надкласс)"""
        concepts = {
            "C001": {"concept_id": "C001", "relations": {"ассоциация": ["C002"]}},
            "C002": {"concept_id": "C002", "relations": {"ассоциация": ["C001"]}}
        }
        errors = _validate_hierarchy_acyclicity(concepts)
        self.assertEqual(errors, [])
    
    def test_mixed_relations(self):
        """Смешанные отношения - только надкласс создаёт цикл"""
        concepts = {
            "C001": {
                "concept_id": "C001", 
                "relations": {
                    "надкласс": ["C002"],
                    "ассоциация": ["C003"]
                }
            },
            "C002": {"concept_id": "C002", "relations": {"надкласс": ["C001"]}},
            "C003": {"concept_id": "C003", "relations": {}}
        }
        errors = _validate_hierarchy_acyclicity(concepts)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Цикл" in e for e in errors))


class TestValidateKB(unittest.TestCase):
    """Интеграционные тесты для validate_kb"""
    
    def test_valid_kb_structure(self):
        """Корректная структура БЗ"""
        valid_kb = {
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
        # Не должно быть исключения
        validate_kb(valid_kb)
    
    def test_missing_topics_key(self):
        """Отсутствует ключ topics"""
        invalid_kb = {"something": []}
        with self.assertRaisesRegex(KBValidationError, "Отсутствует корневой ключ 'topics'"):
            validate_kb(invalid_kb)
    
    def test_topics_not_list(self):
        """topics не массив"""
        invalid_kb = {"topics": "not a list"}
        with self.assertRaisesRegex(KBValidationError, "Поле 'topics' должно быть массивом."):
            validate_kb(invalid_kb)
    
    def test_complex_valid_kb(self):
        """Сложная корректная БЗ"""
        valid_kb = {
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
        validate_kb(valid_kb)
    
    def test_kb_with_multiple_errors(self):
        """БЗ с несколькими ошибками"""
        invalid_kb = {
            "topics": [
                {
                    "topic_id": "T001",
                    "title": "Тема",
                    "concepts": [
                        {"concept_id": "C001", "term": "", "topic_id": "T001"},
                        {"concept_id": "C001", "term": "Дубликат", "topic_id": "T001"},
                        {"concept_id": "INVALID", "term": "Термин", "topic_id": "T001"}
                    ]
                }
            ]
        }
        with self.assertRaises(KBValidationError) as context:
            validate_kb(invalid_kb)
        
        error_msg = str(context.exception)
        self.assertIn("Валидация БЗ не пройдена", error_msg)
        self.assertIn("Пустое поле 'term'", error_msg)
        self.assertIn("Дублирующийся", error_msg)
        self.assertIn("Некорректный формат", error_msg)


if __name__ == '__main__':
    unittest.main()