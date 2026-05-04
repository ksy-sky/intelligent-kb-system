"""
main.py — точка входа интеллектуальной обучающей системы по дисциплине ПиОИвИС.

Структура сценариев:
    Сценарий 1 — Самостоятельное изучение теоретического материала  (scenario_study.py)
    Сценарий 2 — Использование глоссария                            (scenario_glossary.py) ✅
    Сценарий 3 — Работа с интеллектуальным ассистентом              (scenario_assistant.py)

Для добавления нового сценария:
    1. Импортируй свой класс сценария
    2. Создай экземпляр, передав loader
    3. Вызови нужный метод в run_scenarioN()
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kb_loader import KnowledgeBaseLoader
from src.scenario_glossary import GlossaryScenario

# ================= ПУТИ К ФАЙЛАМ =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_FILES = [
    os.path.join(BASE_DIR, "data", "glossary.json"),
    os.path.join(BASE_DIR, "data", "glossary_labs.json"),
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
        print(f"\n Термин:      «{result['term']}»")
        print(f" ID:          {result['concept_id']}")
        print(f" Topic ID:    {result['topic_id']}")
        print(f" Раздел:      {result['topic_title']}")
        source_label = "Теория" if result["source"] == "theory" else "Лабораторные"
        print(f" Источник:    {source_label}")
        print(f" Определение: {result['definition']}")

        if result["relations"]:
            print("   Связи:")
            for rel_type, targets in result["relations"].items():
                targets_str = ", ".join(str(t) for t in targets)
                print(f"     • {rel_type}: {targets_str}")

        if result["examples"]:
            print(f" Пример:      {result['examples'][0]}")
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
# СЦЕНАРИЙ 2 — Использование глоссария ✅
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
# ГЛАВНОЕ МЕНЮ
# =================================================================

def print_menu():
    print_separator("ИНТЕЛЛЕКТУАЛЬНАЯ ОБУЧАЮЩАЯ СИСТЕМА ПиОИвИС")
    print("  Выберите сценарий:\n")
    print("  1 — Изучение теоретического материала")
    print("  2 — Глоссарий (поиск термина)")
    print("  3 — Интеллектуальный ассистент")
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
            print("\n  Неверный выбор. Введите 1, 2, 3 или q.\n")


if __name__ == "__main__":
    main()