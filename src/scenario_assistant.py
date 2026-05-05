"""
Модуль интеллектуального ассистента с использованием LLM через Ollama.
"""

import json
import os
import re
from typing import Dict, List, Any, Optional
from difflib import get_close_matches
import ollama
import subprocess
from src.scenario_glossary import normalize_text

# ========== ФУНКЦИИ ЗАГРУЗКИ (взяты из старого scenario_glossary) ==========


def _load_json_file(filepath: str, source_label: str) -> list:
    """Читает JSON-файл и возвращает плоский список концептов."""
    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}")
        return []
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    concepts = []
    for topic in data.get("topics", []):
        topic_title = topic.get("title", "")
        for concept in topic.get("concepts", []):
            concept = dict(concept)
            concept["topic_title"] = topic_title
            concept["source"] = source_label
            concepts.append(concept)
    return concepts


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH_THEORY = os.path.join(BASE_DIR, "data", "glossary.json")
KB_PATH_LABS = os.path.join(BASE_DIR, "data", "glossary_labs.json")


def load_knowledge_base() -> list:
    return _load_json_file(KB_PATH_THEORY, "theory")


def load_labs_base() -> list:
    return _load_json_file(KB_PATH_LABS, "labs")


def load_all() -> list:
    return load_knowledge_base() + load_labs_base()


def resolve_id(value: str) -> str:
    """Преобразует ID концепта в его термин."""
    if re.match(r"^C(?:L)?\d{2,4}$", value.strip()):
        all_concepts = load_all()
        for c in all_concepts:
            if c.get("concept_id") == value.strip():
                return c.get("term", value)
    return value


# ========== КОНЕЦ ФУНКЦИЙ ЗАГРУЗКИ ==========


MODEL_NAME = "llama3.2"

SYSTEM_PROMPT = """Ты - интеллектуальный ассистент по дисциплине "ПиОИвИС" (Представление и обработка информации в интеллектуальных системах).

Твоя задача - отвечать на вопросы студентов полными, грамотными предложениями на русском языке.

Правила:
1. Отвечай развёрнуто, полными предложениями
2. Если спрашивают определение - дай чёткое определение термина
3. Если спрашивают про связи - опиши их словами
4. Если спрашивают сравнение - сравни понятия
5. Используй информацию из контекста базы знаний
6. Если информации недостаточно - можешь дополнить своими знаниями
7. Будь вежливым и полезным

Формат ответа -  JSON:
{
  "success": true,
  "type": "definition",
  "message": "твой полный, развёрнутый ответ на русском языке"
}

Типы: "definition", "relations", "classification", "comparison", "examples", "general", "error"

поле "message" должно содержать полный, грамотный ответ на русском языке."""


class IntelligentAssistant:
    """Интеллектуальный ассистент с LLM."""

    def __init__(self, use_llm: bool = True):
        self.knowledge_base = load_all()
        self.theory_base = load_knowledge_base()
        self.labs_base = load_labs_base()

        self._terms_index: Dict[str, List[Dict]] = {}
        self._ids_index: Dict[str, Dict] = {}
        self._build_indexes()

        if use_llm:
            try:
                result = subprocess.run(
                    ["ollama", "list"], capture_output=True, text=True, timeout=5
                )
                if MODEL_NAME in result.stdout.lower():
                    self.use_llm = True
                    print(f"Ollama доступен. Модель: {MODEL_NAME}")
                else:
                    print(f"Модель '{MODEL_NAME}' не найдена.")
                    self.use_llm = False
            except:
                self.use_llm = False
        else:
            self.use_llm = False

    def _build_indexes(self):
        """Построение индексов терминов."""
        self._terms_index.clear()
        self._ids_index.clear()

        for entry in self.knowledge_base:
            term = normalize_text(entry.get("term", ""))
            if term:
                if term not in self._terms_index:
                    self._terms_index[term] = []
                self._terms_index[term].append(entry)

            cid = entry.get("concept_id", "")
            if cid:
                self._ids_index[cid] = entry

    def _find_concepts(self, term: str) -> List[Dict]:
        """Поиск всех концептов по термину или ID."""
        normalized = normalize_text(term)

        # Точное совпадение термина
        if normalized in self._terms_index:
            return self._terms_index[normalized]

        # Поиск по ID
        term_upper = term.strip().upper()
        if re.match(r"^C(?:L)?\d{2,4}$", term_upper):
            if term_upper in self._ids_index:
                return [self._ids_index[term_upper]]

        # Нечёткий поиск
        if len(term) >= 4:
            all_terms = list(self._terms_index.keys())
            similar = get_close_matches(normalized, all_terms, n=1, cutoff=0.75)
            if similar:
                return self._terms_index[similar[0]]

        return []

    def _search_relevant_info(self, question: str) -> List[Dict]:
        """Поиск релевантных терминов в базе знаний."""
        question_lower = question.lower().rstrip("?!.")
        relevant = []
        seen = set()
        words = question_lower.split()

        stop_words = {
            "как",
            "дела",
            "привет",
            "пока",
            "что",
            "такое",
            "чем",
            "где",
            "когда",
            "почему",
            "расскажи",
            "покажи",
            "объясни",
            "опиши",
            "найди",
            "дай",
            "и",
            "или",
            "в",
            "на",
            "с",
            "по",
            "к",
            "от",
            "для",
            "про",
            "о",
            "существуют",
            "бывают",
            "есть",
            "можете",
            "назвать",
            "нужен",
            "нужна",
            "отличие",
            "различие",
            "разница",
            "сравнение",
            "сравни",
            "информации",
            "информация",
            "данных",
            "данные",
            "это",
            "не",
            "да",
            "нет",
            "бы",
            "же",
            "ли",
            "то",
            "всё",
            "все",
            "составные",
            "части",
            "состав",
            "компоненты",
            "символы",
            "относятся",
            "какие",
            "перечисли",
            "список",
            "используется",
            "применяется",
        }

        # имщем фразы (от длинных к коротким)
        for phrase_len in range(min(5, len(words)), 1, -1):
            for i in range(len(words) - phrase_len + 1):
                phrase = " ".join(words[i : i + phrase_len])
                if all(w in stop_words for w in phrase.split()):
                    continue
                if len(phrase) < 3:
                    continue
                concepts = self._find_concepts(phrase)
                for concept in concepts:
                    if concept["term"] not in seen:
                        relevant.append(concept)
                        seen.add(concept["term"])

        #  отдельные слова
        if not relevant:
            for word in words:
                if len(word) < 3 or word in stop_words:
                    continue
                concepts = self._find_concepts(word)
                for concept in concepts:
                    if concept["term"] not in seen:
                        relevant.append(concept)
                        seen.add(concept["term"])

        # нечеткий поиск
        if not relevant:
            for word in words:
                if len(word) < 4 or word in stop_words:
                    continue
                similar = get_close_matches(
                    normalize_text(word),
                    list(self._terms_index.keys()),
                    n=2,
                    cutoff=0.6,
                )
                for s in similar:
                    concepts = self._find_concepts(s)
                    for concept in concepts:
                        if concept["term"] not in seen:
                            relevant.append(concept)
                            seen.add(concept["term"])

        return relevant[:5]

    def _build_context(self, concepts: List[Dict]) -> str:
        """Строит текстовый контекст для LLM."""
        if not concepts:
            return "Информация по запросу не найдена в базе знаний."

        parts = []
        for c in concepts:
            p = [f"Термин: {c['term']}"]

            if c.get("definition"):
                p.append(f"Определение: {c['definition']}")

            if c.get("examples"):
                examples = [
                    str(e) for e in c["examples"] if not str(e).startswith("./")
                ]
                if examples:
                    p.append(f"Примеры: {'; '.join(examples[:5])}")

            if c.get("relations"):
                p.append("Связи:")
                for rel_type, targets in c["relations"].items():
                    resolved = [
                        resolve_id(t) for t in targets if not str(t).startswith("./")
                    ]
                    if resolved:
                        p.append(f"  {rel_type}: {', '.join(resolved[:10])}")

            if c.get("topic_title"):
                p.append(f"Раздел: {c['topic_title']}")

            parts.append("\n".join(p))

        return "\n\n".join(parts)

    def _ask_llm(self, question: str, concepts: List[Dict]) -> Dict[str, Any]:
        """Отправляет запрос к LLM."""
        context = self._build_context(concepts)

        question_lower = question.lower()

        #  тип вопроса
        if any(
            w in question_lower
            for w in [
                "отличие",
                "различие",
                "разница",
                "сравни",
                "сравнение",
                "отличается",
            ]
        ):
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Сравни эти понятия, используя информацию из контекста. Ответь полными предложениями.
Ответь в JSON: {{"success": true, "type": "comparison", "message": "твой ответ"}}"""

        elif any(
            w in question_lower
            for w in ["что такое", "определение", "дай понятие", "объясни"]
        ):
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Дай определение термина, используя информацию из контекста.
Ответь в JSON: {{"success": true, "type": "definition", "message": "твой ответ"}}"""

        elif any(
            w in question_lower
            for w in [
                "какие",
                "перечисли",
                "список",
                "относится",
                "входят",
                "состав",
                "компоненты",
                "метасимвол",
                "символ",
            ]
        ):
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Перечисли ВСЕ элементы из контекста, которые относятся к вопросу. Будь конкретным, используй данные из контекста.
Ответь в JSON: {{"success": true, "type": "classification", "message": "твой ответ с перечислением"}}"""

        elif any(
            w in question_lower
            for w in [
                "связи",
                "связан",
                "отношения",
                "используется",
                "применяется",
                "состоит",
            ]
        ):
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Опиши связи термина, используя информацию из контекста.
Ответь в JSON: {{"success": true, "type": "relations", "message": "твой ответ"}}"""

        elif any(w in question_lower for w in ["пример", "примеры", "приведи"]):
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Приведи примеры из контекста.
Ответь в JSON: {{"success": true, "type": "examples", "message": "твой ответ"}}"""

        else:
            prompt = f"""Контекст из базы знаний ПиОИвИС:

{context}

Вопрос студента: {question}

Дай ответ, используя информацию из контекста.
Ответь в JSON: {{"success": true, "type": "general", "message": "твой ответ"}}"""

        try:
            response = ollama.generate(
                model=MODEL_NAME,
                system=SYSTEM_PROMPT,
                prompt=prompt,
                format="json",
                options={
                    "temperature": 0.2,  # Ещё ниже для точности
                    "num_predict": 600,  # Больше токенов для длинных ответов
                    "top_p": 0.9,
                },
            )

            text = response.get("response", "{}")

            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                text = json_match.group()
            else:
                return self._fallback_search(question, concepts)

            result = json.loads(text)

            message = result.get("message", "")
            if not message or len(message.strip()) < 10:
                return self._fallback_search(question, concepts)

            result["success"] = True
            return result

        except Exception as e:
            return self._fallback_search(question, concepts)

    def _fallback_search(self, question: str, concepts: List[Dict]) -> Dict[str, Any]:
        """Запасной поиск без LLM."""
        if not concepts:
            question_lower = question.lower().strip()

            general_words = [
                "как дела",
                "привет",
                "здравствуй",
                "пока",
                "спасибо",
                "как жизнь",
                "кто ты",
            ]
            for word in general_words:
                if word in question_lower:
                    return {
                        "success": True,
                        "type": "general",
                        "message": "Здравствуйте! Я - интеллектуальный ассистент по дисциплине ПиОИвИС. Задайте вопрос по теме предмета, и я постараюсь помочь!",
                    }

            return {
                "success": False,
                "type": "error",
                "message": "Не нашёл информацию по вашему запросу. Попробуйте переформулировать вопрос.",
            }

        if len(concepts) > 1:
            terms_list = [c["term"] for c in concepts[:5]]
            return {
                "success": True,
                "type": "general",
                "message": f"По вашему запросу найдено несколько терминов: {', '.join(terms_list)}. Какой вас интересует?",
                "found_terms": terms_list,
            }

        c = concepts[0]
        definition = c.get("definition", "Определение отсутствует.")
        return {
            "success": True,
            "type": "definition",
            "term": c["term"],
            "definition": definition,
            "message": f"{c['term']} -  {definition}",
        }

    def process_question(self, question: str) -> Dict[str, Any]:
        """Главный метод обработки вопроса."""
        if not question or not question.strip():
            return {
                "success": False,
                "type": "error",
                "message": "Пожалуйста, задайте вопрос.",
            }

        question = question.strip()
        question_lower = question.lower()

        # Отвлечённые вопросы
        general_words = [
            "как дела",
            "привет",
            "здравствуй",
            "пока",
            "спасибо",
            "как жизнь",
            "кто ты",
        ]
        for word in general_words:
            if word in question_lower:
                return {
                    "success": True,
                    "type": "general",
                    "message": "Здравствуйте! Я — интеллектуальный ассистент по дисциплине ПиОИвИС. Буду рад ответить на ваши вопросы по теме дисциплины!",
                }

        # Ищем термины
        concepts = self._search_relevant_info(question)

        # Типы вопросов, которые можно обработать локально
        need_definition = any(
            w in question_lower
            for w in ["что такое", "определение", "объясни", "кто такой", "что значит"]
        )
        need_composition = any(
            w in question_lower
            for w in [
                "состоит",
                "состав",
                "компонент",
                "части",
                "из чего",
                "что входит",
                "что содержит",
            ]
        )
        need_usage = any(
            w in question_lower
            for w in ["используется", "применяется", "где", "для чего"]
        )
        need_classification = any(
            w in question_lower
            for w in [
                "виды",
                "типы",
                "классификац",
                "разбиение",
                "какие бывают",
                "на что делится",
                "перечисли",
                "какие есть",
            ]
        )
        need_examples = any(
            w in question_lower for w in ["пример", "примеры", "приведи"]
        )
        need_hierarchy = any(
            w in question_lower
            for w in ["надкласс", "родитель", "что шире", "что включает"]
        )

        # Если есть термины и это простой вопрос — отвечаем локально
        if concepts and any(
            [
                need_definition,
                need_composition,
                need_usage,
                need_classification,
                need_examples,
                need_hierarchy,
            ]
        ):
            term_name = concepts[0]["term"]
            all_concepts = self._find_concepts(term_name)

            merged_relations = {}
            merged_examples = []
            merged_definition = ""

            for c in all_concepts:
                if c.get("definition") and (
                    not merged_definition or c.get("source") == "theory"
                ):
                    merged_definition = c["definition"]
                for ex in c.get("examples", []):
                    if not str(ex).startswith("./") and ex not in merged_examples:
                        merged_examples.append(ex)
                for k, v in c.get("relations", {}).items():
                    if k not in merged_relations:
                        merged_relations[k] = []
                    for item in v:
                        resolved = resolve_id(item)
                        if (
                            not str(item).startswith("./")
                            and resolved not in merged_relations[k]
                        ):
                            merged_relations[k].append(resolved)

            if need_definition and merged_definition:
                return {
                    "success": True,
                    "type": "definition",
                    "message": f"{term_name} — это {merged_definition}",
                }

            if need_composition:
                for key in [
                    "составные части",
                    "состав",
                    "компоненты",
                    "элементы",
                    "структура",
                ]:
                    if key in merged_relations and merged_relations[key]:
                        return {
                            "success": True,
                            "type": "relations",
                            "message": f"Состав «{term_name}»:\n"
                            + "\n".join(f"• {item}" for item in merged_relations[key]),
                        }

            if need_usage:
                for key in ["используется в", "применяется в", "используется для"]:
                    if key in merged_relations and merged_relations[key]:
                        return {
                            "success": True,
                            "type": "relations",
                            "message": f"«{term_name}» используется в:\n"
                            + "\n".join(f"• {item}" for item in merged_relations[key]),
                        }

            if need_classification:
                for key in ["разбиение", "классификация", "виды"]:
                    if key in merged_relations and merged_relations[key]:
                        return {
                            "success": True,
                            "type": "classification",
                            "message": f"Классификация «{term_name}»:\n"
                            + "\n".join(f"• {item}" for item in merged_relations[key]),
                        }

            if need_examples and merged_examples:
                return {
                    "success": True,
                    "type": "examples",
                    "message": f"Примеры «{term_name}»:\n"
                    + "\n".join(f"• {e}" for e in merged_examples[:10]),
                }

            if need_hierarchy:
                for key in ["надкласс", "надклассы"]:
                    if key in merged_relations and merged_relations[key]:
                        return {
                            "success": True,
                            "type": "hierarchy",
                            "message": f"Надклассы «{term_name}»:\n"
                            + "\n".join(f"• {item}" for item in merged_relations[key]),
                        }

        # все остальное  отправляем в LLM
        if self.use_llm:
            return self._ask_llm(question, concepts if concepts else [])

        # если нет LLM - fallback
        if concepts:
            term_name = concepts[0]["term"]
            all_concepts = self._find_concepts(term_name)
            for c in all_concepts:
                if c.get("definition"):
                    return {
                        "success": True,
                        "type": "definition",
                        "message": f"{c['term']} — это {c['definition']}",
                    }

        return {
            "success": False,
            "type": "error",
            "message": "Не удалось найти информацию. Попробуйте переформулировать вопрос.",
        }


def format_response(response: Dict[str, Any]) -> str:
    """Форматирует ответ для вывода пользователю."""
    sep = "-" * 60

    if not response.get("success"):
        return f"{sep}\n {response.get('message', 'Ошибка')}\n{sep}"

    message = response.get("message", "")

    return f"{sep}\n {message}\n{sep}"


def run_scenario3_assistant():
    """Запуск интерактивного режима ассистента."""
    print("\n" + "=" * 60)
    print("  ИНТЕЛЛЕКТУАЛЬНЫЙ АССИСТЕНТ ПиОИвИС")
    print("=" * 60)

    assistant = IntelligentAssistant(use_llm=True)

    if assistant.use_llm:
        print(f"Режим: LLM ({MODEL_NAME})")
    else:
        print("Режим: Локальный поиск (без ИИ)")

    print("\n Примеры вопросов:")
    print("   • Что такое онтология?")
    print("   • Какие виды технологий существуют?")
    print("   • Чем отличается информация от данных?")
    print("   • Из чего состоит регулярное выражение?")
    print("   • Где используется онтология?")
    print("\n Для выхода введите 'q'.\n")

    while True:
        try:
            user_input = input(" ? Вопрос: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("q", "quit", "выход", "exit"):
            print("\n До свидания! Успехов в изучении ПиОИвИС!\n")
            break

        if not user_input:
            print(" Пожалуйста, задайте вопрос.\n")
            continue

        response = assistant.process_question(user_input)
        print(format_response(response))
        print()
