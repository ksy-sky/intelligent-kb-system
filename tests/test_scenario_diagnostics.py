# tests/test_scenario_diagnostics.py — Сценарий 4: адаптивная диагностика пробелов
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.solver_diagnostics import (DiagnosticsSolver, Question, get_missing_prerequisites,
                                    STATUS_ERROR, STATUS_NO_PREREQ, STATUS_PLAN, STATUS_READY)
from src.solver_router import SolverRouter
from src.solver_analytics import AnalyticsSolver
from src import results_store
from tests.kb_fixtures import FakeLoader, make_concepts


def correct_answers(solver, ctx):
    """Правильные ответы на все вопросы контекста."""
    out = {}
    for q in ctx.questions:
        out[q.concept_id] = str(q.correct_index + 1) if q.kind == "choice" else "да"
    return out


class TestPrerequisites(unittest.TestCase):
    def setUp(self):
        self.solver = DiagnosticsSolver(FakeLoader())

    def test_resolve_target_by_id_term_and_case(self):
        self.assertEqual(self.solver.resolve_target("C004"), "C004")
        self.assertEqual(self.solver.resolve_target("c004"), "C004")
        self.assertEqual(self.solver.resolve_target("  факт "), "C004")
        self.assertIsNone(self.solver.resolve_target("нет такого"))
        self.assertIsNone(self.solver.resolve_target(""))
        self.assertIsNone(self.solver.resolve_target(None))

    def test_direct_prerequisites_superclass_and_used_in(self):
        # C004: надкласс C002; C006 «используется в» C004 -> C006 пререквизит C004
        self.assertEqual(self.solver.direct_prerequisites("C004"),
                         [("C002", "надкласс"), ("C006", "используется в")])

    def test_used_in_inverted(self):
        inv = DiagnosticsSolver(FakeLoader(), used_in_inverted=True)
        # при инверсии цель связи «используется в» (C004) — пререквизит самого C006
        self.assertEqual(inv.direct_prerequisites("C006"), [("C004", "используется в")])

    def test_collect_prerequisites_bfs_order_without_duplicates(self):
        deps, order = self.solver.collect_prerequisites("C004")
        self.assertEqual(order, ["C002", "C006", "C001"])    # ближние раньше дальних
        self.assertEqual(len(order), len(set(order)))
        self.assertNotIn("C004", order)

    def test_multiple_inheritance_collects_all_branches_once(self):
        _, order = self.solver.collect_prerequisites("C007")
        self.assertCountEqual(order, ["C002", "C003", "C001"])  # C001 — общий предок, один раз

    def test_max_depth_limits_traversal(self):
        limited = DiagnosticsSolver(FakeLoader(), max_depth=1)
        _, order = limited.collect_prerequisites("C004")
        self.assertNotIn("C001", order)
        self.assertIn("C002", order)

    def test_unknown_relation_targets_ignored(self):
        loader = FakeLoader(make_concepts(C004={"relations": {"надкласс": ["C002", "C999"]}}))
        _, order = DiagnosticsSolver(loader).collect_prerequisites("C004")
        self.assertNotIn("C999", order)

    def test_concept_without_prerequisites(self):
        _, order = self.solver.collect_prerequisites("C005")
        self.assertEqual(order, [])


class TestQuestions(unittest.TestCase):
    def setUp(self):
        self.solver = DiagnosticsSolver(FakeLoader())

    def test_choice_question_contains_correct_definition(self):
        q = self.solver.generate_questions(["C002"])[0]
        self.assertEqual(q.kind, "choice")
        self.assertEqual(q.concept_id, "C002")
        self.assertIsNotNone(q.correct_index)
        self.assertIn("Осмысленные данные", q.options[q.correct_index])
        self.assertEqual(len(q.options), len(set(q.options)))        # без повторов
        self.assertLessEqual(len(q.options), 4)                      # 3 отвлекающих + верный

    def test_questions_are_deterministic(self):
        a = self.solver.generate_questions(["C002"])[0]
        b = DiagnosticsSolver(FakeLoader()).generate_questions(["C002"])[0]
        self.assertEqual(a.options, b.options)
        self.assertEqual(a.correct_index, b.correct_index)

    def test_self_question_when_no_definition(self):
        q = self.solver.generate_questions(["C011"])[0]
        self.assertEqual(q.kind, "self")
        self.assertEqual(q.options, [])
        self.assertIsNone(q.correct_index)

    def test_self_question_when_too_few_distractors(self):
        tiny = FakeLoader({k: v for k, v in make_concepts().items() if k in ("C001", "C002")})
        q = DiagnosticsSolver(tiny).generate_questions(["C001"])[0]
        self.assertEqual(q.kind, "self")

    def test_one_question_per_concept_in_order(self):
        qs = self.solver.generate_questions(["C002", "C006", "C001"])
        self.assertEqual([q.concept_id for q in qs], ["C002", "C006", "C001"])


class TestAnswersEvaluation(unittest.TestCase):
    choice = Question("C002", "Информация", "?", "choice", ["a", "b", "c", "d"], correct_index=2)
    selfq = Question("C001", "Данные", "?", "self")

    def test_choice_answers(self):
        ev = DiagnosticsSolver.evaluate_answer
        self.assertTrue(ev(self.choice, "3"))
        self.assertTrue(ev(self.choice, 3))
        self.assertFalse(ev(self.choice, "1"))
        self.assertFalse(ev(self.choice, "0"))            # «не знаю»
        self.assertIsNone(ev(self.choice, ""))
        self.assertIsNone(ev(self.choice, None))
        self.assertIsNone(ev(self.choice, "5"))           # вне диапазона
        self.assertIsNone(ev(self.choice, "abc"))

    def test_self_answers(self):
        ev = DiagnosticsSolver.evaluate_answer
        for yes in ("да", "Да", "y", "YES", "1", " д "):
            self.assertTrue(ev(self.selfq, yes), yes)
        for no in ("нет", "Нет", "n", "no", "0", "н"):
            self.assertFalse(ev(self.selfq, no), no)
        self.assertIsNone(ev(self.selfq, ""))
        self.assertIsNone(ev(self.selfq, "может быть"))

    def test_mastery_model_unanswered_counts_as_gap(self):
        solver = DiagnosticsSolver(FakeLoader())
        qs = [self.choice, self.selfq, Question("C003", "Знания", "?", "self")]
        mastered, gaps, unanswered = solver.build_mastery_model(
            qs, {"C002": "3", "C001": "нет"})            # C003 без ответа
        self.assertEqual(mastered, {"C002"})
        self.assertEqual(gaps, {"C001", "C003"})
        self.assertEqual(unanswered, {"C003"})


class TestGraphAndKahn(unittest.TestCase):
    def setUp(self):
        self.solver = DiagnosticsSolver(FakeLoader())

    def test_kahn_orders_prerequisites_first(self):
        ordered, cycle = DiagnosticsSolver.kahn_sort({"A": ["B"], "B": ["C"], "C": []})
        self.assertEqual(ordered, ["A", "B", "C"])
        self.assertEqual(cycle, [])

    def test_kahn_lexicographic_among_equals(self):
        ordered, _ = DiagnosticsSolver.kahn_sort({"B": [], "A": [], "C": []})
        self.assertEqual(ordered, ["A", "B", "C"])

    def test_kahn_detects_cycle(self):
        ordered, cycle = DiagnosticsSolver.kahn_sort({"A": ["B"], "B": ["A"], "C": []})
        self.assertEqual(ordered, ["C"])
        self.assertEqual(cycle, ["A", "B"])

    def test_gap_graph_is_transitive_through_mastered(self):
        deps, _ = self.solver.collect_prerequisites("C004")
        # C002 освоен, но C001 всё равно должен идти раньше C004-цепочки: пробелы C001 и C006
        graph = self.solver.build_gap_graph({"C001", "C006"}, deps)
        self.assertEqual(graph, {"C001": [], "C006": []})
        graph = self.solver.build_gap_graph({"C001", "C002"}, deps)
        self.assertEqual(graph["C001"], ["C002"])

    def test_get_missing_prerequisites(self):
        loader = FakeLoader()
        missing = get_missing_prerequisites("C004", ["C002"], loader)
        self.assertEqual(missing, ["C001", "C006"])
        self.assertEqual(get_missing_prerequisites("C004", ["C001", "C002", "C006"], loader), [])
        self.assertEqual(get_missing_prerequisites("C999", [], loader), [])


class TestStartFinish(unittest.TestCase):
    def setUp(self):
        self.solver = DiagnosticsSolver(FakeLoader())

    def test_unknown_target_returns_error_with_similar(self):
        result, ctx = self.solver.start("Фактт")
        self.assertIsNone(ctx)
        self.assertEqual(result["status"], STATUS_ERROR)
        self.assertEqual(result["plan"], [])
        self.assertIn("C004", [s["concept_id"] for s in result["similar"]])

    def test_target_without_prerequisites(self):
        result, ctx = self.solver.start("C005")
        self.assertIsNone(ctx)
        self.assertEqual(result["status"], STATUS_NO_PREREQ)
        self.assertEqual(len(result["plan"]), 1)
        self.assertTrue(result["plan"][0]["is_target"])

    def test_start_returns_context_with_questions(self):
        result, ctx = self.solver.start("C004")
        self.assertIsNone(result)
        self.assertEqual(ctx.target_id, "C004")
        self.assertEqual([q.concept_id for q in ctx.questions], ctx.prerequisites)

    def test_all_correct_means_ready(self):
        _, ctx = self.solver.start("C004")
        res = self.solver.finish(ctx, correct_answers(self.solver, ctx))
        self.assertEqual(res["status"], STATUS_READY)
        self.assertEqual(res["gaps"], [])
        self.assertEqual(res["plan"], [])
        self.assertEqual(sorted(res["mastered"]), sorted(ctx.prerequisites))

    def test_no_answers_all_gaps_and_unanswered(self):
        res = self.solver.run("C004", {})
        self.assertEqual(res["status"], STATUS_PLAN)
        self.assertCountEqual(res["gaps"], ["C001", "C002", "C006"])
        self.assertCountEqual(res["unanswered"], res["gaps"])
        self.assertEqual(res["mastered"], [])

    def test_plan_order_target_last_and_prerequisites_first(self):
        res = self.solver.run("C004", {})
        ids = [s["concept_id"] for s in res["plan"]]
        self.assertEqual(ids[-1], "C004")
        self.assertTrue(res["plan"][-1]["is_target"])
        self.assertLess(ids.index("C001"), ids.index("C002"))
        self.assertEqual(sum(s["is_target"] for s in res["plan"]), 1)
        self.assertTrue(all(s["reason"] for s in res["plan"]))

    def test_partial_knowledge_removes_mastered_from_plan(self):
        _, ctx = self.solver.start("C004")
        answers = correct_answers(self.solver, ctx)
        answers["C001"] = "0"                              # «не знаю» про Данные
        res = self.solver.finish(ctx, answers)
        self.assertEqual(res["gaps"], ["C001"])
        self.assertEqual([s["concept_id"] for s in res["plan"]], ["C001", "C004"])
        self.assertEqual(res["unanswered"], [])

    def test_reason_mentions_unanswered(self):
        res = self.solver.run("C004", {})
        self.assertIn("нет ответа", res["plan"][0]["reason"])

    def test_cycle_does_not_lose_plan(self):
        loader = FakeLoader(make_concepts(
            C001={"relations": {"надкласс": ["C002"]}}))   # C001 <-> C002 — цикл
        res = DiagnosticsSolver(loader).run("C004", {})
        self.assertEqual(res["status"], STATUS_PLAN)
        self.assertTrue({"C001", "C002"} <= set(res["cycle"]))
        self.assertTrue({"C001", "C002", "C004"} <= {s["concept_id"] for s in res["plan"]})


class TestResultsStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "sub", "diag.jsonl")
        self.addCleanup(self.tmp.cleanup)
        self.result = DiagnosticsSolver(FakeLoader()).run("C004", {})

    def test_save_and_load_latest(self):
        self.assertTrue(results_store.save_diagnostic("Аня", self.result, self.path))
        self.assertTrue(results_store.save_diagnostic("Аня", self.result, self.path))   # повтор
        self.assertTrue(results_store.save_diagnostic("", self.result, self.path))      # аноним
        latest = results_store.load_latest("C004", self.path)
        self.assertEqual({r["student"] for r in latest}, {"Аня", "аноним"})
        self.assertEqual(len(latest), 2)                  # последняя запись на студента
        self.assertEqual(results_store.list_targets(self.path), {"C004": 2})

    def test_nothing_to_save_without_prerequisites(self):
        res, _ = DiagnosticsSolver(FakeLoader()).start("C005")
        self.assertFalse(results_store.save_diagnostic("Аня", res, self.path))
        self.assertFalse(os.path.exists(self.path))

    def test_analytics_params(self):
        results_store.save_diagnostic("Аня", self.result, self.path)
        params = results_store.to_analytics_params(results_store.load_latest(None, self.path), 0.4)
        self.assertEqual(params["threshold"], 0.4)
        self.assertCountEqual(params["target_concepts"], ["C001", "C002", "C006"])
        self.assertEqual(params["student_models"], [[]])

    def test_broken_lines_are_skipped(self):
        results_store.save_diagnostic("Аня", self.result, self.path)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("{не json\n")
        self.assertEqual(len(results_store.load_latest(None, self.path)), 1)

    def test_load_from_missing_file(self):
        self.assertEqual(results_store.load_latest(None, os.path.join(self.tmp.name, "no.jsonl")), [])


class TestDiagnoseThroughRouter(unittest.TestCase):
    """То, что реально вызывает страница Streamlit: router.handle_request(diagnose)."""

    def setUp(self):
        self.router = SolverRouter(FakeLoader())

    def req(self, params):
        return self.router.handle_request({"action": "diagnose", "params": params})

    def test_first_call_need_input_without_correct_index(self):
        resp = self.req({"target": "C004"})
        self.assertEqual(resp["status"], "need_input")
        qs = resp["data"]["questions"]
        self.assertEqual(len(qs), 3)
        for q in qs:
            self.assertEqual(set(q), {"concept_id", "term", "text", "kind", "options"})
            self.assertIn(q["kind"], ("choice", "self"))

    def test_second_call_with_answers_builds_plan(self):
        resp = self.req({"target": "C004", "answers": {"C001": "", "C002": "", "C006": ""}})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"]["status"], STATUS_PLAN)
        self.assertEqual(sorted(resp["data"]["gaps"]), ["C001", "C002", "C006"])

    def test_page_answer_format_choice_and_yes_no(self):
        """Формат ответов страницы: '1'..'n', '0', 'да', 'нет', ''."""
        qs = self.req({"target": "C004"})["data"]["questions"]
        answers = {q["concept_id"]: ("0" if q["kind"] == "choice" else "нет") for q in qs}
        resp = self.req({"target": "C004", "answers": answers})
        self.assertEqual(resp["data"]["unanswered"], [])
        self.assertEqual(len(resp["data"]["gaps"]), 3)

    def test_empty_answers_dict_asks_questions_again(self):
        """Пустой словарь answers роутер считает «ответов нет». Страница всегда шлёт ключ на каждый вопрос
        (пустая строка = пропуск), поэтому на неё это не влияет."""
        self.assertEqual(self.req({"target": "C004", "answers": {}})["status"], "need_input")

    def test_target_without_prerequisites_is_success(self):
        resp = self.req({"target": "C005"})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"]["status"], STATUS_NO_PREREQ)

    def test_target_by_term(self):
        self.assertEqual(self.req({"target": "Факт"})["status"], "need_input")

    def test_errors(self):
        self.assertEqual(self.req({})["error"]["code"], "MISSING_PARAM")
        self.assertEqual(self.req({"target": "C99999"})["error"]["code"], "BAD_ID_FORMAT")
        self.assertEqual(self.req({"target": "Фактт"})["error"]["code"], "CONCEPT_NOT_FOUND")
        self.assertEqual(self.req({"target": "Ссылка"})["error"]["code"], "AMBIGUOUS_CONCEPT")
        self.assertEqual(self.req({"target": "C004", "answers": ["1"]})["error"]["code"], "BAD_PARAM_TYPE")
        self.assertEqual(self.req({"target": 5})["error"]["code"], "BAD_PARAM_TYPE")


class TestDiagnoseOnRealKB(unittest.TestCase):
    """Дымовой тест на настоящей базе знаний."""

    @classmethod
    def setUpClass(cls):
        try:
            from main import KB_FILES
            from src.kb_loader import KnowledgeBaseLoader
            loader = KnowledgeBaseLoader(KB_FILES)
            loader.load()
        except Exception as e:                           # pragma: no cover
            raise unittest.SkipTest(f"БЗ не загрузилась: {e}")
        cls.router = SolverRouter(loader)
        cls.loader = loader

    def test_full_flow_on_any_target_with_questions(self):
        for cid in self.loader.concepts_by_id:
            resp = self.router.handle_request({"action": "diagnose", "params": {"target": cid}})
            if resp["status"] == "need_input":
                answers = {q["concept_id"]: "" for q in resp["data"]["questions"]}
                final = self.router.handle_request(
                    {"action": "diagnose", "params": {"target": cid, "answers": answers}})
                self.assertEqual(final["status"], "success")
                data = final["data"]
                self.assertEqual(data["plan"][-1]["concept_id"], cid)
                self.assertEqual(len(data["gaps"]), len(resp["data"]["questions"]))
                return
        self.fail("в БЗ не нашлось ни одной цели с пререквизитами")


class TestAnalyticsSolver(unittest.TestCase):
    """Сценарий 8: AnalyticsSolver.analyze_gaps — групповые пробелы."""

    def setUp(self):
        self.solver = AnalyticsSolver(FakeLoader())

    def test_no_students_gives_empty_result(self):
        self.assertEqual(self.solver.analyze_gaps([], ["C001", "C002"]), [])

    def test_no_targets_gives_empty_result(self):
        self.assertEqual(self.solver.analyze_gaps([{"C001"}, set()], []), [])

    def test_ratio_threshold_and_ranking(self):
        models = [{"C001"}, {"C001", "C002"}]
        rows = self.solver.analyze_gaps(models, ["C001", "C002", "C003"], 0.5)
        self.assertEqual([r["concept_id"] for r in rows], ["C003", "C002"])     # C001 освоен всеми
        self.assertEqual(rows[0]["gap_ratio"], 1.0)
        self.assertEqual(rows[0]["students_with_gap"], 2)
        self.assertEqual(rows[1]["gap_ratio"], 0.5)                                 # порог включительный
        self.assertEqual(rows[1]["students_with_gap"], 1)
        self.assertTrue(all(r["total_students"] == 2 for r in rows))

    def test_default_threshold_is_half(self):
        rows = self.solver.analyze_gaps([{"C001"}, set(), set()], ["C001"])
        self.assertEqual([r["concept_id"] for r in rows], ["C001"])               # 2/3 >= 0.5
        self.assertEqual(self.solver.analyze_gaps([{"C001"}, {"C001"}, set()], ["C001"]), [])   # 1/3 < 0.5

    def test_threshold_zero_returns_everything_and_one_only_total_gaps(self):
        models = [{"C001"}, set()]
        everything = self.solver.analyze_gaps(models, ["C001", "C002"], 0)
        self.assertEqual([(r["concept_id"], r["gap_ratio"]) for r in everything], [("C002", 1.0), ("C001", 0.5)])
        total = self.solver.analyze_gaps(models, ["C001", "C002"], 1)
        self.assertEqual([r["concept_id"] for r in total], ["C002"])

    def test_threshold_zero_includes_fully_mastered(self):
        rows = self.solver.analyze_gaps([{"C001"}], ["C001"], 0)
        self.assertEqual(rows[0]["gap_ratio"], 0.0)

    def test_ties_sorted_by_concept_id(self):
        rows = self.solver.analyze_gaps([set()], ["C003", "C001", "C002"], 0.5)
        self.assertEqual([r["concept_id"] for r in rows], ["C001", "C002", "C003"])

    def test_ratio_is_rounded_to_two_digits(self):
        rows = self.solver.analyze_gaps([set(), {"C001"}, {"C001"}], ["C001"], 0.1)
        self.assertEqual(rows[0]["gap_ratio"], 0.33)

    def test_rows_are_enriched_from_kb(self):
        row = self.solver.analyze_gaps([set()], ["C004"])[0]
        self.assertEqual(row["term"], "Факт")
        self.assertEqual(row["topic_id"], "T01")

    def test_unknown_concept_gets_placeholders(self):
        row = self.solver.analyze_gaps([set()], ["C999"])[0]
        self.assertEqual((row["term"], row["topic_id"]), ("Unknown", "Unknown"))

    def test_models_may_be_lists_and_extra_concepts_are_ignored(self):
        rows = self.solver.analyze_gaps([["C001", "C777"], ["C001"]], ["C001", "C002"], 0.5)
        self.assertEqual([r["concept_id"] for r in rows], ["C002"])

    def test_duplicate_targets_are_counted_once(self):
        rows = self.solver.analyze_gaps([set()], ["C001", "C001"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["students_with_gap"], 1)

    def test_input_is_not_mutated(self):
        models = [{"C001"}]
        targets = ["C001", "C002"]
        self.solver.analyze_gaps(models, targets)
        self.assertEqual(models, [{"C001"}])
        self.assertEqual(targets, ["C001", "C002"])


class TestAnalyticsThroughRouter(unittest.TestCase):
    """Действие analytics через API-шлюз (страница «Аналитика»)."""

    def setUp(self):
        self.router = SolverRouter(FakeLoader())

    def req(self, params):
        return self.router.handle_request({"action": "analytics", "params": params})

    def code(self, params):
        resp = self.req(params)
        self.assertEqual(resp["status"], "error", resp)
        return resp["error"]["code"]

    def test_success_with_ids(self):
        resp = self.req({"student_models": [["C001"], []], "target_concepts": ["C001", "C002"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual([r["concept_id"] for r in resp["data"]], ["C002", "C001"])   # 1.0 раньше 0.5
        self.assertEqual(resp["data"][1]["gap_ratio"], 0.5)
        self.assertEqual(resp["explanation"]["summary"], "Концептов с долей пробелов ≥ 0.5: 2.")
        self.assertEqual(resp["explanation"]["used_concepts"], ["C001", "C002"])
        self.assertEqual(resp["metadata"]["warnings"], [])

    def test_targets_may_be_terms(self):
        resp = self.req({"student_models": [[]], "target_concepts": ["Данные", "c002"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual([r["concept_id"] for r in resp["data"]], ["C001", "C002"])

    def test_models_may_be_tuples_and_sets(self):
        resp = self.req({"student_models": (("C001",), {"C001"}, frozenset()), "target_concepts": ["C001"], "threshold": 0.3})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"][0]["students_with_gap"], 1)
        self.assertEqual(resp["data"][0]["total_students"], 3)

    def test_no_gaps_above_threshold(self):
        resp = self.req({"student_models": [["C001"], ["C001"]], "target_concepts": ["C001"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"], [])
        self.assertIn("не выявлено", resp["explanation"]["summary"])

    def test_empty_group(self):
        resp = self.req({"student_models": [], "target_concepts": ["C001"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"], [])

    def test_threshold_is_applied(self):
        params = {"student_models": [["C001"], []], "target_concepts": ["C001"]}
        self.assertEqual(len(self.req({**params, "threshold": 0.5})["data"]), 1)
        self.assertEqual(self.req({**params, "threshold": 0.9})["data"], [])
        self.assertEqual(len(self.req({**params, "threshold": 0})["data"]), 1)
        self.assertEqual(self.req({**params, "threshold": 1})["data"], [])       # границы допустимы (int)

    def test_unknown_concepts_in_models_are_dropped_with_warning(self):
        resp = self.req({"student_models": [["C001", "C999", 5], ["C001"]], "target_concepts": ["C001", "C002"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(len(resp["metadata"]["warnings"]), 1)
        self.assertIn("student_models[0]", resp["metadata"]["warnings"][0])
        self.assertEqual([r["concept_id"] for r in resp["data"]], ["C002"])

    def test_missing_params(self):
        self.assertEqual(self.code({"target_concepts": ["C001"]}), "MISSING_PARAM")
        self.assertEqual(self.code({"student_models": [[]]}), "MISSING_PARAM")
        self.assertEqual(self.code({}), "MISSING_PARAM")

    def test_bad_student_models_type(self):
        targets = {"target_concepts": ["C001"]}
        for bad in ("C001", {"C001": 1}, 5, ["C001"], [b"C001"], [["C001"], "C002"], [None], [5]):
            self.assertEqual(self.code({"student_models": bad, **targets}), "BAD_PARAM_TYPE", bad)

    def test_bad_target_concepts(self):
        self.assertEqual(self.code({"student_models": [[]], "target_concepts": "C001"}), "BAD_PARAM_TYPE")
        self.assertEqual(self.code({"student_models": [[]], "target_concepts": ["C999"]}), "CONCEPT_NOT_FOUND")
        self.assertEqual(self.code({"student_models": [[]], "target_concepts": ["C9"]}), "BAD_ID_FORMAT")
        self.assertEqual(self.code({"student_models": [[]], "target_concepts": ["Ссылка"]}), "AMBIGUOUS_CONCEPT")

    def test_bad_threshold_type(self):
        base = {"student_models": [[]], "target_concepts": ["C001"]}
        for bad in ("0.5", True, None, [0.5], {"t": 1}):
            self.assertEqual(self.code({**base, "threshold": bad}), "BAD_PARAM_TYPE", bad)

    def test_bad_threshold_value(self):
        base = {"student_models": [[]], "target_concepts": ["C001"]}
        for bad in (-0.1, 1.01, 5, -1):
            self.assertEqual(self.code({**base, "threshold": bad}), "BAD_PARAM_VALUE", bad)

    def test_duplicate_targets_collapsed(self):
        resp = self.req({"student_models": [[]], "target_concepts": ["C001", "Данные", "c001"]})
        self.assertEqual(len(resp["data"]), 1)

    def test_roundtrip_from_results_store(self):
        """Параметры, собранные results_store, принимаются шлюзом."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "diag.jsonl")
            results_store.save_diagnostic("Аня", DiagnosticsSolver(FakeLoader()).run("C004", {}), path)
            params = results_store.to_analytics_params(results_store.load_latest(None, path), 0.4)
        resp = self.req(params)
        self.assertEqual(resp["status"], "success", resp)
        self.assertCountEqual([r["concept_id"] for r in resp["data"]], ["C001", "C002", "C006"])


if __name__ == "__main__":
    unittest.main()
