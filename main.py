"""
main.py — точка входа интеллектуальной обучающей системы по дисциплине ПиОИвИС (5 семестр).
Структура сценариев:
Сценарий 1 — Самостоятельное изучение теоретического материала  (scenario_study.py) [Студент]
Сценарий 2 — Использование глоссария                          (scenario_glossary.py) [Студент]
Сценарий 3 — Работа с интеллектуальным ассистентом             (scenario_assistant.py) [Студент]
Сценарий 4 — Адаптивная диагностика пробелов                   (solver_diagnostics.py) [Студент, Дана]
Сценарий 5 — Построение траектории и рекомендации              (solver_trajectory.py) [Студент, Аня]
Сценарий 6 — Семантический компаратор (LCA)                    (solver_comparator.py) [Студент, Юля]
Сценарий 7 — Администрирование и валидация базы знаний         (solver_admin.py) [Преподаватель, Ксюша]
Сценарий 8 — Аналитика успеваемости и выявление пробелов       (solver_analytics.py) [Преподаватель, Ксюша]
Архитектура:
Сценарии 7 и 8 работают через API-шлюз (solver_router.py), реализующий паттерн Facade.
Сценарии 1-6 используют прямые вызовы (будут переведены на роутер в следующих итерациях).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario
from src.solver_router import SolverRouter

# БЕЗОПАСНЫЙ ИМПОРТ ВАШЕГО МОДУЛЯ ПЛАНИРОВЩИКА
try:
    from src.solver_trajectory import TrajectorySolver
except ImportError:
    print("⚠️ Внимание: solver_trajectory.py не найден или содержит ошибки.")
    TrajectorySolver = None

# Решатель диагностики (Сценарий 4)
try:
    from src.solver_diagnostics import DiagnosticsSolver
except Exception as e:
    print(f"⚠️ Внимание: не удалось загрузить src/solver_diagnostics.py: {type(e).__name__}: {e}")
    DiagnosticsSolver = None

# Заглушки для остальных решателей (пока они пустые или не готовы к интеграции)
def find_lca(id1, id2, loader):
    return "[Заглушка] solver_comparator.py"

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

def run_scenario4(loader: KnowledgeBaseLoader):
    """Адаптивная диагностика пробелов и построение учебной траектории."""
    if DiagnosticsSolver is None:
        print("\n  Ошибка: Модуль диагностики не загружен.\n")
        return

    print_separator("СЦЕНАРИЙ 4: АДАПТИВНАЯ ДИАГНОСТИКА ПРОБЕЛОВ [Студент]")
    target = input("  Введите целевой концепт (ID или термин, например C042): ").strip()

    solver = DiagnosticsSolver(loader)
    result, ctx = solver.start(target)
    if result is not None:       # ошибка или цель без пререквизитов
        show_diagnostics_result(result)
        return

    total = len(ctx.questions)
    print(f"\n  Для концепта «{solver._term(ctx.target_id)}» найдено пререквизитов: {total}.")
    print("  Ответьте на проверочные вопросы (Enter — пропустить вопрос).")
    answers = {}
    for i, q in enumerate(ctx.questions, 1):
        answers[q.concept_id] = ask_diagnostic_question(i, total, q)

    show_diagnostics_result(solver.finish(ctx, answers))

#=================================================================
#СЦЕНАРИЙ 5 — Построение траектории и рекомендации (Аня)
#=================================================================
def run_scenario5(loader: KnowledgeBaseLoader):
    """Построение индивидуальной учебной траектории и формирование рекомендаций."""
    if TrajectorySolver is None:
        print("\n  Ошибка: Модуль планировщика не загружен.\n")
        return

    print_separator("СЦЕНАРИЙ 5: ПЛАНИРОВЩИК И РЕКОМЕНДАЦИИ [Студент]")
    missing_input = input("  Введите список проблемных ID через запятую (например, C010, C015): ").strip()
    missing_ids = [m.strip() for m in missing_input.split(",")] if missing_input else []
    
    solver = TrajectorySolver(loader)
    
    try:
        plan = solver.build_learning_plan(missing_ids)
        if not plan:
            print("\n  Все указанные концепты уже освоены или отсутствуют в БЗ.")
            return
            
        print(f"\n  Рекомендованный план изучения ({len(plan)} шагов):")
        for idx, step in enumerate(plan, 1):
            print(f"    {idx}. [{step['concept_id']}] {step['term']}")
            print(f"       Причина: {step['reason']}")
            
        # Формирование рекомендаций
        recs = solver.generate_recommendations(plan)
        print(f"\n  Учебные материалы:")
        for rec in recs:
            print(f"    • {rec['term']}:")
            if rec['definition']:
                inh = f" (унаследовано от {rec['inherited_from']})" if rec['inherited_from'] else ""
                print(f"      Определение{inh}: {rec['definition']}")
            if rec['lab_ids']:
                print(f"      Лабораторные: {', '.join(rec['lab_ids'])}")
                
    except ValueError as e:
        print(f"\n  Ошибка построения траектории: {e}")

#=================================================================
#СЦЕНАРИЙ 6 — Семантический компаратор / LCA (Юля)
#=================================================================
def run_scenario6(loader: KnowledgeBaseLoader):
    """Семантическое сравнение двух концептов через поиск ближайшего общего предка (LCA)."""
    print_separator("СЦЕНАРИЙ 6: СЕМАНТИЧЕСКИЙ КОМПАРАТОР (LCA) [Студент]")
    id1 = input("  Введите ID первого концепта (например, C040): ").strip()
    id2 = input("  Введите ID второго концепта (например, C042): ").strip()
    lca = find_lca(id1, id2, loader)
    if lca:
        lca_concept = loader.concepts_by_id.get(lca, {})
        print(f"\n  Ближайший общий предок (LCA): [{lca}] {lca_concept.get('term', '')}")
    else:
        print("\n  Общий предок не найден.")

#=================================================================
#СЦЕНАРИЙ 7 — Администрирование и валидация БЗ (Ксюша, через роутер)
#=================================================================
def run_scenario7(solver_router: SolverRouter):
    """Администрирование и валидация базы знаний через API-шлюз."""
    print_separator("СЦЕНАРИЙ 7: АДМИНИСТРИРОВАНИЕ И ВАЛИДАЦИЯ БЗ [Преподаватель]")
    print("  Запуск автоматической проверки целостности БЗ: ")
    print("  - Проверка уникальности concept_id ")
    print("  - Проверка обязательных полей ")
    print("  - Проверка ссылочной целостности relations ")
    print("  - Проверка ацикличности иерархии 'надкласс'\n")
    request = {"action": "admin", "params": {}}
    result = solver_router.handle_request(request)
    if result["status"] == "success" and result["data"]["status"] == "success":
        data = result["data"]
        print("  РЕЗУЛЬТАТ: УСПЕХ")
        print(f"    Проверено файлов: {data['files_checked']}")
        print(f"    Всего концептов: {data['stats']['total_concepts']}")
        print(f"    Всего разделов: {data['stats']['total_topics']}")
    else:
        print("  РЕЗУЛЬТАТ: ОШИБКА ВАЛИДАЦИИ")
        print(f"    Код ошибки: {result['data'].get('error_code', 'UNKNOWN')}")
        print(f"    Описание: {result['data'].get('message')}")
        if "details" in result["data"]:
            print(f"    Детали: {result['data']['details']}")

#=================================================================
#СЦЕНАРИЙ 8 — Аналитика успеваемости (Ксюша, через роутер)
#=================================================================
def run_scenario8(solver_router: SolverRouter):
    """Аналитика успеваемости и выявление групповых пробелов через API-шлюз."""
    print_separator("СЦЕНАРИЙ 8: АНАЛИТИКА УСПЕВАЕМОСТИ ГРУППЫ [Преподаватель]")
    print("  Демонстрационный режим с тестовыми данными.\n")
    # Демонстрационные данные: модели знаний студентов (множества освоенных concept_id)
    student_models = [
        {"C001", "C002", "C003"},
        {"C001", "C002"},
        {"C001", "C003"},
        {"C001"},
    ]
    # Целевые концепты для анализа
    target_concepts = ["C001", "C002", "C003"]
    request = {
        "action": "analytics",
        "params": {
            "student_models": student_models,
            "target_concepts": target_concepts,
            "threshold": 0.3  # Порог значимости пробела (30%)
        }
    }
    result = solver_router.handle_request(request)
    if result["status"] == "success":
        gaps = result["data"]["gaps"]
        if gaps:
            print(f"  Найдено {len(gaps)} концептов с групповыми пробелами:\n")
            print(f"  {'Концепт':<20} {'Пробел':<10} {'Студентов':<15}")
            print("  " + "-" * 55)
            for gap in gaps:
                print(f"    {gap['term']:<20} {gap['gap_ratio']*100:.0f}%{'':<5} {gap['students_with_gap']}/{gap['total_students']}")
            print("\n  Рекомендация: повторите эти темы на следующей лекции.")
        else:
            print("  Групповые пробелы не обнаружены.")
    else:
        print(f"  Ошибка: {result.get('message')}")

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
    print("  6 — Семантический компаратор / LCA")
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
        "4": lambda: run_scenario4(loader),
        "5": lambda: run_scenario5(loader),
        "6": lambda: run_scenario6(loader),
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
