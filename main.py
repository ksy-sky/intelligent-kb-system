"""
main.py — точка входа интеллектуальной обучающей системы по дисциплине ПиОИвИС (5 семестр).

Структура сценариев:
    Сценарий 1 — Самостоятельное изучение теоретического материала  (scenario_study.py)
    Сценарий 2 — Использование глоссария                          (scenario_glossary.py)
    Сценарий 3 — Работа с интеллектуальным ассистентом             (scenario_assistant.py)
    Сценарий 4 — Адаптивная диагностика пробелов                   (solver_diagnostics.py)
    Сценарий 5 — Построение траектории и рекомендации              (solver_trajectory.py)
    Сценарий 6 — Семантический компаратор (LCA)                    (solver_comparator.py)
    Сценарий 8 — Аналитика успеваемости для преподавателя          (solver_analytics.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario

# Импорт новых решателей задач (5 семестр)
from src.solver_diagnostics import get_missing_prerequisites
from src.solver_trajectory import build_learning_plan
from src.solver_comparator import find_lca
from src.solver_analytics import analyze_group_gaps

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
# СЦЕНАРИЙ 1 — Самостоятельное изучение теоретического материала
# =================================================================

def run_scenario1(loader: KnowledgeBaseLoader):
    """Интерактивный просмотр теоретического материала по разделам."""
    from src.scenario_study import StudyScenario
    
    scenario = StudyScenario(loader)

    print("\n" + "=" * 55)
    print("  СЦЕНАРИЙ 1: САМОСТОЯТЕЛЬНОЕ ИЗУЧЕНИЕ МАТЕРИАЛА")
    print("=" * 55)
    print("  - Введите ID раздела (T01..T07, L01..L05) — список понятий")
    print("  - Введите термин или ID концепта (C001) — карточка")
    print("  - 'q' — возврат в меню\n")

    while True:
        try:
            user_input = input("Запрос: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "выход", "exit"):
            print("\n  Возврат в меню...\n")
            break

        response = scenario.handle_query(user_input)
        print(response)


# =================================================================
# СЦЕНАРИЙ 2 — Использование глоссария
# =================================================================

def run_scenario2(loader: KnowledgeBaseLoader):
    """Интерактивный поиск терминов в базе знаний дисциплины ПиОИвИС."""
    scenario = GlossaryScenario(loader)

    print_separator("ГЛОССАРИЙ ПиОИвИС")
    print(" Введите термин или его ID (например: онтология / C158).")
    print(" Для выхода введите 'q'.\n")

    while True:
        try:
            user_input = input(" Термин: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("q", "quit", "выход", "exit"):
            break

        if not user_input:
            print(" Введите термин.\n")
            continue

        result = scenario.search_term(user_input)
        show_glossary_result(result)
        print()


# =================================================================
# СЦЕНАРИЙ 3 — Работа с интеллектуальным ассистентом
# =================================================================

def run_scenario3(loader: KnowledgeBaseLoader = None):
    from src.scenario_assistant import run_scenario3_assistant
    run_scenario3_assistant()  


# =================================================================
# СЦЕНАРИЙ 4 — Адаптивная диагностика пробелов (Дана)
# =================================================================

def run_scenario4(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 4: АДАПТИВНАЯ ДИАГНОСТИКА ПРОБЕЛОВ")
    target_id = input("Введите ID целевого концепта (например, C042): ").strip()
    mastered_input = input("Введите ID освоенных концептов через запятую (например, C001, C002): ").strip()
    mastered_ids = [m.strip() for m in mastered_input.split(",")] if mastered_input else []
    
    missing = get_missing_prerequisites(target_id, mastered_ids, loader)
    print(f"\n Выявленные пробелы в знаниях для концепта {target_id}:")
    print(missing if missing else "Пробелов нет, все пререквизиты освоены!")


# =================================================================
# СЦЕНАРИЙ 5 — Построение траектории и рекомендации (Аня)
# =================================================================

def run_scenario5(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 5: ПЛАНИРОВЩИК И РЕКОМЕНДАЦИИ")
    missing_input = input("Введите список проблемных ID через запятую (например, C010, C015): ").strip()
    missing_ids = [m.strip() for m in missing_input.split(",")] if missing_input else []
    
    plan = build_learning_plan(missing_ids, loader)
    print(f"\n Рекомендованный план изучения (топологическая сортировка):")
    for idx, c_id in enumerate(plan, 1):
        concept = loader.concepts_by_id.get(c_id, {})
        term = concept.get("term", "Неизвестно")
        topic = concept.get("topic_id", "")
        print(f"  {idx}. [{c_id}] {term} (Раздел/Лаба: {topic})")


# =================================================================
# СЦЕНАРИЙ 6 — Семантический компаратор / LCA (Юля)
# =================================================================

def run_scenario6(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 6: СЕМАНТИЧЕСКИЙ КОМПАРАТОР (LCA)")
    id1 = input("Введите ID первого концепта (например, C040): ").strip()
    id2 = input("Введите ID второго концепта (например, C042): ").strip()
    
    lca = find_lca(id1, id2, loader)
    if lca:
        lca_concept = loader.concepts_by_id.get(lca, {})
        print(f"\n Ближайший общий предок (LCA): [{lca}] {lca_concept.get('term', '')}")
    else:
        print("\n Общий предок не найден.")


# =================================================================
# СЦЕНАРИЙ 8 — Аналитика для преподавателя (Ксюша)
# =================================================================

def run_scenario8(loader: KnowledgeBaseLoader):
    print_separator("СЦЕНАРИЙ 8: АНАЛИТИКА УСПЕВАЕМОСТИ ГРУППЫ")
    topic_id = input("Введите ID раздела для анализа (например, T07): ").strip()
    # Демонстрационный набор данных по группе студентов
    group_data = [
        ["C001", "C002"],
        ["C001"],
        ["C001", "C002", "C003"]
    ]
    print(f"\n Анализ группы для темы {topic_id}...")
    gaps = analyze_group_gaps(group_data, topic_id, loader)
    print(" Статистика пропусков по концептам (чем больше, тем проблемнее):")
    for c_id, count in gaps.items():
        term = loader.concepts_by_id.get(c_id, {}).get("term", "")
        print(f"  • [{c_id}] {term}: не освоили {count} студентов")


# =================================================================
# ГЛАВНОЕ МЕНЮ
# =================================================================

def print_menu():
    print_separator("ИНТЕЛЛЕКТУАЛЬНАЯ ОБУЧАЮЩАЯ СИСТЕМА ПиОИвИС (5 семестр)")
    print("  Выберите сценарий:\n")
    print("  1 — Изучение теоретического материала (Сема 4)")
    print("  2 — Глоссарий / Поиск термина (Сема 4)")
    print("  3 — Интеллектуальный ассистент (Сема 4)")
    print("  4 — Адаптивная диагностика пробелов (Сема 5)")
    print("  5 — Построение траектории и рекомендации (Сема 5)")
    print("  6 — Семантический компаратор / LCA (Сема 5)")
    print("  8 — Аналитика успеваемости для преподавателя (Сема 5)")
    print("  q — Выход\n")


def main():
    # Инициализация БЗ при старте — один раз для всех сценариев
    try:
        loader = KnowledgeBaseLoader(KB_FILES)
        summary = loader.load()
        print(f"База знаний загружена: {summary['concepts_count']} концептов, "
              f"{summary['topics_count']} разделов.")
    except Exception as e:
        print(f"Ошибка загрузки базы знаний: {e}")
        print("Система не может быть запущена без базы знаний.")
        return

    scenarios = {
        "1": lambda: run_scenario1(loader),
        "2": lambda: run_scenario2(loader),
        "3": lambda: run_scenario3(loader),
        "4": lambda: run_scenario4(loader),
        "5": lambda: run_scenario5(loader),
        "6": lambda: run_scenario6(loader),
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
            print("\n  Неверный выбор. Введите 1-6, 8 или q.\n")


if __name__ == "__main__":
    main()
