"""
solver_diagnostics.py — Решатель адаптивной диагностики и построения учебной траектории (Сценарий 4).

Основной поток:
  1. Студент указывает целевой концепт (ID или термин).
  2. Определяются пререквизиты по связям «надкласс» и «используется в».
  3. По каждому пререквизиту генерируется проверочный вопрос.
  4. По ответам строится модель освоенных понятий; неосвоенные = пробелы.
  5. Строится граф зависимостей пробелов, выполняется топологическая сортировка
     (алгоритм Кана) -> упорядоченный план изучения с обоснованием каждого пункта.

Граничные случаи:
  - все пререквизиты освоены         -> status 'ready' (сообщение о готовности);
  - у цели нет пререквизитов         -> status 'no_prerequisites', план из одного элемента;
  - множественное наследование       -> пререквизиты собираются по всем ветвям без дублей.

Ошибочные ситуации:
  - цель отсутствует в БЗ            -> status 'error' + список похожих концептов;
  - часть вопросов без ответа        -> концепт консервативно считается неосвоенным.

Семантика связей (relations в БЗ):
  - A.relations['надкласс'] = [B]       : B — надкласс A         => B — пререквизит A;
  - A.relations['используется в'] = [B] : A используется в B     => A — пререквизит B.
Если в ваших данных «используется в» записано в обратную сторону (так его трактует
solver_trajectory.py: цель связи — пререквизит), создайте решатель с
used_in_inverted=True.

Использование (два шага, т.к. между ними студент отвечает на вопросы):
    solver = DiagnosticsSolver(loader)
    result, ctx = solver.start("C042")        # result != None -> сценарий завершён
    ...задать вопросы ctx.questions, собрать answers {concept_id: ответ}...
    result = solver.finish(ctx, answers)
или одним вызовом, если ответы уже есть:
    result = solver.run("C042", answers)
"""
import difflib
import heapq
import logging
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REL_SUPERCLASS = "надкласс"
REL_USED_IN = "используется в"

STATUS_ERROR = "error"
STATUS_READY = "ready"
STATUS_NO_PREREQ = "no_prerequisites"
STATUS_PLAN = "plan_built"

_YES = {"д", "да", "y", "yes", "1"}
_NO = {"н", "нет", "n", "no", "0"}


@dataclass
class Question:
    """Проверочный вопрос по одному концепту."""
    concept_id: str
    term: str
    text: str
    kind: str                                   # 'choice' — выбор определения, 'self' — самооценка
    options: List[str] = field(default_factory=list)
    correct_index: Optional[int] = None         # 0-based, только для kind == 'choice'


@dataclass
class DiagnosticsContext:
    """Состояние диагностики между шагами start() и finish()."""
    target_id: str
    deps: Dict[str, List[Tuple[str, str]]]      # концепт -> [(пререквизит, тип связи)]
    prerequisites: List[str]                    # пререквизиты цели (без неё), порядок обнаружения
    questions: List[Question]


class DiagnosticsSolver:
    """Решатель адаптивной диагностики пробелов и построения плана изучения."""

    def __init__(self, loader, used_in_inverted: bool = False, n_distractors: int = 3,
                 max_depth: Optional[int] = None, similar_limit: int = 5):
        """
        Args:
            loader: экземпляр KnowledgeBaseLoader (нужен loader.concepts_by_id)
            used_in_inverted: трактовать relations['используется в'] как «цель — пререквизит»
            n_distractors: число неверных вариантов в вопросе с выбором определения
            max_depth: ограничение глубины обхода пререквизитов (None — без ограничения)
            similar_limit: сколько похожих концептов показывать при ошибке
        """
        self.loader = loader
        self.used_in_inverted = used_in_inverted
        self.n_distractors = n_distractors
        self.max_depth = max_depth
        self.similar_limit = similar_limit
        self._used_in_rev: Optional[Dict[str, Set[str]]] = None

    # ------------------------------------------------------------------
    # Доступ к БЗ
    # ------------------------------------------------------------------
    @property
    def _concepts(self) -> Dict[str, dict]:
        return self.loader.concepts_by_id

    def _term(self, cid: str) -> str:
        return self._concepts.get(cid, {}).get("term", cid)

    def _relation_targets(self, cid: str, rel_type: str) -> List[str]:
        raw = self._concepts.get(cid, {}).get("relations", {}).get(rel_type, []) or []
        return [t for t in raw if t in self._concepts and t != cid]

    def _build_used_in_index(self) -> Dict[str, Set[str]]:
        """Обратный индекс: B -> {A : A «используется в» B}."""
        if self._used_in_rev is None:
            rev: Dict[str, Set[str]] = {}
            for cid in self._concepts:
                for target in self._relation_targets(cid, REL_USED_IN):
                    rev.setdefault(target, set()).add(cid)
            self._used_in_rev = rev
        return self._used_in_rev

    def direct_prerequisites(self, cid: str) -> List[Tuple[str, str]]:
        """Прямые пререквизиты концепта: [(id пререквизита, тип связи)] без дублей."""
        result: List[Tuple[str, str]] = []
        seen: Set[Tuple[str, str]] = set()

        def add(pid: str, rel: str) -> None:
            if (pid, rel) not in seen:
                seen.add((pid, rel))
                result.append((pid, rel))

        # Множественное наследование: берём ВСЕ надклассы
        for p in self._relation_targets(cid, REL_SUPERCLASS):
            add(p, REL_SUPERCLASS)

        if self.used_in_inverted:
            used_in = self._relation_targets(cid, REL_USED_IN)
        else:
            used_in = sorted(self._build_used_in_index().get(cid, ()))
        for p in used_in:
            add(p, REL_USED_IN)
        return result

    # ------------------------------------------------------------------
    # Поиск цели
    # ------------------------------------------------------------------
    def resolve_target(self, query: str) -> Optional[str]:
        """Определение concept_id по ID или по термину (без учёта регистра)."""
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
        """Похожие концепты: близкие по написанию термины и термины с подстрокой запроса."""
        query = (query or "").strip().lower()
        if not query:
            return []
        by_term: Dict[str, str] = {}
        for cid, concept in self._concepts.items():
            term = str(concept.get("term", "")).lower()
            if term:
                by_term.setdefault(term, cid)

        found: List[str] = []
        for t in difflib.get_close_matches(query, list(by_term), n=self.similar_limit, cutoff=0.5):
            found.append(by_term[t])
        for t, cid in by_term.items():
            if len(found) >= self.similar_limit:
                break
            if query in t and cid not in found:
                found.append(cid)
        return [{"concept_id": cid, "term": self._term(cid)} for cid in found[:self.similar_limit]]

    # ------------------------------------------------------------------
    # Шаг 2: сбор пререквизитов
    # ------------------------------------------------------------------
    def collect_prerequisites(
        self, target_id: str
    ) -> Tuple[Dict[str, List[Tuple[str, str]]], List[str]]:
        """
        Обход в ширину по всем ветвям (множественное наследование) без дублирования.

        Returns:
            deps  — концепт -> [(прямой пререквизит, тип связи)] для цели и всех её пререквизитов;
            order — пререквизиты цели (без неё) в порядке обнаружения (от ближних к дальним).
        """
        deps: Dict[str, List[Tuple[str, str]]] = {}
        order: List[str] = []
        visited: Set[str] = {target_id}
        queue = deque([(target_id, 0)])
        while queue:
            current, depth = queue.popleft()
            direct = self.direct_prerequisites(current)
            deps[current] = direct
            if self.max_depth is not None and depth >= self.max_depth:
                continue
            for pid, _rel in direct:
                if pid not in visited:
                    visited.add(pid)
                    order.append(pid)
                    queue.append((pid, depth + 1))
        return deps, order

    # ------------------------------------------------------------------
    # Шаг 3: генерация вопросов
    # ------------------------------------------------------------------
    @staticmethod
    def _short(text: str, limit: int = 160) -> str:
        text = " ".join(str(text).split())
        return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"

    def generate_questions(self, concept_ids: List[str]) -> List[Question]:
        """
        Вопрос на выбор определения (если у концепта есть определение и хватает
        отвлекающих вариантов), иначе — вопрос-самооценка.
        """
        questions = []
        for cid in concept_ids:
            q = self._make_choice_question(cid) or self._make_self_question(cid)
            questions.append(q)
        return questions

    def _make_self_question(self, cid: str) -> Question:
        term = self._term(cid)
        return Question(
            concept_id=cid, term=term, kind="self",
            text=f"Знакомо ли вам понятие «{term}» — можете ли объяснить его своими словами? (да/нет)")

    def _make_choice_question(self, cid: str) -> Optional[Question]:
        concept = self._concepts[cid]
        definition = self._short(concept.get("definition", ""))
        if not definition:
            return None

        topic = concept.get("topic_id", "")
        same_topic, other = [], []
        for other_id in sorted(self._concepts):
            if other_id == cid:
                continue
            d = self._short(self._concepts[other_id].get("definition", ""))
            if not d or d == definition:
                continue
            (same_topic if self._concepts[other_id].get("topic_id", "") == topic else other).append(d)

        rng = random.Random(cid)  # детерминированно для одного и того же концепта
        distractors: List[str] = []
        for pool in (same_topic, other):
            pool = list(dict.fromkeys(pool))        # уникальные, порядок сохранён
            rng.shuffle(pool)
            for d in pool:
                if len(distractors) < self.n_distractors and d not in distractors:
                    distractors.append(d)
        if len(distractors) < 2:
            return None

        options = distractors + [definition]
        rng.shuffle(options)
        term = concept.get("term", cid)
        return Question(
            concept_id=cid, term=term, kind="choice",
            text=f"Какое определение соответствует понятию «{term}»?",
            options=options, correct_index=options.index(definition))

    # ------------------------------------------------------------------
    # Шаг 4: модель освоенных понятий
    # ------------------------------------------------------------------
    @staticmethod
    def evaluate_answer(question: Question, answer: Any) -> Optional[bool]:
        """
        True — освоено, False — не освоено, None — нет (или нераспознанный) ответ.
        Для вопроса с выбором: номер варианта, 0 = «не знаю».
        Для самооценки: да/нет.
        """
        a = "" if answer is None else str(answer).strip().lower()
        if not a:
            return None
        if question.kind == "choice":
            if a.isdigit():
                n = int(a)
                if n == 0:
                    return False
                if 1 <= n <= len(question.options):
                    return (n - 1) == question.correct_index
            return None
        if a in _YES:
            return True
        if a in _NO:
            return False
        return None

    def build_mastery_model(
        self, questions: List[Question], answers: Mapping[str, Any]
    ) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Returns (mastered, gaps, unanswered). Концепты без ответа консервативно
        считаются неосвоенными: они попадают и в gaps, и в unanswered.
        """
        mastered: Set[str] = set()
        gaps: Set[str] = set()
        unanswered: Set[str] = set()
        for q in questions:
            verdict = self.evaluate_answer(q, answers.get(q.concept_id))
            if verdict is None:
                unanswered.add(q.concept_id)
                gaps.add(q.concept_id)
            elif verdict:
                mastered.add(q.concept_id)
            else:
                gaps.add(q.concept_id)
        return mastered, gaps, unanswered

    # ------------------------------------------------------------------
    # Шаг 5: граф пробелов и алгоритм Кана
    # ------------------------------------------------------------------
    @staticmethod
    def _ancestors(start: str, deps: Dict[str, List[Tuple[str, str]]]) -> Set[str]:
        """Все транзитивные пререквизиты концепта."""
        result: Set[str] = set()
        stack = [p for p, _ in deps.get(start, ())]
        while stack:
            node = stack.pop()
            if node in result:
                continue
            result.add(node)
            stack.extend(p for p, _ in deps.get(node, ()))
        return result

    def build_gap_graph(self, gaps: Set[str],
                        deps: Dict[str, List[Tuple[str, str]]]) -> Dict[str, List[str]]:
        """
        Граф зависимостей пробелов: ребро u -> v = «u нужно изучить раньше v».
        Зависимость учитывается и через освоенные промежуточные концепты
        (транзитивно), чтобы не терять порядок.
        """
        graph: Dict[str, List[str]] = {g: [] for g in gaps}
        for v in sorted(gaps):
            for u in sorted(self._ancestors(v, deps) & gaps):
                graph[u].append(v)
        return graph

    @staticmethod
    def kahn_sort(graph: Dict[str, List[str]]) -> Tuple[List[str], List[str]]:
        """
        Алгоритм Кана (лексикографический порядок среди равноправных вершин).

        Returns:
            (упорядоченный список, вершины, не вошедшие в порядок из-за цикла)
        """
        in_degree = {n: 0 for n in graph}
        for neighbors in graph.values():
            for v in neighbors:
                in_degree[v] += 1

        heap = [n for n, d in in_degree.items() if d == 0]
        heapq.heapify(heap)
        ordered: List[str] = []
        while heap:
            node = heapq.heappop(heap)
            ordered.append(node)
            for v in graph[node]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    heapq.heappush(heap, v)
        cycle = sorted(n for n, d in in_degree.items() if d > 0)
        return ordered, cycle

    # ------------------------------------------------------------------
    # Обоснование включения в план
    # ------------------------------------------------------------------
    def _explain(self, cid: str, target_id: str, deps: Dict[str, List[Tuple[str, str]]],
                 gaps: Set[str], unanswered: Set[str]) -> str:
        why = ("нет ответа на вопрос — считается неосвоенным"
               if cid in unanswered else "ответ показал пробел")
        links = []
        for dependent, plist in deps.items():
            if dependent != target_id and dependent not in gaps:
                continue
            for pid, rel in plist:
                if pid == cid:
                    links.append(f"«{self._term(dependent)}» (связь «{rel}»)")
        links = sorted(set(links))
        if links:
            need = "необходим для: " + ", ".join(links[:3]) + (" и др." if len(links) > 3 else "")
        else:
            need = f"входит в пререквизиты цели «{self._term(target_id)}»"
        return f"{why}; {need}"

    def _plan_item(self, cid: str, reason: str, is_target: bool = False) -> Dict[str, Any]:
        concept = self._concepts.get(cid, {})
        return {
            "concept_id": cid,
            "term": concept.get("term", cid),
            "topic_id": concept.get("topic_id", ""),
            "reason": reason,
            "is_target": is_target,
        }

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------
    def start(self, target_query: str) -> Tuple[Optional[Dict[str, Any]], Optional[DiagnosticsContext]]:
        """
        Шаг 1: поиск цели, сбор пререквизитов, генерация вопросов.

        Returns:
            (result, None) — сценарий завершён (ошибка или цель без пререквизитов);
            (None, ctx)    — нужно задать вопросы ctx.questions и вызвать finish().
        """
        target_id = self.resolve_target(target_query)
        if target_id is None:
            similar = self.find_similar(target_query)
            msg = f"Концепт «{(target_query or '').strip()}» отсутствует в базе знаний."
            msg += " Возможно, вы имели в виду один из похожих." if similar else \
                   " Похожих концептов не найдено."
            return {"status": STATUS_ERROR, "target_id": None, "target_term": None,
                    "message": msg, "similar": similar, "prerequisites": [],
                    "mastered": [], "gaps": [], "unanswered": [], "plan": [],
                    "cycle": []}, None

        deps, prereqs = self.collect_prerequisites(target_id)
        term = self._term(target_id)
        if not prereqs:
            return {"status": STATUS_NO_PREREQ, "target_id": target_id, "target_term": term,
                    "message": f"У концепта «{term}» нет пререквизитов — план состоит из одного элемента.",
                    "similar": [], "prerequisites": [], "mastered": [], "gaps": [],
                    "unanswered": [],
                    "plan": [self._plan_item(target_id,
                                             "целевой концепт не имеет пререквизитов — можно приступать",
                                             True)],
                    "cycle": []}, None

        return None, DiagnosticsContext(target_id, deps, prereqs, self.generate_questions(prereqs))

    def finish(self, ctx: DiagnosticsContext, answers: Mapping[str, Any]) -> Dict[str, Any]:
        """Шаг 2: по ответам строит модель освоенного, граф пробелов и план изучения."""
        target_id, deps = ctx.target_id, ctx.deps
        term = self._term(target_id)
        mastered, gaps, unanswered = self.build_mastery_model(ctx.questions, answers)

        base = {
            "target_id": target_id, "target_term": term, "similar": [],
            "prerequisites": list(ctx.prerequisites),
            "mastered": sorted(mastered), "gaps": sorted(gaps),
            "unanswered": sorted(unanswered), "cycle": [],
        }

        if not gaps:
            return {**base, "status": STATUS_READY, "plan": [],
                    "message": f"Все пререквизиты освоены. Вы готовы к изучению «{term}»."}

        graph = self.build_gap_graph(gaps, deps)
        ordered, cycle = self.kahn_sort(graph)
        if cycle:
            logger.warning("Цикл зависимостей среди пробелов: %s", cycle)
            ordered += cycle  # план не теряем, но сообщаем о цикле

        plan = [self._plan_item(cid, self._explain(cid, target_id, deps, gaps, unanswered))
                for cid in ordered]
        plan.append(self._plan_item(
            target_id, "целевой концепт — изучается после закрытия всех пробелов", True))

        return {**base, "status": STATUS_PLAN, "plan": plan, "cycle": cycle,
                "message": f"Выявлено пробелов: {len(gaps)}. "
                           f"План изучения для достижения цели «{term}»:"}

    def run(self, target_query: str, answers: Mapping[str, Any]) -> Dict[str, Any]:
        """Оба шага сразу (когда ответы уже собраны)."""
        result, ctx = self.start(target_query)
        return result if result is not None else self.finish(ctx, answers)


def get_missing_prerequisites(target_id: str, mastered_ids: List[str], loader) -> List[str]:
    """
    Совместимая замена заглушки из main.py: пререквизиты цели, которых нет среди
    заявленных студентом освоенных концептов (без вопросов), в порядке плана.
    """
    solver = DiagnosticsSolver(loader)
    tid = solver.resolve_target(target_id)
    if tid is None:
        return []
    deps, prereqs = solver.collect_prerequisites(tid)
    gaps = set(prereqs) - set(mastered_ids)
    if not gaps:
        return []
    ordered, cycle = solver.kahn_sort(solver.build_gap_graph(gaps, deps))
    return ordered + cycle
