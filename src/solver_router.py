"""
Маршрутизатор запросов к решателям задач (API-шлюз / Фасад).
Реализует стратегию fail-fast и централизованную валидацию.
"""

import re
from typing import Dict, Any, Optional
from .solver_analytics import AnalyticsSolver
from .solver_admin import AdminSolver


class SolverRouter:
    """Центральная точка входа для всех запросов к решателям задач"""

    # Регулярное выражение для валидации concept_id из ПЗ (раздел 2.5.1)
    ID_PATTERN = re.compile(r'^C(?:L)?\d{2,4}$')

    def __init__(self, kb_loader):
        self.loader = kb_loader
        
        # Реестр зарегистрированных решателей (R)
        self.registry = {
            'analytics': AnalyticsSolver(kb_loader),
            'admin': AdminSolver(type(kb_loader), data_dir='data'),
            # Сюда позже добавятся решатели Ани, Юли и Даны:
            # 'trajectory': TrajectorySolver(kb_loader),
            # 'comparator': ComparatorSolver(kb_loader),
            # 'diagnostics': DiagnosticsSolver(kb_loader),
        }

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка входящего запроса Q = <action, params>.
        """
        action = request.get('action')
        params = request.get('params', {})

        # Этап 1: Поиск action в реестре
        if not action or action not in self.registry:
            return {
                'status': 'error',
                'error_code': 'UNKNOWN_ACTION',
                'message': f'Неизвестный тип действия: {action}',
                'available_actions': list(self.registry.keys())
            }

        # Этап 2 и 3: Синтаксическая и семантическая валидация (Fail-Fast)
        validation_error = self._validate_params(action, params)
        if validation_error:
            return validation_error

        # Этап 4: Передача валидированных параметров в метод execute целевого решателя
        try:
            solver = self.registry[action]
            
            if action == 'analytics':
                data = solver.analyze_gaps(
                    student_models=params.get('student_models', []),
                    target_concepts=params.get('target_concepts', []),
                    threshold=params.get('threshold', 0.5)
                )
            elif action == 'admin':
                data = solver.run_validation()
            else:
                data = {'message': f'Решатель {action} еще в разработке'}

            return {
                'status': 'success',
                'action': action,
                'data': data
            }

        except Exception as e:
            return {
                'status': 'error',
                'error_code': 'SOLVER_EXECUTION_ERROR',
                'message': str(e)
            }

    def _validate_params(self, action: str, params: Dict) -> Optional[Dict]:
        """
        Валидация параметров по стратегии fail-fast.
        """
        # Проверка обязательных ключей
        if action == 'analytics':
            if 'student_models' not in params or 'target_concepts' not in params:
                return {
                    'status': 'error',
                    'error_code': 'MISSING_PARAM',
                    'message': 'Отсутствуют обязательные параметры: student_models или target_concepts'
                }
            target_concepts = params.get('target_concepts', [])
        else:
            # Для других сценариев (например, admin) params может быть пустым
            target_concepts = []

        # Синтаксическая и семантическая валидация идентификаторов
        for concept_id in target_concepts:
            # 1. Проверка формата (regex)
            if not self.ID_PATTERN.match(str(concept_id)):
                return {
                    'status': 'error',
                    'error_code': 'BAD_ID_FORMAT',
                    'message': f'Неверный формат идентификатора: {concept_id}. Ожидается Cxx или CLxx.'
                }
            # 2. Проверка существования в БЗ (O(1) через in-memory индекс)
            if concept_id not in self.loader.concepts_by_id:
                return {
                    'status': 'error',
                    'error_code': 'CONCEPT_NOT_FOUND',
                    'message': f'Концепт {concept_id} не найден в базе знаний.'
                }

        return None
