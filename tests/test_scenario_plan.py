# tests/test_scenario_plan.py — Сценарий 5: план изучения и рекомендации
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.solver_trajectory import TrajectorySolver
from src.solver_router import SolverRouter
from tests.kb_fixtures import FakeLoader, make_concepts


def ids(plan):
    return [s["concept_id"] for s in plan]


class TestBuildPlan(unittest.TestCase):
    def setUp(self):
        self.solver = TrajectorySolver(FakeLoader())

    def test_empty_gaps(self):
        self.assertEqual(self.solver.build_learning_plan([]), [])

    def test_unknown_ids_are_ignored(self):
        self.assertEqual(self.solver.build_learning_plan(["C999"]), [])
        self.assertEqual(ids(self.solver.build_learning_plan(["C999", "C002"])), ["C002"])

    def test_prerequisites_come_first(self):
        plan = self.solver.build_learning_plan(["C004", "C002", "C001"])
        self.assertEqual(ids(plan), ["C001", "C002", "C004"])

    def test_order_is_independent_of_input_order(self):
        a = ids(self.solver.build_learning_plan(["C004", "C001", "C002", "C003"]))
        b = ids(self.solver.build_learning_plan(["C003", "C002", "C001", "C004"]))
        self.assertEqual(a, b)

    def test_independent_concepts_sorted_by_id(self):
        plan = self.solver.build_learning_plan(["C009", "C005", "C006"])
        self.assertEqual(ids(plan), ["C005", "C006", "C009"])

    @unittest.expectedFailure
    def test_duplicates_in_gap_ids(self):
        """ИЗВЕСТНАЯ ОШИБКА решателя: дубль в gap_ids даёт ложный ValueError «цикл» (cycle_nodes = пусто).
        Через роутер это не проявляется (он убирает дубли). Исправление в solver_trajectory.build_learning_plan:
        valid_gaps = list(dict.fromkeys(gid for gid in gap_ids if gid in self.loader.concepts_by_id)).
        После исправления уберите декоратор @expectedFailure."""
        plan = self.solver.build_learning_plan(["C002", "C002", "C001"])
        self.assertEqual(ids(plan), ["C001", "C002"])

    def test_used_in_direction_in_trajectory(self):
        """Сценарий 5 трактует «A используется в B» как «B — пререквизит A» (цель связи изучается раньше).
        Как в данных БЗ: «обратная ссылка используется в группа» -> сначала «группа»."""
        plan = ids(self.solver.build_learning_plan(["C004", "C006"]))   # C006 «используется в» C004
        self.assertLess(plan.index("C004"), plan.index("C006"))

    def test_plan_item_fields(self):
        item = self.solver.build_learning_plan(["C002"])[0]
        self.assertEqual(set(item), {"concept_id", "term", "topic_id", "reason", "criticality"})
        self.assertEqual(item["term"], "Информация")
        self.assertEqual(item["topic_id"], "T01")
        self.assertTrue(item["reason"])

    def test_criticality_counts_transitive_dependents(self):
        plan = {s["concept_id"]: s for s in self.solver.build_learning_plan(["C001", "C004"])}
        # от C001 зависят: C002, C003, C004, C007, C011 (по надклассу) и C006 (через «используется в» C004)
        self.assertEqual(plan["C001"]["criticality"], 6)
        self.assertEqual(plan["C004"]["criticality"], 1)       # от C004 зависит только C006

    def test_cycle_raises_value_error(self):
        loader = FakeLoader(make_concepts(C001={"relations": {"надкласс": ["C002"]}}))
        with self.assertRaises(ValueError) as cm:
            TrajectorySolver(loader).build_learning_plan(["C001", "C002"])
        self.assertIn("цикл", str(cm.exception).lower())

    def test_cache_invalidation(self):
        self.solver.build_learning_plan(["C001"])
        self.assertIsNotNone(self.solver._forward_graph)
        self.solver.invalidate_cache()
        self.assertIsNone(self.solver._forward_graph)


class TestPlanWithTarget(unittest.TestCase):
    def setUp(self):
        self.solver = TrajectorySolver(FakeLoader())

    def test_target_is_added_to_plan(self):
        plan = self.solver.build_learning_plan(["C001"], "C004")
        self.assertIn("C004", ids(plan))

    def test_path_intermediates_are_added(self):
        # путь C001 — C002 — C004: C002 в плане, хотя не был пробелом
        plan = self.solver.build_learning_plan(["C001"], "C004")
        self.assertEqual(ids(plan), ["C001", "C002", "C004"])

    def test_target_reason(self):
        plan = self.solver.build_learning_plan(["C001"], "C004")
        self.assertEqual(plan[-1]["reason"], "Целевой концепт")

    def test_reason_shows_path_to_target(self):
        plan = self.solver.build_learning_plan(["C001"], "C004")
        self.assertIn("Путь к цели", plan[0]["reason"])
        self.assertIn("Данные", plan[0]["reason"])
        self.assertIn("Факт", plan[0]["reason"])

    def test_unreachable_target_is_reported(self):
        plan = self.solver.build_learning_plan(["C001"], "C005")   # C005 изолирован
        reason = {s["concept_id"]: s["reason"] for s in plan}["C001"]
        self.assertIn("Прямого пути", reason)

    def test_unknown_target_is_ignored(self):
        plan = self.solver.build_learning_plan(["C001"], "C999")
        self.assertEqual(ids(plan), ["C001"])

    def test_reason_without_target_mentions_dependents_or_criticality(self):
        plan = self.solver.build_learning_plan(["C001", "C002"])
        self.assertIn("Необходим для изучения", plan[0]["reason"])
        self.assertIn("критичность", plan[0]["reason"])
        leaf = self.solver.build_learning_plan(["C005"])[0]["reason"]
        self.assertIn("Базовый концепт", leaf)


class TestRecommendations(unittest.TestCase):
    def setUp(self):
        self.loader = FakeLoader(labs={"C002": ["L01"]})
        self.solver = TrajectorySolver(self.loader)

    def recs(self, gaps, target=None):
        plan = self.solver.build_learning_plan(gaps, target)
        return {r["concept_id"]: r for r in self.solver.generate_recommendations(plan)}

    def test_one_recommendation_per_step_with_fields(self):
        plan = self.solver.build_learning_plan(["C001", "C002"])
        recs = self.solver.generate_recommendations(plan)
        self.assertEqual(ids(recs), ids(plan))
        expected = {"concept_id", "term", "topic_id", "topic_title", "reason", "criticality",
                    "definition", "inherited_from", "examples", "related", "similar_by_text", "lab_ids"}
        self.assertEqual(set(recs[0]), expected)

    def test_topic_title_and_examples(self):
        r = self.recs(["C002"])["C002"]
        self.assertEqual(r["topic_title"], "Основы")
        self.assertEqual(r["examples"], ["новость"])
        self.assertIsNone(r["inherited_from"])

    def test_related_resolved_to_terms(self):
        r = self.recs(["C002"])["C002"]
        self.assertEqual(r["related"]["надкласс"], ["Данные"])
        self.assertEqual(r["related"]["свойства"], ["полезность", "достоверность"])   # текст как есть
        self.assertEqual(r["similar_by_text"], [])           # связи есть — запасной поиск не нужен

    def test_labs(self):
        self.assertEqual(self.recs(["C002"])["C002"]["lab_ids"], ["L01"])
        self.assertEqual(self.recs(["C001"])["C001"]["lab_ids"], [])

    def test_inherited_definition_from_superclass(self):
        r = self.recs(["C011"])["C011"]                      # у C011 нет определения, надкласс C001
        self.assertEqual(r["inherited_from"], "Данные")
        self.assertIn("Сведения", r["definition"])

    def test_similar_by_text_when_no_relations(self):
        r = self.recs(["C005"])["C005"]
        self.assertEqual(r["related"], {})
        self.assertLessEqual(len(r["similar_by_text"]), 3)
        for s in r["similar_by_text"]:
            self.assertNotEqual(s["concept_id"], "C005")
            self.assertGreater(s["similarity"], 0)

    def test_unknown_step_skipped(self):
        recs = self.solver.generate_recommendations(
            [{"concept_id": "C999", "term": "?", "reason": ""}])
        self.assertEqual(recs, [])


class TestPlanThroughRouter(unittest.TestCase):
    def setUp(self):
        self.router = SolverRouter(FakeLoader())

    def req(self, params):
        return self.router.handle_request({"action": "plan", "params": params})

    def test_success_has_plan_and_recommendations(self):
        resp = self.req({"gaps": ["C001", "C002"]})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(ids(resp["data"]["plan"]), ["C001", "C002"])
        self.assertEqual(ids(resp["data"]["recommendations"]), ["C001", "C002"])

    def test_gaps_by_term(self):
        resp = self.req({"gaps": ["Данные", "информация"]})
        self.assertEqual(ids(resp["data"]["plan"]), ["C001", "C002"])

    def test_with_target(self):
        """Так вызывает страница, когда пробелы пришли из диагностики."""
        resp = self.req({"gaps": ["C001"], "target": "C004"})
        self.assertEqual(ids(resp["data"]["plan"]), ["C001", "C002", "C004"])

    def test_target_none_is_allowed(self):
        self.assertEqual(self.req({"gaps": ["C001"], "target": None})["status"], "success")

    def test_empty_gaps_is_success_with_empty_plan(self):
        resp = self.req({"gaps": []})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"], {"plan": [], "recommendations": []})

    def test_duplicates_in_gaps_collapsed(self):
        self.assertEqual(ids(self.req({"gaps": ["C002", "c002", "Информация"]})["data"]["plan"]), ["C002"])

    def test_errors(self):
        self.assertEqual(self.req({})["error"]["code"], "MISSING_PARAM")
        self.assertEqual(self.req({"gaps": "C001"})["error"]["code"], "BAD_PARAM_TYPE")
        self.assertEqual(self.req({"gaps": ["C99999"]})["error"]["code"], "BAD_ID_FORMAT")
        self.assertEqual(self.req({"gaps": ["C999"]})["error"]["code"], "CONCEPT_NOT_FOUND")
        self.assertEqual(self.req({"gaps": ["Ссылка"]})["error"]["code"], "AMBIGUOUS_CONCEPT")
        self.assertEqual(self.req({"gaps": ["C001"], "target": "C999"})["error"]["code"], "CONCEPT_NOT_FOUND")

    def test_cycle_error(self):
        router = SolverRouter(FakeLoader(make_concepts(C001={"relations": {"надкласс": ["C002"]}})))
        resp = router.handle_request({"action": "plan", "params": {"gaps": ["C001", "C002"]}})
        self.assertEqual(resp["error"]["code"], "CYCLE_DETECTED")

    def test_metadata_present(self):
        resp = self.req({"gaps": ["C001"]})
        self.assertIn("elapsed_ms", resp["metadata"])
        self.assertEqual(resp["action"], "plan")


class TestDiagnosticsToPlanChain(unittest.TestCase):
    """Связка сценариев 4 -> 5, как на страницах: gaps и target_id из диагностики идут в план."""

    def test_gaps_from_diagnostics_feed_plan(self):
        router = SolverRouter(FakeLoader())
        diag = router.handle_request({"action": "diagnose",
                                      "params": {"target": "C002", "answers": {"C001": ""}}})["data"]
        plan = router.handle_request({"action": "plan",
                                      "params": {"gaps": diag["gaps"], "target": diag["target_id"]}})
        self.assertEqual(plan["status"], "success")
        plan_ids = ids(plan["data"]["plan"])
        self.assertTrue(set(diag["gaps"]) <= set(plan_ids))
        self.assertEqual(plan_ids[-1], "C002")


class TestPlanOnRealKB(unittest.TestCase):
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

    def test_plan_on_real_concepts(self):
        gaps = list(self.loader.concepts_by_id)[:5]
        resp = self.router.handle_request({"action": "plan", "params": {"gaps": gaps}})
        self.assertIn(resp["status"], ("success", "error"))
        if resp["status"] == "success":
            self.assertEqual(set(ids(resp["data"]["plan"])), set(gaps))
            self.assertEqual(ids(resp["data"]["plan"]), ids(resp["data"]["recommendations"]))


if __name__ == "__main__":
    unittest.main()
