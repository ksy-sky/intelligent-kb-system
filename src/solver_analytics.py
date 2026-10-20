"""
Решатель аналитики успеваемости и выявления групповых пробелов (Сценарий 8).
Реализует алгоритм агрегации данных об освоенных концептах группы студентов.
"""

import re
from typing import Dict, List, Set, Tuple


class AnalyticsSolver:
    """Решатель для анализа успеваемости группы студентов (Сценарий 8)"""

    def __init__(self, kb_loader):
        """
        Args:
            kb_loader: экземпляр KnowledgeBaseLoader для доступа к БЗ
        """
        self.loader = kb_loader

    def analyze_gaps(
        self, 
        student_models: List[Set[str]], 
        target_concepts: List[str],
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        Выявление системных проблем в усвоении материала.
        
        Args:
            student_models: список множеств освоенных concept_id для каждого студента
            target_concepts: список целевых концептов для анализа
            threshold: порог значимости пробела (theta)
            
        Returns:
            ранжированный список концептов с долей непокрытия
        """
        # Этап 1: Валидация и инициализация счетчиков
        gaps_counter = {c: 0 for c in target_concepts}
        n = len(student_models)
        
        if n == 0:
            return []

        # Этап 2: Агрегация (вычисление разности множеств)
        for s in student_models:
            # Приводим s к множеству, если оно вдруг список
            s_set = set(s)
            for c in set(target_concepts) - s_set:
                if c in gaps_counter:
                    gaps_counter[c] += 1

        # Этап 3 и 4: Нормализация и фильтрация по порогу theta
        result = []
        for c, count in gaps_counter.items():
            p = count / n
            if p >= threshold:
                # Этап 5: Обогащение (извлечение термина и topic_id для объяснения)
                concept_data = self.loader.concepts_by_id.get(c, {})
                result.append({
                    'concept_id': c,
                    'term': concept_data.get('term', 'Unknown'),
                    'topic_id': concept_data.get('topic_id', 'Unknown'),
                    'gap_ratio': round(p, 2),
                    'students_with_gap': count,
                    'total_students': n
                })

        # Сортировка: по убыванию gap_ratio, затем лексикографически по concept_id (для детерминированности)
        result.sort(key=lambda x: (-x['gap_ratio'], x['concept_id']))
        
        return result
