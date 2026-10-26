"""
solver_trajectory.py — Решатель построения учебной траектории и рекомендаций (Сценарий 5).
Реализует топологическую сортировку (алгоритм Кана) и формирование контекстных рекомендаций.
"""
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)


class TrajectorySolver:
    """Решатель для построения индивидуальной учебной траектории и рекомендаций."""

    def __init__(self, loader):
        """
        Args:
            loader: экземпляр KnowledgeBaseLoader для доступа к БЗ
        """
        self.loader = loader

    def build_learning_plan(self, gap_ids: List[str]) -> List[Dict[str, str]]:
        """
        Построение упорядоченного плана изучения на основе множества пробелов.

        Args:
            gap_ids: список идентификаторов концептов, которые необходимо изучить

        Returns:
            упорядоченный список словарей вида {'concept_id': ..., 'term': ..., 'reason': ...}
        """
        if not gap_ids:
            return []

        # Фильтрация существующих концептов
        valid_gaps = [gid for gid in gap_ids if gid in self.loader.concepts_by_id]
        if not valid_gaps:
            return []

        # Этап 1: Построение локального DAG из пробелов
        local_graph = self._build_subgraph(valid_gaps)

        # Этап 2: Вычисление входящих степеней
        in_degree = {cid: 0 for cid in valid_gaps}
        for src, neighbors in local_graph.items():
            for dst in neighbors:
                if dst in in_degree:
                    in_degree[dst] += 1

        # Инициализация очереди вершинами с нулевой входящей степенью (лексикографически)
        queue = sorted([cid for cid, deg in in_degree.items() if deg == 0])

        trajectory = []

        # Этап 3: Алгоритм Кана
        while queue:
            curr_cid = queue.pop(0)
            concept = self.loader.concepts_by_id[curr_cid]

            # Генерация объяснения включения концепта в план
            reason = self._generate_reason(curr_cid, local_graph, in_degree)

            trajectory.append({
                'concept_id': curr_cid,
                'term': concept.get('term', 'Unknown'),
                'topic_id': concept.get('topic_id', ''),
                'reason': reason
            })

            # Обновление входящих степеней соседей
            for neighbor in local_graph.get(curr_cid, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        # Вставка с сохранением лексикографического порядка
                        self._insert_sorted(queue, neighbor)

        # Проверка на цикл (если обработано меньше вершин, чем было во входном наборе)
        if len(trajectory) != len(valid_gaps):
            processed_ids = {t['concept_id'] for t in trajectory}
            cycle_nodes = set(valid_gaps) - processed_ids
            raise ValueError(f"Обнаружен цикл в пререквизитах среди концептов: {cycle_nodes}")

        return trajectory

    def generate_recommendations(self, plan: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Формирование контекстных рекомендаций по учебным материалам для каждого шага плана.

        Args:
            plan: упорядоченный список концептов из build_learning_plan

        Returns:
            список рекомендаций с определениями, примерами и лабораторными работами
        """
        recommendations = []

        for step in plan:
            cid = step['concept_id']

            # Защита от концептов, отсутствующих в базе знаний
            # (например, если план собирался до изменения БЗ преподавателем)
            if cid not in self.loader.concepts_by_id:
                logger.warning(f"Concept {cid} not found in knowledge base, skipped")
                continue

            concept = self.loader.concepts_by_id[cid]

            # Получение определения (с наследованием от предков при необходимости)
            definition = concept.get('definition', '')
            inherited_from = None

            if not definition:
                ancestor_def, ancestor_term = self._find_inherited_definition(cid)
                if ancestor_def:
                    definition = ancestor_def
                    inherited_from = ancestor_term

            # Получение лабораторных работ по topic_id
            lab_ids = self.loader.get_labs_by_topic(concept.get('topic_id', ''))

            recommendations.append({
                'concept_id': cid,
                'term': step['term'],
                'topic_id': concept.get('topic_id', ''),
                'reason': step['reason'],
                'definition': definition,
                'inherited_from': inherited_from,
                'examples': concept.get('examples', []),
                'lab_ids': lab_ids
            })

        return recommendations

    def _build_subgraph(self, node_ids: List[str]) -> Dict[str, List[str]]:
        """Построение подграфа зависимостей только для указанных узлов."""
        graph = {nid: [] for nid in node_ids}
        node_set = set(node_ids)

        for cid in node_ids:
            relations = self.loader.concepts_by_id[cid].get('relations', {})
            # Учитываем связи "надкласс" и "используется в" как зависимости
            for rel_type in ['надкласс', 'используется в']:
                targets = relations.get(rel_type, [])
                for target in targets:
                    if target in node_set:
                        graph[target].append(cid)  # target -> cid (target является пререквизитом для cid)

        return graph

    def _generate_reason(self, cid: str, graph: Dict[str, List[str]],
                         in_degree: Dict[str, int]) -> str:
        """Генерация пояснения, почему данный концепт включён в траекторию."""
        # Находим прямых потомков данного узла в подграфе пробелов
        dependents = graph.get(cid, [])
        valid_dependents = [d for d in dependents if d in in_degree and in_degree[d] > 0]

        if valid_dependents:
            dep_terms = []
            for dep_cid in valid_dependents[:3]:  # Ограничиваем количество для читаемости
                dep_concept = self.loader.concepts_by_id.get(dep_cid, {})
                dep_terms.append(dep_concept.get('term', dep_cid))

            deps_str = ', '.join(dep_terms)
            return f"Необходим для изучения: {deps_str}"

        return "Базовый концепт / Корневой элемент траектории"

    def _find_inherited_definition(self, cid: str, max_depth: int = 10) -> Tuple[Optional[str], Optional[str]]:
        """Поиск определения у ближайшего предка по связям 'надкласс'."""
        visited = set()
        current = cid
        depth = 0

        while depth < max_depth:
            if current in visited:
                break
            visited.add(current)

            concept = self.loader.concepts_by_id.get(current, {})
            if concept.get('definition'):
                return concept['definition'], concept.get('term')

            # Переход к родителям
            parents = concept.get('relations', {}).get('надкласс', [])
            if not parents:
                break

            # Берём первого валидного родителя
            next_parent = None
            for p in parents:
                if p in self.loader.concepts_by_id:
                    next_parent = p
                    break

            if not next_parent:
                break

            current = next_parent
            depth += 1

        return None, None

    @staticmethod
    def _insert_sorted(lst: List[str], item: str) -> None:
        """Вставка элемента в отсортированный список с сохранением порядка."""
        lo, hi = 0, len(lst)
        while lo < hi:
            mid = (lo + hi) // 2
            if lst[mid] < item:
                lo = mid + 1
            else:
                hi = mid
        lst.insert(lo, item)
