"""
solver_comparator.py — Решатель «Чем отличаются A и B?» (Сценарий 6).

Роль в системе
-------------
Студент часто путает близкие понятия (жадный/ленивый квантификатор, RDF/RDFS, данные/информация).
Компаратор отвечает: к какому общему роду относятся два понятия, чем каждое отличается от
другого и какие характеристики общие, а какие собственные. Это «род и видовое отличие»:
общий предок (LCA) задаёт род, определение и характеристики каждого понятия — отличие.

Сравнительная карточка
----------------------
1. Тип родства (relationship): совпадают / надкласс–подкласс / «соседи» / «двоюродные» /
   часть–целое / общее целое / связаны по смыслу / один раздел / не связаны.
2. LCA, мера Ву–Палмера, пути от предка до каждого понятия (path_1, path_2) и общий путь (path).
3. Род (genus): определение общего предка — то, что объединяет понятия по природе.
4. Матрица характеристик (characteristics): строки — виды характеристик из связей БЗ
   («структура», «синтаксис», «свойства», «преимущества»…), статус каждой строки:
   common / partly / different / only_1 / only_2.
5. Унаследованные характеристики (inherited): то, что оба понятия получают от общего предка.
6. Горизонтальные связи (horizontal): общие связанные понятия, прямые связи и цепочка связей —
   запасной вариант, когда таксономического родства нет.
7. Явные противопоставления («противопоставляется»), порядок изучения, лабораторные работы.
8. Итоговая близость 0..1 = Ву–Палмер + до 30% оставшегося за общие горизонтальные связи
   (связи только повышают близость, но не снижают её).

Единый граф иерархии
--------------------
Связь «надкласс» задана только у части понятий (лабораторные L02/L04/L05). В теории
(T01–T07) иерархия записана «сверху вниз»: у родителя перечислены подклассы
(«разбиение*», «семейство подклассов», «виды») или части («составные части», «состав», …).
Граф строится из двух видов рёбер: is-a («надкласс» + инверсия «разбиение*») и part
(инверсия «составные части» и аналогов). Основной LCA и Ву–Палмер считаются по is-a. Если общего
is-a-предка нет, используется объединённый граф (is-a + part): «общее целое». Рёбра, создающие
цикл, пропускаются (граф всегда ацикличен).

Граничные случаи
----------------
* Понятия не найдены → status='error' + подсказки (опечатки).
* Термин неоднозначен (омонимы теории и лабораторных) → status='error', code='ambiguous'.
* Одинаковые понятия → status='identical' (уникальных характеристик нет).
* Прямой надкласс → предком признаётся сам надкласс.
* Нет общего предка → сообщение об отсутствии таксономического родства, сравнение по
  горизонтальным связям; карточка всё равно содержит определения и характеристики.
"""
import difflib
import logging
import re
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REL_SUPERCLASS = "надкласс"

# Ключи relations, у которых перечислены ПОДКЛАССЫ (родитель → дети). Плюс префикс «разбиение».
ISA_CHILD_KEYS = {"семейство подклассов", "виды", "надклассы"}
ISA_CHILD_PREFIX = "разбиение"
# Ключи, у которых перечислены ЧАСТИ (целое → части)
PART_CHILD_KEYS = {
    "составные части", "состав", "включает", "основные компоненты",
    "основные элементы", "элементы",
}
CONTRAST_KEYS = {"противопоставляется"}
# Ключи иерархии (is-a и часть–целое); остальные связи — «горизонтальные»
STRUCTURAL_KEYS = {REL_SUPERCLASS} | ISA_CHILD_KEYS | PART_CHILD_KEYS
# Не характеристики понятия: иерархия и противопоставление (оно показывается отдельно)
HIERARCHY_KEYS = STRUCTURAL_KEYS | CONTRAST_KEYS
# «пояснение» — свободный текст: показывается отдельно, в матрицу характеристик не входит
FREE_TEXT_KEYS = {"пояснение"}
MAX_INHERITED = 8

KIND_ISA = "isa"
KIND_PART = "part"
KIND_LABEL = {KIND_ISA: "надкласс", KIND_PART: "часть целого"}

# Составляющие итоговой близости
CONTEXT_BONUS = 0.3             # доля оставшегося до 1.0, которую могут добавить общие связи
PART_LAYER_PENALTY = 0.85       # Ву–Палмер по объединённому графу (is-a+part) весит меньше

LEVELS = (
    (0.90, "практически совпадают"),
    (0.60, "очень близкие"),
    (0.35, "родственные"),
    (0.08, "слабо связаны"),
    (0.0, "далёкие"),
)


def _level(score: float) -> str:
    for threshold, label in LEVELS:
        if score >= threshold:
            return label
    return LEVELS[-1][1]


class ComparatorSolver:
    """Решатель сравнения понятий: сходство, различие, LCA, порядок изучения."""

    def __init__(self, loader, similar_limit: int = 5):
        """
        Args:
            loader: экземпляр KnowledgeBaseLoader (уже вызван load())
            similar_limit: сколько подсказок показывать при опечатке
        """
        self.loader = loader
        self.similar_limit = similar_limit
        self._graph_ready = False
        self._parents: Dict[str, Dict[str, str]] = {}      # ребёнок -> {родитель: вид ребра}
        self._children: Dict[str, Dict[str, str]] = {}     # родитель -> {ребёнок: вид ребра}
        self._neighbors: Dict[str, Set[str]] = {}          # горизонтальные ID-связи, в обе стороны
        self._edge_labels: Dict[Tuple[str, str], str] = {}  # (a, b) -> ключ relations у a
        self._up_cache: Dict[Tuple[str, str], Dict[str, Tuple[int, Optional[str]]]] = {}
        self.skipped_edges: List[Tuple[str, str, str]] = []
        self._homonyms: Set[str] = set()

    # ------------------------------------------------------------------ доступ к БЗ
    @property
    def _concepts(self) -> Dict[str, dict]:
        return self.loader.concepts_by_id

    def _term(self, cid: str) -> str:
        return self._concepts.get(cid, {}).get("term", cid)

    def _label(self, cid: str) -> str:
        """«термин»; для омонимов добавляется ID, чтобы их можно было различить."""
        term = self._term(cid)
        return f"«{term}» [{cid}]" if term.lower() in self._homonyms else f"«{term}»"

    def _topic_title(self, cid: str) -> str:
        tid = self._concepts.get(cid, {}).get("topic_id", "")
        topics = getattr(self.loader, "topics_index", {}) or {}
        return (topics.get(tid) or {}).get("title", "")

    # ------------------------------------------------------------------ построение графа
    def _ensure_graph(self) -> None:
        """Граф строится лениво (после load()) и один раз."""
        if self._graph_ready:
            return
        self._parents = {cid: {} for cid in self._concepts}
        self._children = {cid: {} for cid in self._concepts}
        self._neighbors = {cid: set() for cid in self._concepts}
        self._edge_labels.clear()
        self._up_cache.clear()
        self.skipped_edges = []

        explicit: List[Tuple[str, str, str]] = []   # (ребёнок, родитель, вид)
        inferred_isa: List[Tuple[str, str, str]] = []
        inferred_part: List[Tuple[str, str, str]] = []

        for cid, concept in self._concepts.items():
            for key, targets in (concept.get("relations") or {}).items():
                k = str(key).strip().lower()
                for raw in targets:
                    t = str(raw).strip()
                    if t not in self._concepts or t == cid:
                        continue
                    if not self._is_structural_key(k):          # горизонтальная связь
                        self._neighbors[cid].add(t)
                        self._neighbors[t].add(cid)
                    self._edge_labels.setdefault((cid, t), key)
                    if k == REL_SUPERCLASS:
                        explicit.append((cid, t, KIND_ISA))
                    elif k in ISA_CHILD_KEYS or k.startswith(ISA_CHILD_PREFIX):
                        inferred_isa.append((t, cid, KIND_ISA))
                    elif k in PART_CHILD_KEYS:
                        inferred_part.append((t, cid, KIND_PART))

        # Порядок важен: явные is-a → выведенные is-a → части. Первый вид ребра побеждает.
        for child, parent, kind in explicit + inferred_isa + inferred_part:
            self._add_edge(child, parent, kind)

        counts: Dict[str, int] = {}
        for c in self._concepts.values():
            t = str(c.get("term", "")).lower()
            counts[t] = counts.get(t, 0) + 1
        self._homonyms = {t for t, n in counts.items() if n > 1}
        self._graph_ready = True

    def _add_edge(self, child: str, parent: str, kind: str) -> None:
        if parent in self._parents[child]:
            return                                    # дубликат
        if child in self._reach_up(parent):           # parent уже ниже child (в т.ч. обратное ребро) → цикл
            self.skipped_edges.append((child, parent, kind))
            logger.warning("Ребро %s → %s (%s) пропущено: образует цикл", child, parent, kind)
            return
        self._parents[child][parent] = kind
        self._children[parent][child] = kind

    def _reach_up(self, start: str) -> Set[str]:
        """Все предки (любых видов) в текущем графе, включая сам start."""
        seen, stack = {start}, [start]
        while stack:
            for p in self._parents.get(stack.pop(), {}):
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    # ------------------------------------------------------------------ поиск понятий
    def _resolve_all(self, query: str) -> List[str]:
        """Все concept_id, подходящие под запрос (ID без учёта регистра либо термин)."""
        query = (query or "").strip()
        if not query:
            return []
        if query in self._concepts:
            return [query]
        if query.upper() in self._concepts:
            return [query.upper()]
        low = query.lower()
        return [cid for cid, c in self._concepts.items() if str(c.get("term", "")).lower() == low]

    def resolve_concept(self, query: str) -> Optional[str]:
        """concept_id по ID или термину; None, если не найден. При омонимах — первый."""
        found = self._resolve_all(query)
        return found[0] if found else None

    def find_similar(self, query: str) -> List[Dict[str, str]]:
        """Похожие по написанию термины — подсказка при опечатке."""
        query = (query or "").strip().lower()
        if not query:
            return []
        by_term: Dict[str, str] = {}
        for cid, concept in self._concepts.items():
            term = str(concept.get("term", "")).lower()
            if term:
                by_term.setdefault(term, cid)
        found = difflib.get_close_matches(query, list(by_term), n=self.similar_limit, cutoff=0.5)
        return [{"concept_id": by_term[t], "term": self._term(by_term[t])} for t in found]

    # ------------------------------------------------------------------ иерархия
    def _superclass_targets(self, cid: str) -> List[str]:
        """Прямые надклассы (is-a) понятия. Оставлено для обратной совместимости."""
        self._ensure_graph()
        return [p for p, k in self._parents.get(cid, {}).items() if k == KIND_ISA]

    def _layer_parents(self, cid: str, layer: str) -> List[str]:
        if layer == "isa":
            return [p for p, k in self._parents.get(cid, {}).items() if k == KIND_ISA]
        return list(self._parents.get(cid, {}))

    def _up(self, cid: str, layer: str = "isa") -> Dict[str, Tuple[int, Optional[str]]]:
        """
        BFS вверх. Возвращает {предок: (расстояние, через_кого)}; сам cid имеет расстояние 0.
        layer: 'isa' — только «надкласс»; 'all' — is-a + части.
        """
        self._ensure_graph()
        key = (layer, cid)
        if key in self._up_cache:
            return self._up_cache[key]
        info: Dict[str, Tuple[int, Optional[str]]] = {cid: (0, None)}
        queue: deque = deque([cid])
        while queue:
            cur = queue.popleft()
            dist = info[cur][0]
            for parent in self._layer_parents(cur, layer):
                if parent not in info:
                    info[parent] = (dist + 1, cur)
                    queue.append(parent)
        self._up_cache[key] = info
        return info

    def get_ancestors_with_depth(self, cid: str, layer: str = "isa") -> Dict[str, int]:
        """{предок_id: расстояние}; сам концепт — 0, прямой надкласс — 1 и т.д."""
        return {a: d for a, (d, _) in self._up(cid, layer).items()}

    def get_depth(self, cid: str, layer: str = "isa") -> int:
        """Глубина: корень (нет надклассов) = 1; при нескольких родителях — кратчайший путь к корню."""
        info = self._up(cid, layer)
        return min(d for a, (d, _) in info.items() if not self._layer_parents(a, layer)) + 1

    def _path_up(self, cid: str, anc: str, layer: str) -> List[str]:
        """Цепочка [cid, …, anc] по кратчайшему пути вверх."""
        info = self._up(cid, layer)
        path, cur = [anc], anc
        while cur != cid:
            cur = info[cur][1]
            path.append(cur)
        return path[::-1]

    def _lca(self, id1: str, id2: str, layer: str) -> Optional[Dict[str, Any]]:
        """
        Нижний общий предок в заданном слое. «Нижний» = самый глубокий; при равенстве —
        с меньшей суммой расстояний. Для дерева совпадает с классическим LCA.
        """
        up1, up2 = self._up(id1, layer), self._up(id2, layer)
        common = set(up1) & set(up2)
        if not common:
            return None
        ordered = sorted(common, key=lambda a: (-self.get_depth(a, layer), up1[a][0] + up2[a][0], a))
        lca = ordered[0]
        d1, d2, dl = up1[lca][0], up2[lca][0], self.get_depth(lca, layer)
        return {
            "lca": lca, "dist1": d1, "dist2": d2, "depth": dl,
            "wu_palmer": (2 * dl) / (2 * dl + d1 + d2),
            "common": ordered, "layer": layer,
        }

    # ------------------------------------------------------------------ составляющие близости
    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    def _hierarchy_score(self, id1: str, id2: str) -> Tuple[float, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """(оценка, is-a-LCA, LCA по объединённому графу — только если is-a-LCA нет)."""
        isa = self._lca(id1, id2, "isa")
        if isa:
            return isa["wu_palmer"], isa, None
        union = self._lca(id1, id2, "all")
        if union:
            return union["wu_palmer"] * PART_LAYER_PENALTY, None, union
        return 0.0, None, None

    def _context_score(self, id1: str, id2: str) -> float:
        """
        Общие горизонтальные связи (Жаккар по замкнутым окрестностям). Общие предки из окрестностей
        исключаются: они уже учтены иерархией, и считать их дважды нельзя.
        """
        shared_anc = set(self._up(id1, "all")) & set(self._up(id2, "all")) - {id1, id2}
        n1 = (self._neighbors[id1] - shared_anc) | {id1}
        n2 = (self._neighbors[id2] - shared_anc) | {id2}
        if len(n1) == 1 and len(n2) == 1:
            return 0.0
        return self._jaccard(n1, n2)

    def _score(self, id1: str, id2: str) -> Tuple[float, Dict[str, float]]:
        h, _, _ = self._hierarchy_score(id1, id2)
        ctx = self._context_score(id1, id2)
        total = h + CONTEXT_BONUS * ctx * (1 - h)
        return round(min(total, 1.0), 3), {"hierarchy": round(h, 3), "context": round(ctx, 3)}

    # ------------------------------------------------------------------ вспомогательное для карточки
    def _direct_links(self, id1: str, id2: str, horizontal_only: bool = False) -> List[Dict[str, str]]:
        links = []
        for a, b in ((id1, id2), (id2, id1)):
            key = self._edge_labels.get((a, b))
            if key is not None and not (horizontal_only and self._is_structural_key(key)):
                links.append({
                    "from_id": a, "from_term": self._term(a), "relation": key,
                    "to_id": b, "to_term": self._term(b),
                })
        return links

    def _shortest_link_path(self, id1: str, id2: str, max_len: int = 3) -> Optional[List[str]]:
        """Кратчайшая цепочка по любым связям (в обе стороны), не длиннее max_len рёбер."""
        prev = {id1: None}
        queue: deque = deque([(id1, 0)])
        while queue:
            cur, d = queue.popleft()
            if cur == id2:
                path = [cur]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                return path[::-1]
            if d == max_len:
                continue
            for nb in sorted(self._neighbors[cur]):
                if nb not in prev:
                    prev[nb] = cur
                    queue.append((nb, d + 1))
        return None

    @staticmethod
    def _is_structural_key(key: str) -> bool:
        k = str(key).strip().lower()
        return k in STRUCTURAL_KEYS or k.startswith(ISA_CHILD_PREFIX)

    @classmethod
    def _is_hierarchy_key(cls, key: str) -> bool:
        return cls._is_structural_key(key) or str(key).strip().lower() in CONTRAST_KEYS

    def _characteristics(self, cid: str) -> Dict[str, List[str]]:
        """
        Характеристики понятия: {вид: [значения]} из его связей, кроме иерархических и
        свободного текста. Значение-ID заменяется термином, текстовое остаётся как есть.
        """
        out: Dict[str, List[str]] = {}
        for key, targets in (self._concepts[cid].get("relations") or {}).items():
            if self._is_hierarchy_key(key) or str(key).strip().lower() in FREE_TEXT_KEYS:
                continue
            values = [self._term(t) if t in self._concepts else str(t) for t in targets]
            if values:
                out[key] = values
        return out

    def _characteristics_matrix(self, id1: str, id2: str) -> List[Dict[str, Any]]:
        """Матрица общих и уникальных характеристик: по строке на вид характеристики."""
        c1, c2 = self._characteristics(id1), self._characteristics(id2)
        rows = []
        for key in list(c1) + [k for k in c2 if k not in c1]:
            v1, v2 = c1.get(key, []), c2.get(key, [])
            shared = [v for v in v1 if v in v2]
            if v1 and v2:
                status = "common" if set(v1) == set(v2) else ("partly" if shared else "different")
            else:
                status = "only_1" if v1 else "only_2"
            rows.append({"name": key, "values_1": v1, "values_2": v2, "shared": shared, "status": status})
        return rows

    def _inherited(self, common_ancestors: List[str]) -> List[Dict[str, Any]]:
        """Характеристики общих предков (от нижнего к верхнему): оба понятия наследуют их."""
        rows = []
        for anc in common_ancestors:
            for key, values in self._characteristics(anc).items():
                rows.append({"from_id": anc, "from_term": self._term(anc), "name": key, "values": values})
        return rows[:MAX_INHERITED]

    def _terms(self, ids: List[str]) -> List[str]:
        return [self._term(i) for i in ids]

    def _labs(self, cid: str) -> List[str]:
        getter = getattr(self.loader, "get_related_labs", None)
        labs: Set[str] = set(getter(cid) or []) if getter else set()
        tid = str(self._concepts.get(cid, {}).get("topic_id", ""))
        if tid.startswith("L"):
            labs.add(tid)
        return sorted(labs)

    def _profile(self, cid: str, other: str, lca: Optional[str]) -> Dict[str, Any]:
        """Описание одного из сравниваемых понятий для блока «различия»."""
        c = self._concepts[cid]
        parents = [p for p, k in self._parents[cid].items() if k == KIND_ISA]
        subclasses = [ch for ch, k in self._children[cid].items() if k == KIND_ISA]
        parts = [ch for ch, k in self._children[cid].items() if k == KIND_PART]
        branch: List[str] = []
        if lca and lca != cid:
            branch = self._terms(self._path_up(cid, lca, "isa"))   # от понятия вверх до LCA
        return {
            "concept_id": cid,
            "term": self._term(cid),
            "topic_id": c.get("topic_id"),
            "topic_title": self._topic_title(cid),
            "definition": c.get("definition", ""),
            "examples": list(c.get("examples") or [])[:2],
            "superclasses": self._terms(parents),
            "subclasses": self._terms(subclasses)[:8],
            "parts": self._terms(parts)[:8],
            "explanation": " ".join((c.get("relations") or {}).get("пояснение", [])),
            "branch_to_lca": branch,
        }

    # ------------------------------------------------------------------ ошибки поиска
    def _lookup_error(self, queries: List[str], resolved: List[List[str]]) -> Optional[Dict[str, Any]]:
        problems, missing, ambiguous = [], [], []
        for q, ids in zip(queries, resolved):
            if not ids:
                similar = self.find_similar(q)
                missing.append({"query": q, "similar": similar})
                msg = f"Концепт «{q}» не найден."
                if similar:
                    msg += " Возможно, вы имели в виду: " + ", ".join(f"«{s['term']}»" for s in similar)
                problems.append(msg)
            elif len(ids) > 1:
                ambiguous.append({"query": q, "candidates": [
                    {"concept_id": i, "topic_id": self._concepts[i].get("topic_id")} for i in ids]})
                problems.append(f"Термину «{q}» соответствует несколько концептов: " + ", ".join(ids)
                                + ". Уточните ID.")
        if not problems:
            return None
        return {
            "status": "error",
            "code": "ambiguous" if ambiguous and not missing else "not_found",
            "message": " ".join(problems),
            "missing": missing,
            "ambiguous": ambiguous,
        }

    # ------------------------------------------------------------------ сравнение
    def compare(self, query1: str, query2: str) -> Dict[str, Any]:
        """
        Сравнительная карточка двух понятий.

        Args:
            query1, query2: ID или термин
        Returns:
            dict со status ('success' | 'identical' | 'error') и полями карточки (см. docstring модуля).
        """
        self._ensure_graph()
        resolved = [self._resolve_all(query1), self._resolve_all(query2)]
        err = self._lookup_error([query1, query2], resolved)
        if err:
            return err
        id1, id2 = resolved[0][0], resolved[1][0]
        t1, t2 = self._term(id1), self._term(id2)

        if id1 == id2:
            depth = self.get_depth(id1)
            return {
                "status": "identical", "relationship": "identical",
                "concept_id_1": id1, "term_1": t1, "concept_id_2": id2, "term_2": t2,
                "lca_id": id1, "lca_term": t1, "distance_1": 0, "distance_2": 0, "depth_lca": depth,
                "wu_palmer": 1.0, "semantic_similarity": 1.0, "similarity_level": _level(1.0),
                "message": f"{self._label(id1)} — это один и тот же концепт.",
            }

        score, parts = self._score(id1, id2)
        _, isa, union = self._hierarchy_score(id1, id2)
        lca_info = isa or union
        relationship, headline, path = self._classify(id1, id2, isa, union)

        lca_id = lca_info["lca"] if lca_info else None
        direct = self._direct_links(id1, id2)
        contrast = [l for l in direct if str(l["relation"]).lower() in CONTRAST_KEYS]
        # общие предки уже показаны как род/путь — в горизонтальных связях их не дублируем
        shared_nb = sorted((self._neighbors[id1] & self._neighbors[id2]) - {id1, id2} - set(
            (lca_info or {}).get("common", [])))
        link_path = self._shortest_link_path(id1, id2) if relationship == "linked" else None

        same_topic = self._concepts[id1].get("topic_id") == self._concepts[id2].get("topic_id")
        labs = sorted(set(self._labs(id1)) | set(self._labs(id2)))
        order = self._study_order(id1, id2, lca_id, relationship)
        matrix = self._characteristics_matrix(id1, id2)
        common_anc = lca_info["common"] if lca_info else []

        result: Dict[str, Any] = {
            "status": "success",
            "relationship": relationship,
            "concept_id_1": id1, "term_1": t1, "concept_id_2": id2, "term_2": t2,
            "lca_id": lca_id,
            "lca_term": self._term(lca_id) if lca_id else None,
            "lca_layer": lca_info["layer"] if lca_info else None,
            "distance_1": lca_info["dist1"] if lca_info else None,
            "distance_2": lca_info["dist2"] if lca_info else None,
            "depth_lca": lca_info["depth"] if lca_info else None,
            "wu_palmer": round(isa["wu_palmer"], 3) if isa else 0.0,
            "semantic_similarity": score,
            "similarity_level": _level(score),
            "similarity_parts": parts,
            "relation": headline if relationship in ("ancestor", "descendant", "part_whole") else None,
            "path": path,
            "path_text": self._path_text(path),
            "path_1": self._path_down(lca_id, id1, lca_info["layer"]) if lca_info else [],
            "path_2": self._path_down(lca_id, id2, lca_info["layer"]) if lca_info else [],
            "genus": ({"concept_id": lca_id, "term": self._term(lca_id),
                       "definition": self._concepts[lca_id].get("definition", "")} if isa else None),
            "common_ancestors": [
                {"concept_id": a, "term": self._term(a),
                 "distance_to_c1": self._up(id1, lca_info["layer"])[a][0],
                 "distance_to_c2": self._up(id2, lca_info["layer"])[a][0]}
                for a in common_anc
            ],
            "characteristics": matrix,
            "inherited": self._inherited(common_anc) if isa else [],
            "common": {
                "same_topic": same_topic,
                "topic_id": self._concepts[id1].get("topic_id") if same_topic else None,
                "shared_characteristics": [{"name": r["name"], "values": r["shared"]} for r in matrix if r["shared"]],
                "linked_concepts": [{"concept_id": n, "term": self._term(n)} for n in shared_nb[:8]],
            },
            "horizontal": {
                "direct_links": self._direct_links(id1, id2, horizontal_only=True),
                "shared_links": [{"concept_id": n, "term": self._term(n)} for n in shared_nb[:8]],
                "link_path": [{"concept_id": c, "term": self._term(c)} for c in link_path] if link_path else [],
            },
            "differences": {
                "concept_1": self._profile(id1, id2, lca_id if isa else None),
                "concept_2": self._profile(id2, id1, lca_id if isa else None),
            },
            "direct_links": direct,
            "contrasted": bool(contrast),
            "study": {"order": order, "labs": labs},
        }
        result["tip"] = self._tip(result)
        result["message"] = self._message(result, headline)
        return result

    def _path_down(self, lca: str, cid: str, layer: str) -> List[Dict[str, str]]:
        """Путь от общего предка вниз до понятия: [LCA, …, cid]."""
        return [{"concept_id": c, "term": self._term(c)} for c in self._path_up(cid, lca, layer)[::-1]]

    # --- классификация родства -------------------------------------------------------------
    def _classify(self, id1, id2, isa, union) -> Tuple[str, str, List[Dict[str, str]]]:
        """(тип родства, фраза-вердикт, путь по понятиям)."""
        l1, l2 = self._label(id1), self._label(id2)
        if isa:
            lca, d1, d2 = isa["lca"], isa["dist1"], isa["dist2"]
            path = self._build_path(id1, id2, lca, "isa")
            if lca == id1:
                return "ancestor", f"{l1} — надкласс для {l2}: {l2} это частный случай {l1}", path
            if lca == id2:
                return "descendant", f"{l2} — надкласс для {l1}: {l1} это частный случай {l2}", path
            if d1 == 1 and d2 == 1:
                return "siblings", f"{l1} и {l2} — «соседние» понятия: оба прямые подклассы {self._label(lca)}", path
            return "cousins", (f"{l1} и {l2} относятся к одной ветке {self._label(lca)}, "
                               f"но не напрямую (расстояние до предка: {d1} и {d2})"), path
        if union:
            lca, d1, d2 = union["lca"], union["dist1"], union["dist2"]
            path = self._build_path(id1, id2, lca, "all")
            if lca == id1:
                return "part_whole", f"{l2} входит в {l1} (часть — целое)", path
            if lca == id2:
                return "part_whole", f"{l1} входит в {l2} (часть — целое)", path
            return "common_whole", f"{l1} и {l2} — разные элементы одного целого {self._label(lca)}", path
        no_tax = f"Таксономического родства между {l1} и {l2} в базе знаний нет"
        link = self._shortest_link_path(id1, id2)
        if link:
            path = [{"concept_id": c, "term": self._term(c),
                     "role": "start" if i == 0 else ("end" if i == len(link) - 1 else "via"),
                     "edge": None} for i, c in enumerate(link)]
            hops = len(link) - 1
            how = "напрямую связаны" if hops == 1 else f"связаны через цепочку из {hops} связей"
            return "linked", f"{no_tax}, но по горизонтальным связям они {how}", path
        if self._concepts[id1].get("topic_id") == self._concepts[id2].get("topic_id"):
            return "same_topic", f"{no_tax}; горизонтальных связей тоже нет, но понятия изучаются в одном разделе", []
        return "unrelated", f"{no_tax}, горизонтальных связей между ними тоже нет — сравнивайте по определениям", []

    def _build_path(self, id1: str, id2: str, lca: str, layer: str) -> List[Dict[str, str]]:
        up1 = self._path_up(id1, lca, layer)           # id1 … lca
        up2 = self._path_up(id2, lca, layer)           # id2 … lca
        seq = up1 + up2[::-1][1:]                       # id1 … lca … id2
        out = []
        for i, cid in enumerate(seq):
            if cid == lca:
                role = "lca"
            elif i == 0:
                role = "start"
            elif i == len(seq) - 1:
                role = "end"
            else:
                role = "up" if i < len(up1) else "down"
            edge = None
            if i < len(seq) - 1:
                a, b = cid, seq[i + 1]
                kind = self._parents[a].get(b) or self._parents[b].get(a)
                edge = KIND_LABEL.get(kind)
            out.append({"concept_id": cid, "term": self._term(cid), "role": role, "edge": edge})
        return out

    @staticmethod
    def _path_text(path: List[Dict[str, str]]) -> str:
        """«A ⟶ P ⟶ LCA ⟵ Q ⟵ B»: стрелка идёт от потомка к предку."""
        if not path:
            return ""
        lca_idx = next((i for i, n in enumerate(path) if n["role"] == "lca"), None)
        text = path[0]["term"]
        for i in range(1, len(path)):
            if lca_idx is None:
                arrow = "—"                       # цепочка по смысловым связям, без направления
            else:
                arrow = "⟶" if i <= lca_idx else "⟵"
            text += f" {arrow} {path[i]['term']}"
        return text

    def _study_order(self, id1, id2, lca_id, relationship) -> List[Dict[str, str]]:
        """Что за чем учить: общее → частное; при равенстве — как введено."""
        seq: List[str] = []
        if lca_id and lca_id not in (id1, id2) and relationship in ("siblings", "cousins", "common_whole"):
            seq.append(lca_id)
        pair = [id1, id2]
        if relationship == "descendant":
            pair = [id2, id1]
        elif relationship in ("siblings", "cousins", "common_whole"):
            pair.sort(key=lambda c: self.get_depth(c, "all"))
        seq.extend(pair)
        return [{"concept_id": c, "term": self._term(c)} for c in seq]

    def _tip(self, r: Dict[str, Any]) -> str:
        """Совет «как не перепутать»: опирается на род и на строки матрицы характеристик."""
        t1, t2 = self._label(r["concept_id_1"]), self._label(r["concept_id_2"])
        rel = r["relationship"]
        if r["contrasted"]:
            base = f"В базе знаний {t1} и {t2} прямо противопоставлены — запомните, чем именно они различаются."
        elif rel == "siblings":
            base = f"Не путайте: {t1} и {t2} — разные виды {self._label(r['lca_id'])}; общий род у них один, отличаются определением."
        elif rel in ("ancestor", "descendant"):
            gen, spec = (t1, t2) if rel == "ancestor" else (t2, t1)
            base = f"{spec} — частный случай {gen}: наследует его характеристики и добавляет собственные."
        elif rel == "cousins":
            base = f"Сначала разберитесь с общей веткой {self._label(r['lca_id'])}, затем с различиями."
        elif rel in ("part_whole", "common_whole"):
            base = "Это разные уровни/элементы одного целого — не смешивайте часть и целое."
        else:
            base = "Таксономической связи нет — сравнивайте понятия по определениям, характеристикам и общим связям."
        diff = [row["name"] for row in r["characteristics"] if row["status"] in ("different", "partly")]
        only = [row["name"] for row in r["characteristics"] if row["status"] in ("only_1", "only_2")]
        extra = []
        if diff:
            extra.append("характеристики, по которым они различаются: " + ", ".join(diff))
        if only:
            extra.append("описаны только у одного из них: " + ", ".join(only))
        return base + (" (" + "; ".join(extra) + ")" if extra else "")

    def _message(self, r: Dict[str, Any], headline: str) -> str:
        lines = [headline[0].upper() + headline[1:] + "."]
        if r["lca_id"] and r["relationship"] in ("siblings", "cousins", "common_whole"):
            lines.append(f"Ближайший общий предок: {self._label(r['lca_id'])}.")
        lines.append(f"Близость: {r['semantic_similarity']:.2f} ({r['similarity_level']}).")
        return "\n".join(lines)

    def compare_by_id(self, id1: str, id2: str) -> Dict[str, Any]:
        """Алиас для вызова из роутера (аргументы уже нормализованы до concept_id)."""
        return self.compare(id1, id2)
