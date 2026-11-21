"""
solver_router.py — API-шлюз (фасад) подсистемы решателей. Единая точка входа для UI.

Конвейер (записка, п. 2.4–2.5.1):
  1. action есть в реестре?                -> UNKNOWN_ACTION
  2. синтаксическая валидация параметров   -> MISSING_PARAM / BAD_PARAM_TYPE / BAD_PARAM_VALUE / BAD_ID_FORMAT
  3. семантическая валидация, нормализация -> CONCEPT_NOT_FOUND / AMBIGUOUS_CONCEPT  (ID или термин -> concept_id)
  4. вызов решателя
  5. ответ {status, action, data, explanation, error, metadata}

Действия: diagnose (сц.4), plan (сц.5), compare (сц.6), admin (сц.7), analytics (сц.8).
"""
import difflib
import logging
import os
import re
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ACTIONS = ("diagnose", "plan", "compare", "admin", "analytics")


class RouterError(Exception):
    """Штатная ошибка запроса: код + сообщение (+ детали)."""
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details


class SolverRouter:
    ID_PATTERN = re.compile(r"^C(?:L)?\d{2,4}$")
    ID_LIKE = re.compile(r"^C(?:L)?\d+$", re.IGNORECASE)   # похоже на ID, но формат неверный

    def __init__(self, kb_loader, data_dir: str = DATA_DIR):
        self.loader = kb_loader
        self.solvers = {}
        # решатели подключаются по одному: сломанный модуль коллеги не ломает остальные
        self._load("diagnose", "solver_diagnostics", "DiagnosticsSolver", kb_loader)
        self._load("plan", "solver_trajectory", "TrajectorySolver", kb_loader)
        self._load("compare", "solver_comparator", "ComparatorSolver", kb_loader)
        self._load("analytics", "solver_analytics", "AnalyticsSolver", kb_loader)
        self._load("admin", "solver_admin", "AdminSolver", type(kb_loader), data_dir)

    def _load(self, action, module, cls, *args):
        try:
            mod = __import__(f"{__package__}.{module}", fromlist=[cls]) if __package__ else __import__(module, fromlist=[cls])
            self.solvers[action] = getattr(mod, cls)(*args)
        except Exception as e:
            logger.warning("Решатель %s (%s) не подключён: %s: %s", action, module, type(e).__name__, e)

    # ================================================================ вход
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        warnings: List[str] = []
        action = request.get("action") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict) or not isinstance(request.get("params") or {}, dict):
                raise RouterError("BAD_REQUEST", "Запрос должен иметь вид {action, params}, params — объект")
            params = request.get("params") or {}

            if action not in ACTIONS:                                           # этап 1
                raise RouterError("UNKNOWN_ACTION", f"Неизвестное действие: {action}",
                                  {"available_actions": list(ACTIONS)})
            if action not in self.solvers:
                raise RouterError("SOLVER_UNAVAILABLE", f"Решатель «{action}» не подключён")

            # этапы 2–4: валидация + вызов решателя (if/elif по action)
            if action == "diagnose":
                status, data, summary = self._diagnose(params)
            elif action == "plan":
                status, data, summary = self._plan(params)
            elif action == "compare":
                status, data, summary = self._compare(params)
            elif action == "analytics":
                status, data, summary = self._analytics(params, warnings)
            else:  # admin
                status, data, summary = self._admin()

            explanation = {"summary": summary, "used_concepts": sorted(self._collect_ids(data))[:200]}
            return self._response(status, action, t0, warnings, data=data, explanation=explanation)
        except RouterError as e:
            return self._response("error", action, t0, warnings,
                                  error={"code": e.code, "message": e.message, "details": e.details})
        except Exception as e:                       # сбой внутри решателя: в лог, клиенту — штатный ответ
            logger.exception("Сбой решателя %s", action)
            return self._response("error", action, t0, warnings,
                                  error={"code": "INTERNAL_ERROR", "message": "Внутренняя ошибка решателя",
                                         "details": f"{type(e).__name__}: {e}"})

    # ======================================================== действия
    def _diagnose(self, p):
        """Сценарий 4. Без answers -> need_input + вопросы; с answers -> план."""
        solver = self.solvers["diagnose"]
        target = self._concept(p, "target")
        answers = p.get("answers")
        if answers is not None and not isinstance(answers, dict):
            raise RouterError("BAD_PARAM_TYPE", "«answers» должен быть объектом {concept_id: ответ}")

        result, ctx = solver.start(target)
        if result is not None:                                   # цель без пререквизитов
            return "success", result, result.get("message", "")
        if not answers:
            questions = []
            for q in ctx.questions:
                questions.append({"concept_id": q.concept_id, "term": q.term, "text": q.text,
                                  "kind": q.kind, "options": q.options})   # correct_index клиенту не отдаём
            data = {"target_id": ctx.target_id, "questions": questions,
                    "answer_format": "{concept_id: номер варианта (0 = не знаю) | да/нет}"}
            return "need_input", data, "Для построения плана нужны ответы на проверочные вопросы."
        result = solver.finish(ctx, answers)
        return "success", result, result.get("message", "")

    def _plan(self, p):
        """Сценарий 5. gaps — список пробелов, target — необязательная цель."""
        solver = self.solvers["plan"]
        gaps = self._concept_list(p, "gaps")
        target = self._concept(p, "target") if p.get("target") else None
        if not gaps:
            return "success", {"plan": [], "recommendations": []}, "Пробелов нет — траектория не нужна."
        try:
            plan = solver.build_learning_plan(gaps, target)
        except ValueError as e:                                  # цикл в пререквизитах
            raise RouterError("CYCLE_DETECTED", "Нарушена ацикличность иерархии", str(e))
        recs = solver.generate_recommendations(plan)
        return "success", {"plan": plan, "recommendations": recs}, f"Шагов в плане: {len(plan)}."

    def _compare(self, p):
        """Сценарий 6. concept_1, concept_2 — ID или термины."""
        c1, c2 = self._concept(p, "concept_1"), self._concept(p, "concept_2")
        result = self.solvers["compare"].compare_by_id(c1, c2)
        return "success", result, result.get("message", "")

    def _analytics(self, p, warnings):
        """Сценарий 8. student_models — список наборов concept_id."""
        models = p.get("student_models")
        if models is None:
            raise RouterError("MISSING_PARAM", "Отсутствует «student_models»", {"missing": "student_models"})
        if not isinstance(models, (list, tuple)) or any(
                isinstance(m, (str, bytes)) or not isinstance(m, (list, tuple, set, frozenset)) for m in models):
            raise RouterError("BAD_PARAM_TYPE", "«student_models» должен быть списком наборов concept_id")
        known_models = []
        for i, m in enumerate(models):
            known = {c for c in m if isinstance(c, str) and c in self.loader.concepts_by_id}
            if len(known) != len(set(m)):
                warnings.append(f"student_models[{i}]: ссылки на неизвестные концепты исключены")
            known_models.append(known)

        targets = self._concept_list(p, "target_concepts", required=True)
        theta = p.get("threshold", 0.5)
        if isinstance(theta, bool) or not isinstance(theta, (int, float)):
            raise RouterError("BAD_PARAM_TYPE", "«threshold» должен быть числом")
        if not 0 <= theta <= 1:
            raise RouterError("BAD_PARAM_VALUE", "«threshold» должен быть в диапазоне [0, 1]")

        rows = self.solvers["analytics"].analyze_gaps(known_models, targets, float(theta))
        summary = (f"Концептов с долей пробелов ≥ {theta}: {len(rows)}." if rows
                   else "Групповых пробелов выше порога не выявлено.")
        return "success", rows, summary

    def _admin(self):
        """Сценарий 7."""
        result = self.solvers["admin"].run_validation()
        if result.get("status") == "error":
            raise RouterError(result.get("error_code", "VALIDATION_FAILED"),
                              result.get("message", "Ошибка валидации"), result.get("details"))
        return "success", result, result.get("message", "")

    # ===================================================== валидация
    def _concept(self, params, name) -> str:
        """Один концепт: ID или термин -> concept_id."""
        if params.get(name) is None:
            raise RouterError("MISSING_PARAM", f"Отсутствует обязательный параметр «{name}»", {"missing": name})
        return self._resolve(name, params[name])

    def _concept_list(self, params, name, required=True) -> List[str]:
        value = params.get(name)
        if value is None:
            if required:
                raise RouterError("MISSING_PARAM", f"Отсутствует обязательный параметр «{name}»", {"missing": name})
            return []
        if not isinstance(value, (list, tuple, set)):
            raise RouterError("BAD_PARAM_TYPE", f"«{name}» должен быть списком концептов")
        ids = []
        for v in value:
            cid = self._resolve(name, v)
            if cid not in ids:
                ids.append(cid)
        return ids

    def _resolve(self, name, value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RouterError("BAD_PARAM_TYPE", f"«{name}»: ожидается непустая строка (ID или термин)")
        v = value.strip()
        if self.ID_PATTERN.match(v.upper()) and v.upper() in self.loader.concepts_by_id:   # O(1)
            return v.upper()
        if self.ID_LIKE.match(v) and not self.ID_PATTERN.match(v.upper()):
            raise RouterError("BAD_ID_FORMAT", f"Неверный формат идентификатора: {v}. Ожидается Cxx или CLxx.")
        hits = self.loader.search_by_term(v)
        if len(hits) == 1:
            return hits[0]["concept_id"]
        if len(hits) > 1:
            raise RouterError("AMBIGUOUS_CONCEPT", f"Термину «{v}» соответствует несколько концептов",
                              {"candidates": [{"concept_id": h["concept_id"], "topic_id": h.get("topic_id")} for h in hits]})
        similar = difflib.get_close_matches(v.lower(), list(self.loader.concepts_by_term), n=5, cutoff=0.6)
        raise RouterError("CONCEPT_NOT_FOUND", f"Концепт «{v}» не найден в базе знаний", {"similar": similar})

    # ======================================================== утилиты
    def _collect_ids(self, data) -> set:
        """Все concept_id в результате — для поля explanation.used_concepts."""
        found, stack = set(), [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                stack.extend(x.values())
            elif isinstance(x, (list, tuple, set)):
                stack.extend(x)
            elif isinstance(x, str) and x in self.loader.concepts_by_id:
                found.add(x)
        return found

    def _response(self, status, action, t0, warnings, data=None, explanation=None, error=None):
        return {
            "status": status, "action": action, "data": data,
            "explanation": explanation, "error": error,
            "metadata": {"elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
                         "kb_concepts": len(self.loader.concepts_by_id), "warnings": warnings},
        }
