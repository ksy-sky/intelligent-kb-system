"""
solver_comparator.py — Решатель «Чем отличаются A и B?» (Сценарий 6).

Роль в системе
-------------
Студент часто путает близкие понятия (жадный/ленивый квантификатор, RDF/RDFS,
данные/информация и т.п.). Компаратор отвечает на вопрос «в чём сходство и
различие этих двух понятий» и показывает, в каком порядке их изучать.
Поиск ближайшего общего предка (LCA) — лишь один из шагов, а не весь результат.

Что строится на выходе (сравнительная карточка)
-----------------------------------------------
1. Тип родства (relationship): совпадают / надкласс–подкласс / «соседи» / «двоюродные» /
   часть–целое / общее целое / связаны по смыслу / один раздел / не связаны.
2. LCA, путь через него и мера Ву–Палмера (по иерархии «is-a»).
3. Общее: общие предки, общие связи, общие ключевые слова определений, разделы и лабы.
4. Различия: собственная ветка каждого понятия, определение, примеры, отличительные слова.
5. Явные противопоставления из базы знаний («противопоставляется» и прямые связи).
6. Рекомендуемый порядок изучения и лабораторные работы.
7. Итоговая степень близости (0..1) с расшифровкой по составляющим.

Единый граф иерархии
--------------------
Связь «надкласс» задана только у части понятий (лабораторные L02/L04/L05). В теории
(T01–T07) иерархия записана «сверху вниз»: у родителя перечислены подклассы
(«разбиение*», «семейство подклассов», «виды») или части («составные части»,
«состав», «включает», …). Поэтому граф строится из двух видов рёбер:
  * is-a  — «надкласс» (ребёнок → родитель) + инверсия «разбиение*» и аналогов;
  * part  — инверсия «составные части», «состав», «включает» и аналогов.
Основной LCA и мера Ву–Палмера считаются только по is-a. Если общего is-a-предка нет,
используется объединённый граф (is-a + part): тогда говорим об «общем целом».
Рёбра, создающие цикл, пропускаются (граф всегда ацикличен).

Граничные случаи
----------------
* Понятия не найдены → status='error' + подсказки (опечатки).
* Термин неоднозначен (омонимы теории и лабораторных) → status='error', code='ambiguous'.
* Одинаковые понятия → status='identical'.
* Нет ни одной связи → relationship='unrelated' (карточка всё равно содержит различия).
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
# Для сравнения «общих связей» эти ключи малоинформативны
IGNORED_SHARED_KEYS = {"пояснение"}

KIND_ISA = "isa"
KIND_PART = "part"
KIND_LABEL = {KIND_ISA: "надкласс", KIND_PART: "часть целого"}

# Веса составляющих итоговой близости
W_HIERARCHY, W_CONTEXT, W_LEXICAL = 0.6, 0.2, 0.2
PART_LAYER_PENALTY = 0.7        # Ву–Палмер по объединённому графу (is-a+part) весит меньше

STOPWORDS = {
    "который", "которые", "которая", "которое", "которых", "также", "этого", "этот", "если",
    "быть", "есть", "для", "или", "при", "над", "под", "как", "что", "его", "ее", "их",
    "это", "тот", "такой", "между", "через", "после", "перед", "может", "могут", "используется",
    "используются", "представляет", "являются", "является", "позволяет", "обычно", "любой",
    "всех", "всей", "свой", "своих", "другой", "других", "которой", "котором", "только",
}

LEVELS = (
    (0.70, "практически совпадают"),
    (0.45, "очень близкие"),
    (0.25, "родственные"),
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
        self._neighbors: Dict[str, Set[str]] = {}          # любые ID-связи, в обе стороны
        self._edge_labels: Dict[Tuple[str, str], str] = {}  # (a, b) -> ключ relations у a
        self._stems: Dict[str, Dict[str, str]] = {}        # cid -> {стем: слово}
        self._df: Dict[str, int] = {}                      # стем -> в скольких понятиях встречается
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
        self._build_text_index()
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

    # ------------------------------------------------------------------ текстовый индекс
    @staticmethod
    def _tokenize(text: str) -> Dict[str, str]:
        """{стем: слово}. Грубый стемминг: первые 5 букв (русская морфология), без стоп-слов."""
        out: Dict[str, str] = {}
        for w in re.findall(r"[а-яёa-z]+", (text or "").lower()):
            if len(w) < 4 or w in STOPWORDS:
                continue
            out.setdefault(w[:5], w)
        return out

    def _build_text_index(self) -> None:
        self._stems.clear()
        df: Dict[str, int] = {}
        for cid, c in self._concepts.items():
            stems = self._tokenize(f"{c.get('term', '')} {c.get('definition', '')}")
            self._stems[cid] = stems
            for s in stems:
                df[s] = df.get(s, 0) + 1
        self._df = df

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
        n1, n2 = self._neighbors[id1], self._neighbors[id2]
        return self._jaccard(n1 | {id1}, n2 | {id2}) if (n1 or n2) else 0.0

    def _lexical_score(self, id1: str, id2: str) -> float:
        return self._jaccard(set(self._stems[id1]), set(self._stems[id2]))

    def _score(self, id1: str, id2: str) -> Tuple[float, Dict[str, float]]:
        h, _, _ = self._hierarchy_score(id1, id2)
        ctx, lex = self._context_score(id1, id2), self._lexical_score(id1, id2)
        total = W_HIERARCHY * h + W_CONTEXT * ctx + W_LEXICAL * lex
        parts = {"hierarchy": round(h, 3), "context": round(ctx, 3), "lexical": round(lex, 3)}
        return round(min(total, 1.0), 3), parts

    # ------------------------------------------------------------------ вспомогательное для карточки
    def _direct_links(self, id1: str, id2: str) -> List[Dict[str, str]]:
        links = []
        for a, b in ((id1, id2), (id2, id1)):
            key = self._edge_labels.get((a, b))
            if key is not None:
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

    def _distinctive_words(self, id1: str, id2: str, limit: int = 6) -> List[str]:
        """Слова определения id1, которых нет у id2; редкие по базе — первыми (они информативнее)."""
        s1, s2 = self._stems[id1], self._stems[id2]
        own = [(self._df.get(s, 1), -len(w), w) for s, w in s1.items() if s not in s2]
        own.sort()
        return [w for _, _, w in own[:limit]]

    def _shared_words(self, id1: str, id2: str, limit: int = 6) -> List[str]:
        s1, s2 = self._stems[id1], self._stems[id2]
        common = [(self._df.get(s, 1), -len(s1[s]), s1[s]) for s in s1 if s in s2]
        common.sort()
        return [w for _, _, w in common[:limit]]

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
            "branch_to_lca": branch,
            "distinctive_words": self._distinctive_words(cid, other),
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
        shared_nb = sorted((self._neighbors[id1] & self._neighbors[id2]) - {id1, id2})
        keys1 = {k for k in (self._concepts[id1].get("relations") or {}) if k not in IGNORED_SHARED_KEYS}
        keys2 = {k for k in (self._concepts[id2].get("relations") or {}) if k not in IGNORED_SHARED_KEYS}

        same_topic = self._concepts[id1].get("topic_id") == self._concepts[id2].get("topic_id")
        labs = sorted(set(self._labs(id1)) | set(self._labs(id2)))
        order = self._study_order(id1, id2, lca_id, relationship)

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
            "common_ancestors": [
                {"concept_id": a, "term": self._term(a),
                 "distance_to_c1": self._up(id1, lca_info["layer"])[a][0],
                 "distance_to_c2": self._up(id2, lca_info["layer"])[a][0]}
                for a in (lca_info["common"] if lca_info else [])
            ],
            "common": {
                "same_topic": same_topic,
                "topic_id": self._concepts[id1].get("topic_id") if same_topic else None,
                "relation_types": sorted(keys1 & keys2),
                "linked_concepts": [{"concept_id": n, "term": self._term(n)} for n in shared_nb[:8]],
                "keywords": self._shared_words(id1, id2),
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
        link = self._shortest_link_path(id1, id2)
        if link:
            path = [{"concept_id": c, "term": self._term(c),
                     "role": "start" if i == 0 else ("end" if i == len(link) - 1 else "via"),
                     "edge": None} for i, c in enumerate(link)]
            hops = len(link) - 1
            how = "напрямую связаны" if hops == 1 else f"связаны через цепочку из {hops} связей"
            return "linked", f"{l1} и {l2} не лежат в одной иерархии, но {how}", path
        if self._lexical_score(id1, id2) >= 0.2 and len(self._shared_words(id1, id2)) >= 2:
            return "text_similar", (f"{l1} и {l2} не связаны в иерархии, но их определения "
                                    "похожи по смыслу (общие ключевые слова)"), []
        if self._concepts[id1].get("topic_id") == self._concepts[id2].get("topic_id"):
            return "same_topic", f"{l1} и {l2} изучаются в одном разделе, но явных связей между ними нет", []
        return "unrelated", f"{l1} и {l2} в базе знаний не связаны", []

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
        """Совет «как не перепутать»."""
        d1, d2 = r["differences"]["concept_1"], r["differences"]["concept_2"]
        t1, t2 = self._label(r["concept_id_1"]), self._label(r["concept_id_2"])
        w1, w2 = d1["distinctive_words"][:3], d2["distinctive_words"][:3]
        rel = r["relationship"]
        if r["contrasted"]:
            base = f"В базе знаний {t1} и {t2} прямо противопоставлены — запомните, чем именно они различаются."
        elif rel == "siblings":
            base = f"Не путайте: {t1} и {t2} — разные виды {self._label(r['lca_id'])}."
        elif rel in ("ancestor", "descendant"):
            gen, spec = (t1, t2) if rel == "ancestor" else (t2, t1)
            base = f"{spec} наследует свойства {gen}, но имеет собственные особенности."
        elif rel == "cousins":
            base = f"Сначала разберитесь с общей веткой {self._label(r['lca_id'])}, затем с различиями."
        elif rel in ("part_whole", "common_whole"):
            base = "Это разные уровни/элементы одного целого — не смешивайте часть и целое."
        elif rel == "text_similar":
            base = "Явной связи в иерархии нет — сравнивайте понятия по определениям и примерам."
        else:
            base = "Понятия лежат в разных областях знаний; сравнивайте их по определениям."
        extra = []
        if w1:
            extra.append(f"для {t1} характерно: {', '.join(w1)}")
        if w2:
            extra.append(f"для {t2} характерно: {', '.join(w2)}")
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
