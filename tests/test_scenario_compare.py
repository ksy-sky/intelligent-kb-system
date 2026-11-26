# tests/test_scenario_compare.py — Сценарий 6: сравнение понятий
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.solver_comparator import ComparatorSolver
from src.solver_router import SolverRouter
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


if __name__ == "__main__":
    unittest.main()
