"""
main.py — точка входа интеллектуальной обучающей системы по дисциплине ПиОИвИС (5 семестр).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario
from src.kb_validator import KnowledgeBaseValidator

# ================= БЕЗОПАСНЫЙ ИМПОРТ РЕШАТЕЛЕЙ (С ЗАГЛУШКАМИ) =================

try:
    from src.solver_diagnostics import get_missing_prerequisites
except ImportError:
    def get_missing_prerequisites(target_id, mastered_ids, loader):
        return ["[Заглушка] Модуль solver_diagnostics.py еще не заполнен"]

try:
    from src.solver_trajectory import build_learning_plan
except ImportError:
    def build_learning_plan(missing_ids, loader):
        return ["[Заглушка] Модуль solver_trajectory.py еще не заполнен"]

try:
    from src.solver_comparator import find_lca
except ImportError:
    def find_lca(id1, id2, loader):
        return "[Заглушка] Модуль solver_comparator.py еще не заполнен"

try:
    from src.solver_analytics import analyze_group_gaps
except ImportError:
    def analyze_group_gaps(group_data, topic_id, loader):
        return {"[Заглушка] Файл solver_analytics.py пуст": 0}


# ================= ПУТИ К ФАЙЛАМ =================

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


# =================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =================================================================

def print_separator(title: str = ""):
    line = "=" * 55
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)


def show_glossary_result(result: dict):
    """Форматированный вывод карточки термина (Сценарий 2)."""
    if result["found"]:
        print(f"\n Термин:     «{result['term']}»")
        print(f" ID:         {result['concept_id']}")
        print(f" Topic ID:   {result['topic_id']}")
        print(f" Раздел:     {result['topic_title']}")
        source_label = "Теория" if result["source"] == "theory" else "Лабораторные"
        print(f" Источник:   {source_label}")
        print(f" Определение: {result['definition']}")

        if result["relations"]:
            print("   Связи:")
            for rel_type, targets in result["relations"].items():
                targets_str = ", ".join(str(t) for t in targets)
                print(f"      • {rel_type}: {targets_str}")

        if result["examples"]:
            print(f" Пример:     {result['examples'][0]}")
    else:
        print(f"\n Термин «{result['term']}» не найден в базе знаний.")
        if result.get("similar_terms"):
            print(f" Похожие термины: {', '.join(result['similar_terms'])}")
        else:
            print(" Похожих терминов не найдено.")


# =================================================================
# СЦЕНАРИИ
# =================================================================

def run_scenario1(loader: KnowledgeBaseLoader):
    from src.scenario_study import StudyScenario
    scenario = StudyScenario(loader)
    print("\n" + "=" * 55)
    print("  СЦЕНАРИЙ 1: САМОСТОЯТЕЛЬНОЕ ИЗУЧЕНИЕ МАТЕРИАЛА [Студент]")
    print("=" * 55)
    while True:
        try:
            user_input = input("Запрос (или 'q' для выхода): ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input or user_input.lower() in ("q", "quit", "выход", "exit"):
            break
        print(scenario.handle_query(user_input))


def run_scenario2(loader: KnowledgeBaseLoader):
    scenario = GlossaryScenario(loader)
    print_separator("ГЛОССАРИЙ ПиОИвИС [Студент]")
    while True:
        try:
            user_input = input(" Термин (или 'q' для выхода): ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if user_input.lower() in ("q", "quit", "выход", "exit"):
            break
        if user_input:
            show_glossary_result(scenario.search_term(user_input))
            print()


def run_scenario3(loader: KnowledgeBaseLoader = None):
    try:
        from src.scenario_assistant import run_scenario3_assistant
        run_scenario3_assistant()
    except ImportError:
        print("\n[Заглушка] Сценарий 3 пока не реализован.\n")


def run_scenario4(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 4: АДАПТИВНАЯ ДИАГНОСТИКА ПРОБЕЛОВ [Студент]")
    target_id = input("Введите ID целевого концепта (например, C042): ").strip()
    mastered_input = input("Введите ID освоенных через запятую: ").strip()
    mastered_ids = [m.strip() for m in mastered_input.split(",")] if mastered_input else []
    
    missing = get_missing_prerequisites(target_id, mastered_ids, loader)
    print(f"\n Результат диагностики: {missing}")


def run_scenario5(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 5: ПЛАНИРОВЩИК И РЕКОМЕНДАЦИИ [Студент]")
    missing_input = input("Введите список проблемных ID через запятую: ").strip()
    missing_ids = [m.strip() for m in missing_input.split(",")] if missing_input else []
    
    plan = build_learning_plan(missing_ids, loader)
    print(f"\n План изучения: {plan}")


def run_scenario6(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 6: СЕМАНТИЧЕСКИЙ КОМПАРАТОР (LCA) [Студент]")
    id1 = input("Введите ID первого концепта: ").strip()
    id2 = input("Введите ID второго концепта: ").strip()
    
    lca = find_lca(id1, id2, loader)
    print(f"\n Ближайший общий предок (LCA): {lca}")


def run_scenario7(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 7: ВАЛИДАЦИЯ БАЗЫ ЗНАНИЙ [Преподаватель]")
    try:
        validator = KnowledgeBaseValidator(KB_FILES)
        is_valid = validator.validate()
        print("\n [УСПЕХ] База знаний корректна!" if is_valid else "\n [ВНИМАНИЕ] Есть ошибки.")
    except Exception as e:
        print(f"\n Ошибка валидации: {e}")


def run_scenario8(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 8: АНАЛИТИКА УСПЕВАЕМОСТИ ГРУППЫ [Преподаватель]")
    topic_id = input("Введите ID раздела для анализа (например, T07): ").strip()
    group_data = [["C001", "C002"], ["C001"]]
    gaps = analyze_group_gaps(group_data, topic_id, loader)
    print(f"\n Результат аналитики: {gaps}")


# =================================================================
# ГЛАВНОЕ МЕНЮ
# =================================================================

def print_menu():
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
    try:
        loader = KnowledgeBaseLoader(KB_FILES)
        summary = loader.load()
        print(f"База знаний загружена: {summary['concepts_count']} концептов, "
              f"{summary['topics_count']} разделов.")
    except Exception as e:
        print(f"Ошибка загрузки базы знаний: {e}")
        return

    scenarios = {
        "1": lambda: run_scenario1(loader),
        "2": lambda: run_scenario2(loader),
        "3": lambda: run_scenario3(loader),
        "4": lambda: run_scenario4(loader),
        "5": lambda: run_scenario5(loader),
        "6": lambda: run_scenario6(loader),
        "7": lambda: run_scenario7(loader),
        "8": lambda: run_scenario8(loader),
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
