# tests/test_scenario_compare.py — Сценарий 6: сравнение понятий
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.solver_comparator import ComparatorSolver
from src.solver_router import RouterError, SolverRouter
from tests.kb_fixtures import FakeLoader, make_concepts


class TestLookup(unittest.TestCase):
    def setUp(self):
        self.solver = ComparatorSolver(FakeLoader())

    def test_resolve_by_id_term_case(self):
        self.assertEqual(self.solver.resolve_concept("C002"), "C002")
        self.assertEqual(self.solver.resolve_concept("c002"), "C002")
        self.assertEqual(self.solver.resolve_concept("ИНФОРМАЦИЯ"), "C002")
        self.assertIsNone(self.solver.resolve_concept("нет"))
        self.assertIsNone(self.solver.resolve_concept(""))

    def test_homonym_returns_all(self):
        self.assertCountEqual(self.solver._resolve_all("Ссылка"), ["C010", "CL001"])

    def test_find_similar(self):
        similar = self.solver.find_similar("Информаци")
        self.assertIn("C002", [s["concept_id"] for s in similar])
        self.assertEqual(self.solver.find_similar(""), [])


class TestHierarchy(unittest.TestCase):
    def setUp(self):
        self.solver = ComparatorSolver(FakeLoader())

    def test_depth(self):
        self.assertEqual(self.solver.get_depth("C001"), 1)
        self.assertEqual(self.solver.get_depth("C002"), 2)
        self.assertEqual(self.solver.get_depth("C004"), 3)

    def test_ancestors_with_depth(self):
        self.assertEqual(self.solver.get_ancestors_with_depth("C004"),
                         {"C004": 0, "C002": 1, "C001": 2})

    def test_multiple_inheritance_ancestors(self):
        anc = self.solver.get_ancestors_with_depth("C007")
        self.assertEqual(set(anc), {"C007", "C002", "C003", "C001"})

    def test_lca_siblings(self):
        lca = self.solver._lca("C002", "C003", "isa")
        self.assertEqual((lca["lca"], lca["dist1"], lca["dist2"]), ("C001", 1, 1))
        self.assertAlmostEqual(lca["wu_palmer"], 0.5)        # 2*1 / (2*1 + 1 + 1)

    def test_lca_none_for_unrelated(self):
        self.assertIsNone(self.solver._lca("C002", "C005", "isa"))

    def test_cycle_edge_is_skipped(self):
        loader = FakeLoader(make_concepts(C001={"relations": {"надкласс": ["C004"]}}))
        solver = ComparatorSolver(loader)
        solver._ensure_graph()
        self.assertTrue(solver.skipped_edges)               # ребро, замыкающее цикл, пропущено
        solver.get_depth("C004")                             # и обход не зацикливается


class TestCompareRelationships(unittest.TestCase):
    def setUp(self):
        self.solver = ComparatorSolver(FakeLoader())

    def test_siblings(self):
        r = self.solver.compare("C002", "C003")
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["relationship"], "siblings")
        self.assertEqual(r["lca_id"], "C001")
        self.assertEqual((r["distance_1"], r["distance_2"]), (1, 1))
        self.assertAlmostEqual(r["wu_palmer"], 0.5)
        self.assertEqual(r["genus"]["term"], "Данные")
        self.assertIn("Данные", r["message"])

    def test_ancestor_and_descendant(self):
        r = self.solver.compare("C001", "C004")
        self.assertEqual(r["relationship"], "ancestor")
        self.assertEqual(r["lca_id"], "C001")
        self.assertEqual(self.solver.compare("C004", "C001")["relationship"], "descendant")

    def test_cousins(self):
        r = self.solver.compare("C004", "C003")
        self.assertEqual(r["relationship"], "cousins")
        self.assertEqual(r["lca_id"], "C001")
        self.assertEqual((r["distance_1"], r["distance_2"]), (2, 1))

    def test_part_whole(self):
        r = self.solver.compare("C008", "C009")
        self.assertEqual(r["relationship"], "part_whole")
        self.assertEqual(r["lca_layer"], "all")
        self.assertIsNone(r["genus"])                         # род — только для is-a

    def test_unrelated_same_topic_vs_different_topic(self):
        far = self.solver.compare("C005", "C001")
        self.assertEqual(far["relationship"], "unrelated")
        self.assertIsNone(far["lca_id"])
        self.assertEqual(far["semantic_similarity"], 0.0)
        self.assertEqual(far["similarity_level"], "далёкие")
        near = self.solver.compare("C005", "C006")            # оба T02, связей нет
        self.assertEqual(near["relationship"], "same_topic")

    def test_linked_by_horizontal_relation(self):
        loader = FakeLoader(make_concepts(C005={"relations": {"связано с": ["C009"]}}))
        r = ComparatorSolver(loader).compare("C005", "C009")
        self.assertEqual(r["relationship"], "linked")
        self.assertEqual(len(r["horizontal"]["link_path"]), 2)

    def test_identical(self):
        r = ComparatorSolver(FakeLoader()).compare("C002", "информация")
        self.assertEqual(r["status"], "identical")
        self.assertEqual(r["semantic_similarity"], 1.0)
        self.assertEqual((r["distance_1"], r["distance_2"]), (0, 0))

    def test_multiple_inheritance_hybrid_vs_parent(self):
        r = self.solver.compare("C007", "C002")
        self.assertEqual(r["relationship"], "descendant")
        self.assertEqual(r["lca_id"], "C002")

    def test_contrast(self):
        loader = FakeLoader(make_concepts(C002={"relations": {
            "надкласс": ["C001"], "противопоставляется": ["C003"]}}))
        r = ComparatorSolver(loader).compare("C002", "C003")
        self.assertTrue(r["contrasted"])
        self.assertIn("противопоставлены", r["tip"])
        self.assertFalse(self.solver.compare("C002", "C003")["contrasted"])


class TestCompareCard(unittest.TestCase):
    def setUp(self):
        self.solver = ComparatorSolver(FakeLoader(labs={"C002": ["L01"]}))
        self.r = self.solver.compare("C002", "C003")

    def test_symmetry_of_similarity(self):
        back = self.solver.compare("C003", "C002")
        self.assertEqual(self.r["semantic_similarity"], back["semantic_similarity"])
        self.assertEqual(self.r["lca_id"], back["lca_id"])

    def test_similarity_in_range_for_all_pairs(self):
        ids = list(self.solver._concepts)
        for a in ids:
            for b in ids:
                r = self.solver.compare(a, b)
                if r["status"] != "success":
                    continue
                self.assertGreaterEqual(r["semantic_similarity"], 0.0, (a, b))
                self.assertLessEqual(r["semantic_similarity"], 1.0, (a, b))

    def test_siblings_more_similar_than_cousins(self):
        cousins = self.solver.compare("C004", "C003")
        self.assertGreater(self.r["semantic_similarity"], cousins["semantic_similarity"])

    def test_paths_from_lca_to_concepts(self):
        r = self.solver.compare("C004", "C003")
        self.assertEqual([n["concept_id"] for n in r["path_1"]], ["C001", "C002", "C004"])
        self.assertEqual([n["concept_id"] for n in r["path_2"]], ["C001", "C003"])
        self.assertIn("⟶", r["path_text"])

    def test_common_ancestors_list(self):
        r = self.solver.compare("C004", "C003")
        self.assertEqual([a["concept_id"] for a in r["common_ancestors"]], ["C001"])

    def test_characteristics_matrix_status(self):
        rows = {row["name"]: row for row in self.r["characteristics"]}
        row = rows["свойства"]
        self.assertEqual(row["status"], "partly")            # «достоверность» общая
        self.assertEqual(row["shared"], ["достоверность"])

    def test_characteristics_only_one_side_and_common(self):
        loader = FakeLoader(make_concepts(
            C002={"relations": {"надкласс": ["C001"], "структура": ["x"], "синтаксис": ["s"]}},
            C003={"relations": {"надкласс": ["C001"], "структура": ["x"], "применение": ["a"]}}))
        rows = {r["name"]: r["status"] for r in ComparatorSolver(loader).compare("C002", "C003")["characteristics"]}
        self.assertEqual(rows, {"структура": "common", "синтаксис": "only_1", "применение": "only_2"})

    def test_hierarchy_keys_not_in_characteristics(self):
        names = [row["name"] for row in self.r["characteristics"]]
        self.assertNotIn("надкласс", names)

    def test_differences_profiles(self):
        d = self.r["differences"]
        self.assertEqual(d["concept_1"]["term"], "Информация")
        self.assertEqual(d["concept_2"]["term"], "Знания")
        self.assertEqual(d["concept_1"]["superclasses"], ["Данные"])
        self.assertEqual(d["concept_1"]["branch_to_lca"], ["Информация", "Данные"])
        self.assertIn("Осмысленные данные", d["concept_1"]["definition"])

    def test_study_order_general_first(self):
        order = [o["concept_id"] for o in self.r["study"]["order"]]
        self.assertEqual(order[0], "C001")                    # сначала общий род
        self.assertCountEqual(order, ["C001", "C002", "C003"])
        desc = [o["concept_id"] for o in self.solver.compare("C004", "C001")["study"]["order"]]
        self.assertEqual(desc, ["C001", "C004"])

    def test_labs_in_study(self):
        self.assertEqual(self.r["study"]["labs"], ["L01"])

    def test_common_same_topic(self):
        self.assertTrue(self.r["common"]["same_topic"])
        self.assertEqual(self.r["common"]["topic_id"], "T01")

    def test_tip_and_message_are_non_empty(self):
        self.assertTrue(self.r["tip"])
        self.assertIn("Близость", self.r["message"])


class TestCompareErrors(unittest.TestCase):
    def setUp(self):
        self.solver = ComparatorSolver(FakeLoader())

    def test_not_found_with_hints(self):
        r = self.solver.compare("Информаци", "C003")
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["code"], "not_found")
        self.assertEqual(r["missing"][0]["query"], "Информаци")
        self.assertIn("C002", [s["concept_id"] for s in r["missing"][0]["similar"]])

    def test_both_missing(self):
        r = self.solver.compare("xxx", "yyy")
        self.assertEqual(len(r["missing"]), 2)

    def test_ambiguous(self):
        r = self.solver.compare("Ссылка", "C001")
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["code"], "ambiguous")
        self.assertCountEqual([c["concept_id"] for c in r["ambiguous"][0]["candidates"]], ["C010", "CL001"])

    def test_homonym_labelled_with_id_in_message(self):
        r = self.solver.compare("CL001", "C010")
        self.assertIn("[CL001]", r["message"] + " ".join(str(v) for v in r.values() if isinstance(v, str)))


class TestCompareThroughRouter(unittest.TestCase):
    def setUp(self):
        self.router = SolverRouter(FakeLoader())

    def req(self, params):
        return self.router.handle_request({"action": "compare", "params": params})

    def test_success_by_id_and_term(self):
        resp = self.req({"concept_1": "C002", "concept_2": "Знания"})
        self.assertEqual(resp["status"], "success")
        data = resp["data"]
        self.assertEqual(data["lca_id"], "C001")
        for key in ("semantic_similarity", "distance_1", "distance_2", "common_ancestors"):
            self.assertIn(key, data)                          # поля, которые показывает страница

    def test_identical_is_success(self):
        resp = self.req({"concept_1": "C002", "concept_2": "C002"})
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["data"]["status"], "identical")

    def test_errors(self):
        self.assertEqual(self.req({"concept_1": "C002"})["error"]["code"], "MISSING_PARAM")
        self.assertEqual(self.req({"concept_1": "C002", "concept_2": "C999"})["error"]["code"], "CONCEPT_NOT_FOUND")
        self.assertEqual(self.req({"concept_1": "C002", "concept_2": "C9"})["error"]["code"], "BAD_ID_FORMAT")
        self.assertEqual(self.req({"concept_1": "C002", "concept_2": "Ссылка"})["error"]["code"], "AMBIGUOUS_CONCEPT")
        self.assertEqual(self.req({"concept_1": "C002", "concept_2": 5})["error"]["code"], "BAD_PARAM_TYPE")

    def test_not_found_hint_for_typo(self):
        err = self.req({"concept_1": "Информаци", "concept_2": "C003"})["error"]
        self.assertEqual(err["code"], "CONCEPT_NOT_FOUND")
        self.assertIn("информация", err["details"]["similar"])

    def test_unknown_action(self):
        resp = self.router.handle_request({"action": "nope", "params": {}})
        self.assertEqual(resp["error"]["code"], "UNKNOWN_ACTION")


class TestCompareOnRealKB(unittest.TestCase):
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
        cls.ids = list(loader.concepts_by_id)

    def test_random_pairs_do_not_crash_and_are_in_range(self):
        pairs = [(self.ids[i], self.ids[-1 - i]) for i in range(0, 60, 3)]
        for a, b in pairs:
            resp = self.router.handle_request({"action": "compare", "params": {"concept_1": a, "concept_2": b}})
            self.assertEqual(resp["status"], "success", (a, b, resp.get("error")))
            self.assertTrue(0.0 <= resp["data"]["semantic_similarity"] <= 1.0)

    def test_symmetry_on_real_kb(self):
        a, b = self.ids[0], self.ids[10]
        r1 = self.router.handle_request({"action": "compare", "params": {"concept_1": a, "concept_2": b}})
        r2 = self.router.handle_request({"action": "compare", "params": {"concept_1": b, "concept_2": a}})
        self.assertEqual(r1["data"]["semantic_similarity"], r2["data"]["semantic_similarity"])


class TestRouterGateway(unittest.TestCase):
    """Общие свойства API-шлюза: формат запроса, подключение решателей, обработка сбоев."""

    def setUp(self):
        self.router = SolverRouter(FakeLoader())

    def req(self, request):
        return self.router.handle_request(request)

    # ------------------------------------------------------------ формат запроса
    def test_request_must_be_a_dict(self):
        for bad in (None, "compare", 42, [], ["compare"]):
            resp = self.req(bad)
            self.assertEqual(resp["status"], "error", bad)
            self.assertEqual(resp["error"]["code"], "BAD_REQUEST", bad)
            self.assertIsNone(resp["action"])

    def test_params_must_be_an_object(self):
        resp = self.req({"action": "compare", "params": ["C001", "C002"]})
        self.assertEqual(resp["error"]["code"], "BAD_REQUEST")
        self.assertEqual(resp["action"], "compare")

    def test_missing_or_empty_params_are_treated_as_empty(self):
        for request in ({"action": "compare"}, {"action": "compare", "params": None}, {"action": "compare", "params": {}}):
            self.assertEqual(self.req(request)["error"]["code"], "MISSING_PARAM")

    def test_unknown_action_lists_available_ones(self):
        err = self.req({"action": "nope", "params": {}})["error"]
        self.assertEqual(err["code"], "UNKNOWN_ACTION")
        self.assertEqual(err["details"]["available_actions"], ["diagnose", "plan", "compare", "admin", "analytics"])
        self.assertEqual(self.req({"params": {}})["error"]["code"], "UNKNOWN_ACTION")      # action не задан

    def test_response_envelope(self):
        resp = self.req({"action": "compare", "params": {"concept_1": "C002", "concept_2": "C003"}})
        self.assertEqual(set(resp), {"status", "action", "data", "explanation", "error", "metadata"})
        self.assertEqual(resp["metadata"]["kb_concepts"], len(self.router.loader.concepts_by_id))
        self.assertEqual(resp["metadata"]["warnings"], [])
        self.assertGreaterEqual(resp["metadata"]["elapsed_ms"], 0)
        self.assertIn("C001", resp["explanation"]["used_concepts"])
        self.assertIsNone(resp["error"])

    # ------------------------------------------------------ подключение решателей
    def test_all_solvers_are_connected(self):
        self.assertEqual(set(self.router.solvers), {"diagnose", "plan", "compare", "admin", "analytics"})

    def test_unavailable_solver(self):
        del self.router.solvers["compare"]
        resp = self.req({"action": "compare", "params": {"concept_1": "C001", "concept_2": "C002"}})
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error"]["code"], "SOLVER_UNAVAILABLE")
        self.assertIn("compare", resp["error"]["message"])

    def test_broken_module_is_skipped_with_warning(self):
        router = SolverRouter(FakeLoader())
        router.solvers.clear()
        with self.assertLogs("src.solver_router", level="WARNING") as logs:
            router._load("compare", "module_that_does_not_exist", "ComparatorSolver")
        self.assertNotIn("compare", router.solvers)
        self.assertIn("не подключён", logs.output[0])

    def test_broken_class_name_or_constructor_is_skipped(self):
        router = SolverRouter(FakeLoader())
        router.solvers.clear()
        with self.assertLogs("src.solver_router", level="WARNING"):
            router._load("compare", "solver_comparator", "NoSuchClass")
            router._load("plan", "solver_trajectory", "TrajectorySolver", "лишний", "аргумент", "тут")
        self.assertEqual(router.solvers, {})
        router._load("compare", "solver_comparator", "ComparatorSolver", FakeLoader())     # нормальное подключение
        self.assertIn("compare", router.solvers)

    # ------------------------------------------------------------- сбои решателей
    def test_internal_error_is_reported_not_raised(self):
        def boom(*_):
            raise RuntimeError("boom")

        self.router.solvers["compare"].compare_by_id = boom
        with self.assertLogs("src.solver_router", level="ERROR"):
            resp = self.req({"action": "compare", "params": {"concept_1": "C001", "concept_2": "C002"}})
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error"]["code"], "INTERNAL_ERROR")
        self.assertIn("RuntimeError: boom", resp["error"]["details"])
        self.assertIsNone(resp["data"])

    def test_internal_error_in_analytics_and_admin(self):
        def boom(*_, **__):
            raise ValueError("сломано")

        self.router.solvers["analytics"].analyze_gaps = boom
        self.router.solvers["admin"].run_validation = boom
        with self.assertLogs("src.solver_router", level="ERROR"):
            a = self.req({"action": "analytics", "params": {"student_models": [[]], "target_concepts": ["C001"]}})
            b = self.req({"action": "admin", "params": {}})
        self.assertEqual(a["error"]["code"], "INTERNAL_ERROR")
        self.assertEqual(b["error"]["code"], "INTERNAL_ERROR")

    def test_compare_failure_is_wrapped(self):
        failure = {"status": "error", "message": "нет общего предка"}
        self.router.solvers["compare"].compare_by_id = lambda a, b: failure
        err = self.req({"action": "compare", "params": {"concept_1": "C001", "concept_2": "C002"}})["error"]
        self.assertEqual(err["code"], "COMPARE_FAILED")
        self.assertEqual(err["message"], "нет общего предка")
        self.assertEqual(err["details"], failure)

    def test_compare_failure_without_message_uses_default(self):
        self.router.solvers["compare"].compare_by_id = lambda a, b: {"status": "error"}
        err = self.req({"action": "compare", "params": {"concept_1": "C001", "concept_2": "C002"}})["error"]
        self.assertEqual(err["message"], "Не удалось сравнить понятия")

    # ------------------------------------------------------- валидация параметров
    def test_concept_list_optional_and_required(self):
        self.assertEqual(self.router._concept_list({}, "gaps", required=False), [])
        self.assertEqual(self.router._concept_list({"gaps": None}, "gaps", required=False), [])
        with self.assertRaises(RouterError) as ctx:
            self.router._concept_list({}, "gaps")
        self.assertEqual(ctx.exception.code, "MISSING_PARAM")
        self.assertEqual(ctx.exception.details, {"missing": "gaps"})

    def test_concept_list_accepts_collections_and_dedups(self):
        self.assertEqual(self.router._concept_list({"g": ("C002", "Данные", "c002")}, "g"), ["C002", "C001"])
        self.assertEqual(self.router._concept_list({"g": {"C001"}}, "g"), ["C001"])
        self.assertEqual(self.router._concept_list({"g": []}, "g"), [])

    def test_concept_list_rejects_non_collections(self):
        for bad in ("C001", 5, {"C001": 1}):
            resp = self.req({"action": "plan", "params": {"gaps": bad}})
            self.assertEqual(resp["error"]["code"], "BAD_PARAM_TYPE", bad)

    def test_resolve_normalizes_ids_and_rejects_empty(self):
        self.assertEqual(self.router._resolve("x", "  c002 "), "C002")
        self.assertEqual(self.router._resolve("x", "CL001"), "CL001")
        self.assertEqual(self.router._resolve("x", "  ФАКТ "), "C004")
        for bad in ("", "   ", None, 7, ["C001"]):
            with self.assertRaises(RouterError) as ctx:
                self.router._resolve("x", bad)
            self.assertEqual(ctx.exception.code, "BAD_PARAM_TYPE", bad)

    def test_ambiguous_term_describes_candidates(self):
        err = self.req({"action": "compare", "params": {"concept_1": "Ссылка", "concept_2": "C001"}})["error"]
        self.assertEqual(err["code"], "AMBIGUOUS_CONCEPT")
        cands = {c["concept_id"]: c for c in err["details"]["candidates"]}
        self.assertEqual(set(cands), {"C010", "CL001"})
        self.assertEqual(cands["C010"]["source"], "теория")
        self.assertEqual(cands["CL001"]["source"], "лабораторный практикум")
        self.assertEqual(cands["C010"]["topic_title"], "Структуры")
        self.assertEqual(err["details"]["param"], "concept_1")

    def test_candidate_truncates_long_definition_and_tolerates_missing_topics(self):
        long_def = "а" * 300
        c = self.router._candidate({"concept_id": "C500", "term": "Т", "topic_id": "T99", "definition": long_def})
        self.assertEqual(c["definition"], "а" * 140 + "…")
        self.assertEqual(c["topic_title"], "")                          # темы T99 нет в индексе
        short = self.router._candidate({"concept_id": "C501", "term": "Т", "topic_id": "T01", "definition": "  кратко  "})
        self.assertEqual(short["definition"], "кратко")
        bare = self.router._candidate({"concept_id": "C502"})
        self.assertEqual((bare["term"], bare["topic_id"], bare["definition"]), ("", "", ""))
        del self.router.loader.topics_index
        self.assertEqual(self.router._candidate({"concept_id": "C500", "topic_id": "T01"})["topic_title"], "")

    # ----------------------------------------------------------------- утилиты
    def test_collect_ids_walks_nested_structures(self):
        data = {"a": ["C001", {"b": ("C002", "не id")}], "c": {"C003", "C999"}, "d": 5, "e": None}
        self.assertEqual(self.router._collect_ids(data), {"C001", "C002", "C003"})
        self.assertEqual(self.router._collect_ids("C004"), {"C004"})
        self.assertEqual(self.router._collect_ids(None), set())

    def test_used_concepts_are_sorted_and_capped(self):
        concepts = make_concepts()
        for i in range(300):
            cid = f"C{1000 + i}"
            concepts[cid] = {"concept_id": cid, "term": f"т{i}", "topic_id": "T01", "definition": "", "examples": [], "relations": {}}
        router = SolverRouter(FakeLoader(concepts))
        resp = router.handle_request({"action": "analytics", "params": {
            "student_models": [[]], "target_concepts": [f"C{1000 + i}" for i in range(300)]}})
        used = resp["explanation"]["used_concepts"]
        self.assertEqual(len(used), 200)
        self.assertEqual(used, sorted(used))


if __name__ == "__main__":
    unittest.main()
