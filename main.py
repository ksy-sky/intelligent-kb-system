"""
main.py — точка входа интеллектуальной обучающей системы по дисциплине ПиОИвИС (5 семестр).
Структура сценариев:
Сценарий 1 — Самостоятельное изучение теоретического материала  (scenario_study.py) [Студент]
Сценарий 2 — Использование глоссария                          (scenario_glossary.py) [Студент]
Сценарий 3 — Работа с интеллектуальным ассистентом             (scenario_assistant.py) [Студент]
Сценарий 4 — Адаптивная диагностика пробелов                   (solver_diagnostics.py) [Студент, Дана]
Сценарий 5 — Построение траектории и рекомендации              (solver_trajectory.py) [Студент, Аня]
Сценарий 6 — Сравнение понятий: чем отличаются (solver_comparator.py) [Студент, Юля]
Сценарий 7 — Администрирование и валидация базы знаний         (solver_admin.py) [Преподаватель, Ксюша]
Сценарий 8 — Аналитика успеваемости и выявление пробелов       (solver_analytics.py) [Преподаватель, Ксюша]
Архитектура:
Сценарии 7 и 8 работают через API-шлюз (solver_router.py), реализующий паттерн Facade.
Сценарии 1-6 используют прямые вызовы (будут переведены на роутер в следующих итерациях).
"""
import os
import sys
import textwrap
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario
from src.solver_router import SolverRouter
from src.results_store import save_diagnostic, list_targets, load_latest, to_analytics_params

# БЕЗОПАСНЫЙ ИМПОРТ ВАШЕГО МОДУЛЯ ПЛАНИРОВЩИКА
try:
    from src.solver_trajectory import TrajectorySolver
except ImportError:
    print(" Внимание: solver_trajectory.py не найден или содержит ошибки.")
    TrajectorySolver = None

# Решатель диагностики (Сценарий 4)
try:
    from src.solver_diagnostics import DiagnosticsSolver
except Exception as e:
    print(f" Внимание: не удалось загрузить src/solver_diagnostics.py: {type(e).__name__}: {e}")
    DiagnosticsSolver = None

# Решатель семантического компаратора (Сценарий 6)
try:
    from src.solver_comparator import ComparatorSolver
except Exception as e:
    print(f" Внимание: не удалось загрузить src/solver_comparator.py: {type(e).__name__}: {e}")
    ComparatorSolver = None
        


#================= ПУТИ К ФАЙЛАМ =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_FILES = [
    os.path.join(BASE_DIR, "data", "glossary_T01.json"),
    os.path.join(BASE_DIR, "data", "glossary_T02.json"),
    os.path.join(BASE_DIR, "data", "glossary_T03.json"),
    os.path.join(BASE_DIR, "data", "glossary_T04.json"),
    os.path.join(BASE_DIR, "data", "glossary_T05.json"),
    os.path.join(BASE_DIR, "data", "glossary_T06.json"),
    os.path.join(BASE_DIR, "data", "glossary_T07.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs_t1.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs_t2.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs_t3.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs_t4.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs_t5.json"),
]

#=================================================================
#ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
#=================================================================
def print_separator(title: str = ""):
    """Вывод разделителя с опциональным заголовком."""
    line = "=" * 60
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)

def show_glossary_result(result: dict):
    """Форматированный вывод карточки термина (Сценарий 2)."""
    if result["found"]:
        print(f"\n  Термин:     {result['term']}")
        print(f"  ID:         {result['concept_id']}")
        print(f"  Topic ID:   {result['topic_id']}")
        print(f"  Раздел:     {result['topic_title']}")
        source_label = "Теория" if result["source"] == "theory" else "Лабораторные"
        print(f"  Источник:   {source_label}")
        print(f"  Определение: {result['definition']}")
        if result["relations"]:
            print("  Связи:")
            for rel_type, targets in result["relations"].items():
                targets_str = ", ".join(str(t) for t in targets)
                print(f"    - {rel_type}: {targets_str}")
        if result["examples"]:
            print(f"  Пример:     {result['examples'][0]}")
    else:
        print(f"\n  Термин '{result['term']}' не найден в базе знаний.")
        if result.get("similar_terms"):
            print(f"  Похожие термины: {', '.join(result['similar_terms'])}")
        else:
            print("  Похожих терминов не найдено.")

def print_router_error(resp: dict):
    """Единый вывод ошибки роутера."""
    err = resp["error"]
    print(f"\n  Ошибка [{err['code']}]: {err['message']}")
    d = err.get("details")
    if isinstance(d, dict) and d.get("similar"):
        print(f"  Возможно, вы имели в виду: {', '.join(d['similar'])}")
    elif isinstance(d, dict) and d.get("candidates"):
        print("  Уточните концепт (ID): " + ", ".join(
            f"{c['concept_id']} ({c.get('source', c.get('topic_id', ''))})" for c in d["candidates"]))

def choose_candidate(err: dict):
    """
    Термину соответствует несколько концептов (теория и/или лабораторный практикум):
    показывает список и просит выбрать. Возвращает concept_id или None (отмена).
    """
    det = err.get("details") or {}
    cands = det.get("candidates", [])
    print(f"\n  Термину «{det.get('value', '')}» соответствует несколько концептов:")
    for i, c in enumerate(cands, 1):
        print(f"    {i}. [{c['concept_id']}] {c['term']} — {c['source']} ({c['topic_id']}: {c['topic_title']})")
        if c.get("definition"):
            print(_wrap(c["definition"], "         "))
    valid = {c["concept_id"] for c in cands}
    while True:
        try:
            ans = input(f"  Выберите номер (1-{len(cands)}) или ID, Enter — отмена: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not ans:
            return None
        if ans.isdigit() and 1 <= int(ans) <= len(cands):
            return cands[int(ans) - 1]["concept_id"]
        if ans.upper() in valid:
            return ans.upper()
        print("  Неверный выбор.")


def request_with_choice(router: SolverRouter, action: str, params: dict):
    """
    Выполняет запрос; если термин неоднозначен, даёт пользователю выбрать ID и повторяет запрос.
    Возвращает (ответ, параметры_с_выбранными_ID); при отмене выбора ответ — ошибка AMBIGUOUS_CONCEPT.
    """
    params = dict(params)
    for _ in range(10):                                  # защита от бесконечного цикла
        resp = router.handle_request({"action": action, "params": params})
        err = resp.get("error") or {}
        det = err.get("details") if isinstance(err.get("details"), dict) else {}
        if err.get("code") != "AMBIGUOUS_CONCEPT" or not det.get("candidates"):
            return resp, params
        chosen = choose_candidate(err)
        if chosen is None:
            return resp, params
        name, value = det.get("param"), det.get("value")
        cur = params.get(name)
        if isinstance(cur, str):
            params[name] = chosen
        elif isinstance(cur, (list, tuple)):
            params[name] = [chosen if isinstance(x, str) and x.strip() == value else x for x in cur]
        else:
            return resp, params
    return resp, params


def _wrap(text: str, indent: str = "      ") -> str:
    """Перенос длинных строк определений по ширине консоли."""
    return textwrap.fill(text, width=76, initial_indent=indent, subsequent_indent=indent)


def _show_comparator_result(result: dict):
    """Сравнительная карточка двух понятий (Сценарий 6)."""
    lines = result["message"].split("\n")
    if result["status"] == "identical":
        print("\n  " + lines[0])
        return
    print("\n  " + "\n  ".join(l for l in lines if not l.startswith("Близость")))   # итог близости — ниже

    rel_titles = {
        "ancestor": "надкласс — подкласс", "descendant": "надкласс — подкласс",
        "siblings": "«соседи» (общий надкласс)", "cousins": "одна ветка иерархии",
        "part_whole": "часть — целое", "common_whole": "элементы одного целого",
        "linked": "связаны по смыслу", "text_similar": "похожие определения",
        "same_topic": "один раздел, связей нет", "unrelated": "не связаны",
    }
    print(f"  Тип родства: {rel_titles.get(result['relationship'], result['relationship'])}")

    if result.get("path_text"):
        print(f"\n  Путь по иерархии: {result['path_text']}")
    if result.get("lca_id"):
        layer = "по is-a" if result["lca_layer"] == "isa" else "по частям/целому"
        print(f"  LCA ({layer}): [{result['lca_id']}] {result['lca_term']}  "
              f"(глубина {result['depth_lca']}; до C1: {result['distance_1']}, до C2: {result['distance_2']})")
        if result["wu_palmer"]:
            print(f"  Ву–Палмер по is-a: {result['wu_palmer']}")
    p = result["similarity_parts"]
    print(f"  Близость: {result['semantic_similarity']} — {result['similarity_level']}  "
          f"[иерархия {p['hierarchy']} · связи {p['context']} · лексика {p['lexical']}]")

    links = result.get("direct_links", [])
    if len(links) == 2 and links[0]["relation"] == links[1]["relation"]:      # симметричная связь
        print(f"  Прямая связь: «{links[0]['from_term']}» ⇄ «{links[0]['to_term']}»: {links[0]['relation']}")
    else:
        for link in links:
            print(f"  Прямая связь: «{link['from_term']}» —{link['relation']}→ «{link['to_term']}»")
    if result.get("contrasted"):
        print("  ⚠ В базе знаний эти понятия прямо противопоставлены.")

    com = result["common"]
    print("\n  ОБЩЕЕ")
    shown = False
    if com["same_topic"]:
        print(f"    • один раздел: {com['topic_id']}"); shown = True
    if len(result["common_ancestors"]) > 1 or (result["common_ancestors"] and result["relationship"] in ("siblings", "cousins", "common_whole")):
        print("    • общие предки: " + ", ".join(a["term"] for a in result["common_ancestors"])); shown = True
    if com["relation_types"]:
        print("    • одинаково описаны через: " + ", ".join(com["relation_types"])); shown = True
    if com["linked_concepts"]:
        print("    • общие связи: " + ", ".join(c["term"] for c in com["linked_concepts"])); shown = True
    if com["keywords"]:
        print("    • общие слова определений: " + ", ".join(com["keywords"])); shown = True
    if not shown:
        print("    — явного сходства в базе знаний не найдено")

    print("\n  РАЗЛИЧИЯ")
    for n in ("1", "2"):
        d = result["differences"][f"concept_{n}"]
        print(f"    [{d['concept_id']}] {d['term']}  ({d['topic_id']}: {d['topic_title']})")
        if d["definition"]:
            print(_wrap(d["definition"]))
        if d["superclasses"]:
            print(f"      Надкласс: {', '.join(d['superclasses'])}")
        if d["subclasses"]:
            print(f"      Подклассы: {', '.join(d['subclasses'])}")
        if d["parts"]:
            print(f"      Состоит из: {', '.join(d['parts'])}")
        if d["examples"]:
            print(f"      Пример: {d['examples'][0][:110]}")
        if d["distinctive_words"]:
            print(f"      Только здесь: {', '.join(d['distinctive_words'])}")

    print(f"\n  КАК НЕ ПЕРЕПУТАТЬ\n{_wrap(result['tip'], '    ')}")
    study = result["study"]
    print("\n  ПОРЯДОК ИЗУЧЕНИЯ: " + " → ".join(f"{x['term']}" for x in study["order"]))
    if study["labs"]:
        print(f"  Лабораторные работы: {', '.join(study['labs'])}")


#=================================================================
#СЦЕНАРИЙ 1 — Самостоятельное изучение теоретического материала
#=================================================================
def run_scenario1(loader: KnowledgeBaseLoader):
    """Интерактивный просмотр теоретического материала по разделам."""
    from src.scenario_study import StudyScenario
    scenario = StudyScenario(loader)
    print_separator("СЦЕНАРИЙ 1: САМОСТОЯТЕЛЬНОЕ ИЗУЧЕНИЕ МАТЕРИАЛА [Студент]")
    print("  - Введите ID раздела (T01..T07, L01..L05) — список понятий")
    print("  - Введите термин или ID концепта (C001) — карточка")
    print("  - 'q' — возврат в меню\n")
    while True:
        try:
            user_input = input("  Запрос: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "выход", "exit"):
            print("\n  Возврат в меню...\n")
            break
        response = scenario.handle_query(user_input)
        print(response)

#=================================================================
#СЦЕНАРИЙ 2 — Использование глоссария
#=================================================================
def run_scenario2(loader: KnowledgeBaseLoader):
    """Интерактивный поиск терминов в базе знаний дисциплины ПиОИвИС."""
    scenario = GlossaryScenario(loader)
    print_separator("СЦЕНАРИЙ 2: ГЛОССАРИЙ ПиОИвИС [Студент]")
    print("  Введите термин или его ID (например: онтология / C158).")
    print("  Для выхода введите 'q'.\n")
    while True:
        try:
            user_input = input("  Термин: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if user_input.lower() in ("q", "quit", "выход", "exit"):
            break
        if not user_input:
            print("  Введите термин.\n")
            continue
        result = scenario.search_term(user_input)
        show_glossary_result(result)
        print()

#=================================================================
#СЦЕНАРИЙ 3 — Работа с интеллектуальным ассистентом
#=================================================================
def run_scenario3(loader: KnowledgeBaseLoader = None):
    """Запуск интеллектуального ассистента на базе LLM."""
    from src.scenario_assistant import run_scenario3_assistant
    run_scenario3_assistant()

#=================================================================
#СЦЕНАРИЙ 4 — Адаптивная диагностика пробелов (Дана)
#=================================================================
def ask_diagnostic_question(index: int, total: int, q) -> str:
    """Задаёт один проверочный вопрос в консоли. Пустой ввод = нет ответа."""
    print(f"\n  Вопрос {index}/{total}: {q.text}")
    if q.kind == "choice":
        for i, opt in enumerate(q.options, 1):
            print(f"    {i}. {opt}")
        print("    0. Не знаю")
        prompt = "  Ваш ответ (номер, Enter — пропустить): "
    else:
        prompt = "  Ваш ответ (да/нет, Enter — пропустить): "
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return ""

def show_diagnostics_result(result: dict):
    """Форматированный вывод результата диагностики (Сценарий 4)."""
    print(f"\n  {result['message']}")
    if result["status"] == "error":
        if result["similar"]:
            print("  Похожие концепты:")
            for s in result["similar"]:
                print(f"    - [{s['concept_id']}] {s['term']}")
        return
    if result["status"] == "plan_built":
        print(f"  Освоено: {len(result['mastered'])}, пробелов: {len(result['gaps'])}")
        if result["unanswered"]:
            print(f"  Без ответа (считаются неосвоенными): {', '.join(result['unanswered'])}")
        print()
    for idx, step in enumerate(result["plan"], 1):
        mark = "  ← цель" if step["is_target"] else ""
        print(f"    {idx}. [{step['concept_id']}] {step['term']}{mark}")
        print(f"       Обоснование: {step['reason']}")
    if result["cycle"]:
        print(f"\n  Внимание: обнаружен цикл зависимостей среди: {', '.join(result['cycle'])}")
    if result["status"] == "plan_built":
        print("\n  Подробные материалы по пробелам — в сценарии 5 "
              f"(ID: {', '.join(result['gaps'])}).")

def run_scenario4(router: SolverRouter):
    """Адаптивная диагностика пробелов и построение учебной траектории (через роутер)."""
    print_separator("СЦЕНАРИЙ 4: АДАПТИВНАЯ ДИАГНОСТИКА ПРОБЕЛОВ [Студент]")
    target = input("  Введите целевой концепт (ID или термин, например C042): ").strip()
    student = input("  Ваше имя или псевдоним (для статистики группы): ").strip()

    resp, params = request_with_choice(router, "diagnose", {"target": target})
    target = params["target"]                # мог быть уточнён выбором ID
    if resp["status"] == "error":
        print_router_error(resp)
        return
    if resp["status"] == "success":          # цель без пререквизитов
        show_diagnostics_result(resp["data"])
        return

    questions = resp["data"]["questions"]    # status == "need_input"
    total = len(questions)
    print(f"\n  Найдено пререквизитов: {total}.")
    print("  Ответьте на проверочные вопросы (Enter — пропустить вопрос).")
    answers = {}
    for i, q in enumerate(questions, 1):
        answers[q["concept_id"]] = ask_diagnostic_question(i, total, SimpleNamespace(**q))

    resp = router.handle_request({"action": "diagnose", "params": {"target": target, "answers": answers}})
    if resp["status"] == "error":
        print_router_error(resp)
    else:
        show_diagnostics_result(resp["data"])
    if save_diagnostic(student, resp["data"]):
        print("\n  Результат сохранён для аналитики преподавателя.")
#=================================================================
#СЦЕНАРИЙ 5 — Построение траектории и рекомендации (Аня)
#=================================================================
def run_scenario5(router: SolverRouter):
    print_separator("СЦЕНАРИЙ 5: ПЛАНИРОВЩИК И РЕКОМЕНДАЦИИ [Студент]")
    missing_input = input("  Введите список проблемных ID через запятую (например, CL152,CL153): ").strip()
    missing_ids = [m.strip() for m in missing_input.split(",") if m.strip()]

    resp, _ = request_with_choice(router, "plan", {"gaps": missing_ids})
    if resp["status"] == "error":
        print_router_error(resp)
        return
    plan, recs = resp["data"]["plan"], resp["data"]["recommendations"]
    if not plan:
        print("\n  Все указанные концепты уже освоены или отсутствуют в БЗ.")
        return
    recs_by_id = {r['concept_id']: r for r in recs}

    print(f"\n  Рекомендованный план изучения ({len(plan)} шагов):\n")

    for idx, step in enumerate(plan, 1):
        rec = recs_by_id.get(step['concept_id'])

        print(f"  {'─' * 58}")
        print(f"  ШАГ {idx}. [{step['concept_id']}] {step['term']}")
        print(f"  Причина включения: {step['reason']}")

        if not rec:
            continue

        if rec.get('topic_title'):
            print(f"\n  Раздел: {rec['topic_id']} — {rec['topic_title']}")

        if rec.get('criticality', 0) > 0:
            print(f"  Критичность: от этого понятия зависит {rec['criticality']} понятий в БЗ")

        if rec['definition']:
            inh = f" (унаследовано от «{rec['inherited_from']}»)" if rec['inherited_from'] else ""
            print(f"  Определение{inh}:")
            print(f"    {rec['definition']}")

        if rec.get('examples'):
            print(f"  Примеры:")
            for ex in rec['examples']:
                print(f"    • {ex}")

        if rec.get('related'):
            print(f"  Связано с:")
            for rel_type, terms in rec['related'].items():
                print(f"    {rel_type}: {', '.join(terms)}")
        elif rec.get('similar_by_text'):
            print(f"  Явных связей в БЗ нет. Похожие по смыслу понятия:")
            for sim in rec['similar_by_text']:
                print(f"    • {sim['term']} (сходство: {sim['similarity']})")

        if rec['lab_ids']:
            print(f"  Лабораторные работы: {', '.join(rec['lab_ids'])}")

    print(f"  {'─' * 58}")


#=================================================================
#СЦЕНАРИЙ 6 — Семантический компаратор / LCA (Юля)
#=================================================================

def run_scenario6(router: SolverRouter):
    """Сравнение двух понятий: «чем отличаются A и B» (через роутер)."""
    print_separator("СЦЕНАРИЙ 6: ЧЕМ ОТЛИЧАЮТСЯ ПОНЯТИЯ? [Студент]")
    print("  Понятия можно вводить как ID (C040), так и термином. Пустой ввод — назад в меню.\n")
    while True:
        try:
            c1 = input("  Первое понятие: ").strip()
            if not c1:
                return
            c2 = input("  Второе понятие: ").strip()
            if not c2:
                return
        except (KeyboardInterrupt, EOFError):
            return
        resp, _ = request_with_choice(router, "compare", {"concept_1": c1, "concept_2": c2})
        if resp["status"] == "error":
            print_router_error(resp)
        else:
            _show_comparator_result(resp["data"])
        print()

#=================================================================
#СЦЕНАРИЙ 7 — Администрирование и валидация БЗ (Ксюша, через роутер)
#=================================================================
def run_scenario7(solver_router: SolverRouter):
    """Администрирование и валидация базы знаний через API-шлюз."""
    print_separator("СЦЕНАРИЙ 7: АДМИНИСТРИРОВАНИЕ И ВАЛИДАЦИЯ БЗ [Преподаватель]")
    print("  Проверка: уникальность concept_id, обязательные поля, ссылки relations, ацикличность 'надкласс'\n")
    resp = solver_router.handle_request({"action": "admin", "params": {}})
    if resp["status"] == "success":
        data = resp["data"]
        print("  РЕЗУЛЬТАТ: УСПЕХ")
        print(f"    Проверено файлов: {data['files_checked']}")
        print(f"    Всего концептов: {data['stats']['concepts_count']}")
        print(f"    Всего разделов: {data['stats']['topics_count']}")
    else:
        err = resp["error"]
        print("  РЕЗУЛЬТАТ: ОШИБКА ВАЛИДАЦИИ")
        print(f"    Код ошибки: {err['code']}")
        print(f"    Описание: {err['message']}")
        if err.get("details"):
            print(f"    Детали: {err['details']}")

#=================================================================
def run_scenario8(solver_router: SolverRouter):
    """Аналитика успеваемости и выявление групповых пробелов через API-шлюз."""
    print_separator("СЦЕНАРИЙ 8: АНАЛИТИКА УСПЕВАЕМОСТИ ГРУППЫ [Преподаватель]")
    targets = list_targets()
    if not targets:
        print("  Данных диагностики пока нет. Пусть студенты пройдут сценарий 4.")
        return
    print("  Цели, по которым есть результаты:")
    for tid, n in targets.items():
        print(f"    {tid} — студентов: {n}")
    target_id = input("  Введите ID цели: ").strip().upper()
    records = load_latest(target_id)
    resp = solver_router.handle_request({
        "action": "analytics",
        "params": to_analytics_params(records, threshold=0.3),
    })
    if resp["status"] != "success":
        print(f"  Ошибка [{resp['error']['code']}]: {resp['error']['message']}")
        return
    for w in resp["metadata"]["warnings"]:
        print(f"  Предупреждение: {w}")
    gaps = resp["data"]
    if gaps:
        print(f"  Найдено {len(gaps)} концептов с групповыми пробелами:\n")
        print(f"  {'Концепт':<20} {'Пробел':<10} {'Студентов':<15}")
        print("  " + "-" * 55)
        for g in gaps:
            print(f"    {g['term']:<20} {g['gap_ratio']*100:.0f}%{'':<5} {g['students_with_gap']}/{g['total_students']}")
        print("\n  Рекомендация: повторите эти темы на следующей лекции.")
    else:
        print("  Групповые пробелы не обнаружены.")

#=================================================================
#ГЛАВНОЕ МЕНЮ
#=================================================================
def print_menu():
    """Вывод главного меню системы."""
    print_separator("ИНТЕЛЛЕКТУАЛЬНАЯ ОБУЧАЮЩАЯ СИСТЕМА ПиОИвИС (5 семестр)")
    print("  Выберите сценарий:\n")
    print("  --- Функционал для Студента ---")
    print("  1 — Изучение теоретического материала")
    print("  2 — Глоссарий / Поиск термина")
    print("  3 — Интеллектуальный ассистент")
    print("  4 — Адаптивная диагностика пробелов")
    print("  5 — Построение траектории и рекомендации")
    print("  6 — Сравнение двух понятий (чем отличаются)")
    print("\n  --- Функционал для Преподавателя ---")
    print("  7 — Администрирование и валидация базы знаний")
    print("  8 — Аналитика успеваемости и выявление пробелов")
    print("\n  q — Выход\n")

def main():
    """Точка входа в систему."""
    # Инициализация базы знаний при старте — один раз для всех сценариев
    try:
        loader = KnowledgeBaseLoader(KB_FILES)
        summary = loader.load()
        # Используем правильные ключи, которые возвращает ваш лоадер
        print(f"База знаний загружена: {summary['concepts_count']} концептов, "
              f"{summary['topics_count']} разделов.")
    except Exception as e:
        print(f"Ошибка загрузки базы знаний: {e}")
        print("Система не может быть запущена без базы знаний.")
        return

    # Инициализация API-шлюза (маршрутизатора решателей) для сценариев 7 и 8
    solver_router = SolverRouter(loader)

    # Реестр сценариев
    scenarios = {
        "1": lambda: run_scenario1(loader),
        "2": lambda: run_scenario2(loader),
        "3": lambda: run_scenario3(loader),
        "4": lambda: run_scenario4(solver_router),
        "5": lambda: run_scenario5(solver_router),
        "6": lambda: run_scenario6(solver_router),
        "7": lambda: run_scenario7(solver_router),
        "8": lambda: run_scenario8(solver_router),
    }

    while True:
        print_menu()
        try:
            choice = input("  Ваш выбор: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            choice = "q"
        if choice in ("q", "quit", "выход", "exit"):
            print("\n  До свидания!\n")
            break
        elif choice in scenarios:
            scenarios[choice]()
        else:
            print("\n  Неверный выбор. Введите 1-8 или q.\n")

if __name__ == "__main__":
    main()
