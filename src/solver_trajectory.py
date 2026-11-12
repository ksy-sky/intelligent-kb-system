"""
solver_trajectory.py — Решатель построения учебной траектории и рекомендаций (Сценарий 5).

Реализует:
  1. Топологическую сортировку графа пререквизитов вручную (алгоритм Кана)
     с рангом критичности каждого понятия (число понятий во ВСЕЙ базе
     знаний, транзитивно зависящих от данного — вычисляется собственным
     обходом в глубину, без внешних графовых библиотек).
  2. Формирование объяснения включения понятия в план в виде полного
     пути от понятия до целевого концепта (поиск в ширину вручную).
  3. Формирование контекстных рекомендаций по материалам, с эвристическим
     TF-IDF поиском похожих понятий как запасным механизмом для
     концептов с пустыми relations в базе знаний.
"""
import logging
from collections import deque
from typing import Dict, List, Set, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Типы отношений, формирующие иерархию зависимостей ("что нужно знать раньше").
# "надклассы" добавлен для устойчивости к расхождению в названии ключа,
# встречающемуся в части файлов базы знаний (glossary_T04.json, T06.json).
DEPENDENCY_RELATION_TYPES = ["надкласс", "надклассы", "используется в"]


class TrajectorySolver:
    #Решатель для построения индивидуальной учебной траектории и рекомендаций

    def __init__(self, loader):
        self.loader = loader
        # Кэш полного графа зависимостей БЗ: cid -> список понятий, для
        # которых cid является пререквизитом (рёбра "вперёд", cid -> dependents)
        self._forward_graph: Optional[Dict[str, List[str]]] = None


    #  Построение и кэширование полного графа зависимостей базы знаний

    def _get_full_graph(self) -> Dict[str, List[str]]:
        """
        Строит (при первом обращении) и кэширует граф зависимостей по
        ВСЕЙ базе знаний в виде словаря смежности: prerequisite_id -> [dependent_ids].
        Ребро target -> cid означает, что target является пререквизитом для cid.
        """
        if self._forward_graph is not None:
            return self._forward_graph

        graph: Dict[str, List[str]] = {cid: [] for cid in self.loader.concepts_by_id}

        for cid, concept in self.loader.concepts_by_id.items():
            relations = concept.get("relations", {})
            for rel_type in DEPENDENCY_RELATION_TYPES:
                for target in relations.get(rel_type, []):
                    target_clean = str(target).strip()
                    if target_clean in self.loader.concepts_by_id:
                        graph.setdefault(target_clean, []).append(cid)

        self._forward_graph = graph
        return graph

    def invalidate_cache(self) -> None:
        self._forward_graph = None

    def _count_descendants(self, cid: str, graph: Dict[str, List[str]]) -> int:
        """
        Считает число понятий, транзитивно зависящих от cid (т.е. всех
        потомков в графе зависимостей), собственным обходом в ширину.
        Используется для вычисления критичности.
        """
        visited: Set[str] = set()
        queue = deque(graph.get(cid, []))

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(graph.get(node, []))

        return len(visited)

    #  Построение учебной траектории (алгоритм Кана, вручную)

    def build_learning_plan(
        self,
        gap_ids: List[str],
        target_concept_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Построение упорядоченного плана изучения на основе множества пробелов.

        Args:
            gap_ids: список идентификаторов концептов, которые необходимо изучить
            target_concept_id: опциональный целевой концепт — если задан,
                объяснение включения каждого шага строится как путь до цели,
                иначе используется ранг критичности

        Returns:
            упорядоченный список словарей вида
            {'concept_id', 'term', 'topic_id', 'reason', 'criticality'}
        """
        if not gap_ids:
            return []

        valid_gaps = [gid for gid in gap_ids if gid in self.loader.concepts_by_id]
        if not valid_gaps:
            return []

        full_graph = self._get_full_graph()

        # Этап 1: построение локального подграфа только для вершин пробелов
        local_graph = self._build_subgraph(valid_gaps, full_graph)

        # Этап 2: вычисление входящих степеней
        in_degree = {cid: 0 for cid in valid_gaps}
        for src, neighbors in local_graph.items():
            for dst in neighbors:
                if dst in in_degree:
                    in_degree[dst] += 1

        queue = sorted([cid for cid, deg in in_degree.items() if deg == 0])

        # Критичность: сколько понятий во ВСЕЙ базе знаний транзитивно
        # зависят от данного концепта (считается по полному графу, не
        # по локальному подграфу пробелов)
        criticality = {cid: self._count_descendants(cid, full_graph) for cid in valid_gaps}

        trajectory = []

        # Этап 3: алгоритм Кана
        while queue:
            curr_cid = queue.pop(0)
            concept = self.loader.concepts_by_id[curr_cid]

            reason = self._generate_reason(
                curr_cid, local_graph, in_degree, full_graph, criticality, target_concept_id
            )

            trajectory.append({
                "concept_id": curr_cid,
                "term": concept.get("term", "Unknown"),
                "topic_id": concept.get("topic_id", ""),
                "reason": reason,
                "criticality": criticality.get(curr_cid, 0),
            })

            for neighbor in local_graph.get(curr_cid, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        self._insert_sorted(queue, neighbor)

        if len(trajectory) != len(valid_gaps):
            processed_ids = {t["concept_id"] for t in trajectory}
            cycle_nodes = set(valid_gaps) - processed_ids
            raise ValueError(f"Обнаружен цикл в пререквизитах среди концептов: {cycle_nodes}")

        return trajectory

    def _build_subgraph(
        self, node_ids: List[str], full_graph: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Построение локального подграфа зависимостей только для указанных
        узлов — фильтрует рёбра полного графа, оставляя только те, что
        идут между вершинами node_ids.
        """
        node_set = set(node_ids)
        graph = {nid: [] for nid in node_ids}

        for src in node_ids:
            for dst in full_graph.get(src, []):
                if dst in node_set:
                    graph[src].append(dst)

        return graph

    def _find_path_bfs(
        self, start: str, target: str, graph: Dict[str, List[str]]
    ) -> Optional[List[str]]:
        """
        Поиск кратчайшего пути от start до target в графе зависимостей
        собственной реализацией поиска в ширину (BFS), с восстановлением
        пути через словарь предшественников.
        """
        if start == target:
            return [start]

        visited = {start}
        queue = deque([start])
        predecessor: Dict[str, str] = {}

        while queue:
            node = queue.popleft()
            for neighbor in graph.get(node, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                predecessor[neighbor] = node
                if neighbor == target:
                    path = [target]
                    while path[-1] != start:
                        path.append(predecessor[path[-1]])
                    path.reverse()
                    return path
                queue.append(neighbor)

        return None  # пути не существует

    def _generate_reason(
        self,
        cid: str,
        local_graph: Dict[str, List[str]],
        in_degree: Dict[str, int],
        full_graph: Dict[str, List[str]],
        criticality: Dict[str, int],
        target_concept_id: Optional[str],
    ) -> str:
        """
        Формирует объяснение включения концепта в план.

        Если задан target_concept_id и до него существует путь — строится
        полная цепочка понятий от cid до цели (поиск в ширину вручную).
        Иначе используется ранг критичности (число зависимых понятий во
        всей базе знаний) и прямые потомки в локальном подграфе.
        """
        if target_concept_id and target_concept_id in full_graph:
            if cid == target_concept_id:
                return "Целевой концепт"
            path = self._find_path_bfs(cid, target_concept_id, full_graph)
            if path:
                path_terms = [
                    self.loader.concepts_by_id[p].get("term", p) for p in path
                ]
                return f"Путь к цели: {' → '.join(path_terms)}"

        dependents = local_graph.get(cid, [])
        valid_dependents = [d for d in dependents if d in in_degree and in_degree[d] > 0]
        crit = criticality.get(cid, 0)

        if valid_dependents:
            dep_terms = [
                self.loader.concepts_by_id.get(d, {}).get("term", d)
                for d in valid_dependents[:3]
            ]
            deps_str = ", ".join(dep_terms)
            crit_note = f" (критичность: от него зависит {crit} понятий)" if crit else ""
            return f"Необходим для изучения: {deps_str}{crit_note}"

        if crit > 0:
            return f"Базовое понятие дисциплины (от него зависит {crit} понятий во всей БЗ)"

        return "Базовый концепт / не имеет зависимых понятий в базе знаний"

    #  Формирование рекомендаций по материалам

    def generate_recommendations(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Формирование контекстных рекомендаций по учебным материалам для
        каждого шага плана. Если у концепта пустые relations, в качестве
        запасного механизма подключается TF-IDF поиск семантически
        похожих концептов по текстам определений.
        """
        recommendations = []

        for step in plan:
            cid = step["concept_id"]

            if cid not in self.loader.concepts_by_id:
                logger.warning(f"Concept {cid} not found in knowledge base, skipped")
                continue

            concept = self.loader.concepts_by_id[cid]

            definition = concept.get("definition", "")
            inherited_from = None
            if not definition:
                ancestor_def, ancestor_term = self._find_inherited_definition(cid)
                if ancestor_def:
                    definition = ancestor_def
                    inherited_from = ancestor_term

            topic_id = concept.get("topic_id", "")
            topic_title = self.loader.get_topics_index().get(topic_id, {}).get("title", "")

            related = self._resolve_all_relations(concept)

            similar_by_text: List[Dict[str, Any]] = []
            if not related:
                similar_by_text = self._find_similar_by_text(cid, top_n=3)

            lab_ids = self.loader.get_related_labs(cid)

            recommendations.append({
                "concept_id": cid,
                "term": step["term"],
                "topic_id": topic_id,
                "topic_title": topic_title,
                "reason": step["reason"],
                "criticality": step.get("criticality", 0),
                "definition": definition,
                "inherited_from": inherited_from,
                "examples": concept.get("examples", []),
                "related": related,
                "similar_by_text": similar_by_text,
                "lab_ids": lab_ids,
            })

        return recommendations

    def _resolve_all_relations(self, concept: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Разворачивает ВСЕ непустые типы связей концепта (а не только
        фиксированный список) в читаемые термины, если значение — ID
        существующего концепта, либо оставляет как текстовый литерал.
        """
        resolved: Dict[str, List[str]] = {}
        raw_relations = concept.get("relations", {})

        for rel_type, targets in raw_relations.items():
            if not targets:
                continue
            terms = []
            for t in targets:
                t_clean = str(t).strip()
                target_concept = self.loader.concepts_by_id.get(t_clean)
                terms.append(target_concept.get("term", t_clean) if target_concept else t_clean)
            resolved[rel_type] = terms

        return resolved

    def _find_similar_by_text(self, cid: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Запасной эвристический механизм: если у концепта нет явных связей
        в базе знаний, ищет top_n семантически похожих концептов по
        косинусному сходству TF-IDF векторов их определений.

        Это вспомогательная эвристика, не заменяющая основной
        детерминированный алгоритм (п. 2.5 ПЗ): она лишь компенсирует
        неполноту ручной разметки связей в части концептов базы знаний.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        target_concept = self.loader.concepts_by_id.get(cid, {})
        target_text = (target_concept.get("definition", "") + " "
                        + " ".join(target_concept.get("examples", [])))
        if not target_text.strip():
            return []

        candidate_ids = []
        candidate_texts = []
        for other_cid, other_concept in self.loader.concepts_by_id.items():
            if other_cid == cid:
                continue
            text = (other_concept.get("definition", "") + " "
                    + " ".join(other_concept.get("examples", [])))
            if text.strip():
                candidate_ids.append(other_cid)
                candidate_texts.append(text)

        if not candidate_texts:
            return []

        vectorizer = TfidfVectorizer()
        try:
            matrix = vectorizer.fit_transform([target_text] + candidate_texts)
        except ValueError:
            return []

        similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

        ranked = sorted(
            zip(candidate_ids, similarities), key=lambda x: x[1], reverse=True
        )

        results = []
        for other_cid, score in ranked[:top_n]:
            if score <= 0.0:
                continue
            other_concept = self.loader.concepts_by_id[other_cid]
            results.append({
                "concept_id": other_cid,
                "term": other_concept.get("term", other_cid),
                "similarity": round(float(score), 2),
            })

        return results

    def _find_inherited_definition(
        self, cid: str, max_depth: int = 10
    ) -> Tuple[Optional[str], Optional[str]]:
        #Поиск определения у ближайшего предка по связям 'надкласс'/'надклассы'.
        visited = set()
        current = cid
        depth = 0

        while depth < max_depth:
            if current in visited:
                break
            visited.add(current)

            concept = self.loader.concepts_by_id.get(current, {})
            if concept.get("definition"):
                return concept["definition"], concept.get("term")

            relations = concept.get("relations", {})
            parents = relations.get("надкласс", []) + relations.get("надклассы", [])
            if not parents:
                break

            next_parent = None
            for p in parents:
                p_clean = str(p).strip()
                if p_clean in self.loader.concepts_by_id:
                    next_parent = p_clean
                    break

            if not next_parent:
                break

            current = next_parent
            depth += 1

        return None, None

    @staticmethod
    def _insert_sorted(lst: List[str], item: str) -> None:
        lo, hi = 0, len(lst)
        while lo < hi:
            mid = (lo + hi) // 2
            if lst[mid] < item:
                lo = mid + 1
            else:
                hi = mid
        lst.insert(lo, item)
