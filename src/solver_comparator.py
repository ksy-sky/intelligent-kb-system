"""
solver_comparator.py — Решатель семантического сравнения концептов через поиск
ближайшего общего предка (LCA — Lowest Common Ancestor) в иерархии онтологии.
Реализует Сценарий 6.

Алгоритм:
1. Для каждого из двух концептов строится множество предков (через связи «надкласс»)
   с сохранением глубины (расстояния от концепта до предка).
2. Находится пересечение множеств предков — общие предки.
3. Из общих предков выбирается тот, у которого суммарное расстояние до обоих
   концептов минимально — это и есть LCA.
4. Вычисляется мера семантической близости Ву-Палмера (Wu-Palmer similarity):
   sim(c1, c2) = 2 * depth(LCA) / (depth(c1) + depth(c2))

Граничные случаи:
- Один концепт является предком другого → LCA = сам предок.
- Концепты идентичны → LCA = сам концепт, similarity = 1.0.
- Общие предки отсутствуют → status='no_common_ancestor'.
- Один или оба концепта не найдены → status='error' + список похожих.
- Циклы в иерархии → защита через visited-set.
"""
import difflib
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

REL_SUPERCLASS = "надкласс"


class ComparatorSolver:
    """Решатель семантического сравнения двух концептов через LCA."""

    def __init__(self, loader, similar_limit: int = 5):
        """
        Args:
            loader: экземпляр KnowledgeBaseLoader
            similar_limit: количество похожих концептов в подсказках при ошибке
        """
        self.loader = loader
        self.similar_limit = similar_limit

    @property
    def _concepts(self) -> Dict[str, dict]:
        return self.loader.concepts_by_id

    def _term(self, cid: str) -> str:
        return self._concepts.get(cid, {}).get("term", cid)


    def resolve_concept(self, query: str) -> Optional[str]:
        """Определение concept_id по ID или термину (без учёта регистра)."""
        query = (query or "").strip()
        if not query:
            return None
        if query in self._concepts:
            return query
        upper = query.upper()
        if upper in self._concepts:
            return upper
        low = query.lower()
        for cid, concept in self._concepts.items():
            if str(concept.get("term", "")).lower() == low:
                return cid
        return None

    def find_similar(self, query: str) -> List[Dict[str, str]]:
        """Похожие концепты для подсказки при ошибке."""
        query = (query or "").strip().lower()
        if not query:
            return []
        by_term: Dict[str, str] = {}
        for cid, concept in self._concepts.items():
            term = str(concept.get("term", "")).lower()
            if term:
                by_term.setdefault(term, cid)
        found: List[str] = []
        for t in difflib.get_close_matches(
            query, list(by_term), n=self.similar_limit, cutoff=0.5
        ):
            found.append(by_term[t])
        return [
            {"concept_id": cid, "term": self._term(cid)} for cid in found[: self.similar_limit]
        ]


    def get_ancestors_with_depth(self, cid: str) -> Dict[str, int]:
        """
        BFS вверх по связям «надкласс».
        Возвращает {предок_id: глубина}.
        Глубина самого концепта = 0, его прямой надкласс = 1 и т.д.
        """
        # ВАЖНО: добавляем сам концепт с глубиной 0, чтобы он мог быть LCA
        ancestors: Dict[str, int] = {cid: 0}  
        queue: deque = deque([(cid, 0)])
        visited: Set[str] = {cid}
        while queue:
            current, depth = queue.popleft()
            for parent in self._superclass_targets(current):
                if parent not in visited:
                    visited.add(parent)
                    ancestors[parent] = depth + 1
                    queue.append((parent, depth + 1))
        return ancestors
    
    def get_depth(self, cid: str) -> int:
        """
        Глубина концепта в иерархии.
        ВАЖНО: Корень (без надклассов) имеет глубину 1 (стандарт меры Ву-Палмера),
        чтобы избежать нулевой семантической близости.
        """
        depth = 1  # ← Изменено с 0 на 1
        visited: Set[str] = set()
        current = cid
        while current and current not in visited:
            visited.add(current)
            parents = self._superclass_targets(current)
            if not parents:
                break
            current = parents[0]
            depth += 1
        return depth

    
    def compare(self, query1: str, query2: str) -> Dict[str, Any]:
        """
        Семантическое сравнение двух концептов.
        Args:
            query1, query2: ID или термин концепта
        Returns:
            словарь с результатом сравнения (status, lca, similarity, ...)
        """
        id1 = self.resolve_concept(query1)
        id2 = self.resolve_concept(query2)

        missing = []
        if id1 is None:
            missing.append({"query": query1, "similar": self.find_similar(query1)})
        if id2 is None:
            missing.append({"query": query2, "similar": self.find_similar(query2)})
        if missing:
            msg_parts = []
            for m in missing:
                msg = f"Концепт «{m['query']}» не найден."
                if m["similar"]:
                    msg += " Возможно, вы имели в виду: " + ", ".join(
                        f"«{s['term']}»" for s in m["similar"]
                    )
                msg_parts.append(msg)
            return {
                "status": "error",
                "message": "; ".join(msg_parts),
                "missing": missing,
            }

        if id1 == id2:
            depth = self.get_depth(id1)
            return {
                "status": "identical",
                "concept_id_1": id1,
                "term_1": self._term(id1),
                "concept_id_2": id2,
                "term_2": self._term(id2),
                "lca_id": id1,
                "lca_term": self._term(id1),
                "distance_1": 0,
                "distance_2": 0,
                "depth_lca": depth,
                "semantic_similarity": 1.0,
                "message": f"«{self._term(id1)}» — это один и тот же концепт.",
            }

        ancestors1 = self.get_ancestors_with_depth(id1)
        ancestors2 = self.get_ancestors_with_depth(id2)

        common = set(ancestors1.keys()) & set(ancestors2.keys())

        if not common:
            return {
                "status": "no_common_ancestor",
                "concept_id_1": id1,
                "term_1": self._term(id1),
                "concept_id_2": id2,
                "term_2": self._term(id2),
                "message": (
                    f"У концептов «{self._term(id1)}» и «{self._term(id2)}» "
                    "не найдено общих предков в иерархии."
                ),
            }

        lca_id = min(common, key=lambda a: ancestors1[a] + ancestors2[a])
        dist1 = ancestors1[lca_id]
        dist2 = ancestors2[lca_id]

        depth_lca = self.get_depth(lca_id)
        depth1 = depth_lca + dist1
        depth2 = depth_lca + dist2
        similarity = (2 * depth_lca) / (depth1 + depth2) if (depth1 + depth2) > 0 else 0.0

        relation = None
        if id1 in ancestors2:
            relation = f"«{self._term(id1)}» является надклассом для «{self._term(id2)}»"
        elif id2 in ancestors1:
            relation = f"«{self._term(id2)}» является надклассом для «{self._term(id1)}»"

        common_sorted = sorted(
            common, key=lambda a: (ancestors1[a] + ancestors2[a], a)
        )

        return {
            "status": "success",
            "concept_id_1": id1,
            "term_1": self._term(id1),
            "concept_id_2": id2,
            "term_2": self._term(id2),
            "lca_id": lca_id,
            "lca_term": self._term(lca_id),
            "distance_1": dist1,
            "distance_2": dist2,
            "depth_lca": depth_lca,
            "semantic_similarity": round(similarity, 3),
            "relation": relation,
            "common_ancestors": [
                {
                    "concept_id": a,
                    "term": self._term(a),
                    "distance_to_c1": ancestors1[a],
                    "distance_to_c2": ancestors2[a],
                }
                for a in common_sorted
            ],
            "message": (
                f"Ближайший общий предок (LCA) для «{self._term(id1)}» и "
                f"«{self._term(id2)}»: «{self._term(lca_id)}».\n"
                f"Семантическая близость (Wu-Palmer): {similarity:.3f}."
            ),
        }

    def compare_by_id(self, id1: str, id2: str) -> Dict[str, Any]:
        """Удобный алиас для вызова по ID (без поиска по термину)."""
        return self.compare(id1, id2)
