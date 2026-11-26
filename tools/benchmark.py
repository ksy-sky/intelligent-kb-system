"""Замеры для п. 3.6: python tools/benchmark.py  (результат: data/../benchmark_results.csv не пишется, вывод в консоль)."""
import copy, glob, json, os, random, re, shutil, statistics, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from main import KB_FILES
from src.kb_loader import KnowledgeBaseLoader
from src.solver_router import SolverRouter
from src.solver_admin import AdminSolver

ID = re.compile(r"^(CL?)(\d+)$")
REPEAT = 5


def med(f, n=REPEAT):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); f(); ts.append((time.perf_counter() - t) * 1000)
    return statistics.median(ts)


def shift(v, k):
    if isinstance(v, str):
        m = ID.match(v)
        return f"{m.group(1)}{int(m.group(2)) + 1000 * k:0{len(m.group(2))}d}" if m else v
    if isinstance(v, list):
        return [shift(x, k) for x in v]
    if isinstance(v, dict):
        return {a: shift(b, k) if a in ("concept_id",) else (shift(b, k) if a in ("relations",) or isinstance(b, (list, dict)) else b) for a, b in v.items()}
    return v


def make_kb(copies, dst):
    for k in range(copies):
        for f in KB_FILES:
            d = json.load(open(f, encoding="utf-8"))
            for t in d["topics"]:
                t["topic_id"] = f"{t['topic_id']}_{k}" if k else t["topic_id"]
                for c in t["concepts"]:
                    c["topic_id"] = t["topic_id"]
                    c["concept_id"] = shift(c["concept_id"], k)
                    if "relations" in c:
                        c["relations"] = {r: shift(vs, k) for r, vs in c["relations"].items()}
            json.dump(d, open(os.path.join(dst, f"{k}_{os.path.basename(f)}"), "w", encoding="utf-8"), ensure_ascii=False)


def main():
    loader = KnowledgeBaseLoader(KB_FILES); loader.load()
    router = SolverRouter(loader)
    ids = sorted(loader.concepts_by_id)
    print(f"БЗ: {len(ids)} концептов\n")

    print("1) Аналитика (сценарий 8), |T| = 50, m = 100, theta = 0.5")
    random.seed(1)
    T = random.sample(ids, 50)
    print("  n      время решателя+роутера, мс")
    for n in (10, 100, 1000, 10000, 100000):
        models = [random.sample(ids, 100) for _ in range(n)]
        req = {"action": "analytics", "params": {"student_models": models, "target_concepts": T, "threshold": 0.5}}
        print(f"  {n:<6} {med(lambda: router.handle_request(req)):.2f}")

    print("\n2) Накладные расходы роутера (нормализация ID / термина / ошибка)")
    term = loader.concepts_by_id[ids[5]]["term"]
    for name, params in (("по ID", ids[5]), ("по термину", term), ("не найден", "несуществующийтермин")):
        req = {"action": "plan", "params": {"gaps": [params]}}
        r = router.handle_request(req)
        print(f"  {name:<12} status={r['status']:<10} elapsed_ms={r['metadata'].get('elapsed_ms')}")

    print("\n3) Валидация БЗ (сценарий 7) при росте размера БЗ")
    print("  копий  концептов  время, мс  status")
    for copies in (1, 2, 4, 8):
        tmp = tempfile.mkdtemp()
        try:
            make_kb(copies, tmp)
            adm = AdminSolver(KnowledgeBaseLoader, tmp)
            res = {}
            t = med(lambda: res.update(adm.run_validation()), 3)
            print(f"  {copies:<6} {len(ids)*copies:<9} {t:8.1f}  {res.get('status')} {res.get('error_code','')}")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
