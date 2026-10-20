"""
Решатель администрирования и валидации базы знаний (Сценарий 7).
"""

import os
from typing import Dict, Any


class AdminSolver:
    """Решатель для проверки целостности БЗ преподавателем"""

    def __init__(self, kb_loader_class, data_dir: str = 'data'):
        """
        Args:
            kb_loader_class: класс KnowledgeBaseLoader (для создания нового инстанса)
            data_dir: директория с JSON-файлами
        """
        self.kb_loader_class = kb_loader_class
        self.data_dir = data_dir

    def run_validation(self) -> Dict[str, Any]:
        """
        Запуск полной валидации всех JSON-файлов базы знаний.
        Проверяет уникальность ID, обязательные поля, ссылочную целостность и ацикличность.
        """
        try:
            json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        except FileNotFoundError:
            return {
                'status': 'error',
                'error_code': 'DIR_NOT_FOUND',
                'message': f'Директория "{self.data_dir}" не найдена.'
            }

        if not json_files:
            return {
                'status': 'error',
                'error_code': 'NO_FILES',
                'message': 'Не найдено JSON-файлов для валидации.'
            }

        file_paths = [os.path.join(self.data_dir, f) for f in sorted(json_files)]
        
        try:
            # Попытка загрузки автоматически запускает kb_validator внутри KnowledgeBaseLoader
            loader = self.kb_loader_class(file_paths)
            stats = loader.load()
            
            return {
                'status': 'success',
                'message': 'База знаний успешно загружена и прошла полную валидацию.',
                'stats': stats,
                'files_checked': len(json_files)
            }
            
        except ValueError as e:
            # Перехватываем ошибки валидации (циклы, дубликаты ID, висячие ссылки)
            return {
                'status': 'error',
                'error_code': 'VALIDATION_FAILED',
                'message': 'Ошибка валидации базы знаний!',
                'details': str(e),
                'files_checked': len(json_files)
            }
        except Exception as e:
            return {
                'status': 'error',
                'error_code': 'CRITICAL_ERROR',
                'message': f'Критическая ошибка при загрузке: {str(e)}',
                'files_checked': len(json_files)
            }
