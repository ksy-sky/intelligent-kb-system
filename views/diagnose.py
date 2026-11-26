"""Сценарий 4. Адаптивная диагностика пробелов.

Поток страницы (Streamlit перезапускает скрипт при каждом клике, поэтому всё нужное
между шагами лежит в st.session_state):
  1. Выбор цели + имя студента + кнопка «Начать»        -> call("diagnose", {"target": id})
     ответ need_input -> вопросы кладём в session_state["diag_questions"]
  2. st.form с вопросами, кнопка «Получить результат»    -> call("diagnose", {"target": id, "answers": {...}})
  3. Результат: освоено / пробелы / план с обоснованием, сохранение для аналитики (сц. 8)
  4. Кнопка «Построить траекторию по пробелам» -> session_state["plan_gaps"], страница «План» (сц. 5)
"""
import streamlit as st

from src.results_store import save_diagnostic
from ui_common import (call, concept_label, concept_picker, show_error,
                       show_router_debug, show_warnings)

# ключи session_state этой страницы
K_QUESTIONS = "diag_questions"   # список вопросов от решателя
K_TARGET = "diag_target"         # concept_id цели, по которой идёт диагностика
K_STUDENT = "diag_student"       # имя студента
K_RESULT = "diag_result"         # ответ роутера на diagnose с answers (или без пререквизитов)
K_SAVED = "diag_saved"           # результат уже записан для аналитики?

# для вопросов с выбором: -1 «пропустить», 0 «не знаю», 1..n — номера вариантов
SKIP, DONT_KNOW = -1, 0


def reset_diagnostic() -> None:
    for k in (K_QUESTIONS, K_TARGET, K_STUDENT, K_RESULT, K_SAVED):
        st.session_state.pop(k, None)
    # сбросить и сами радиокнопки, иначе старые ответы «прилипнут» к новой диагностике
    for k in [k for k in st.session_state if str(k).startswith("diag_q_")]:
        del st.session_state[k]


def start_diagnostic(target: str, student: str) -> None:
    """Шаг 1: первый вызов diagnose без answers."""
    reset_diagnostic()
    resp = call("diagnose", {"target": target})
    if resp["status"] == "error":
        show_error(resp)
        return
    st.session_state[K_TARGET] = target
    st.session_state[K_STUDENT] = student
    if resp["status"] == "need_input":
        st.session_state[K_QUESTIONS] = resp["data"]["questions"]
    else:
        # цель без пререквизитов: вопросов нет, результат сразу
        st.session_state[K_RESULT] = resp


def render_question(i: int, total: int, q: dict) -> None:
    """Рисует один вопрос; значение радиокнопки хранится в session_state под её key."""
    key = f"diag_q_{q['concept_id']}"
    st.markdown(f"**Вопрос {i}/{total}.** {q['text']}")
    if q["kind"] == "choice":
        labels = {SKIP: "Пропустить", DONT_KNOW: "Не знаю"}
        labels.update({n: opt for n, opt in enumerate(q["options"], 1)})
        # порядок: варианты ответа, затем «Не знаю» и «Пропустить» (по умолчанию)
        options = list(range(1, len(q["options"]) + 1)) + [DONT_KNOW, SKIP]
        st.radio("Ответ", options, index=len(options) - 1, key=key,
                 format_func=lambda n: labels[n], label_visibility="collapsed")
    else:
        st.radio("Ответ", ["Пропустить", "да", "нет"], index=0, key=key,
                 horizontal=True, label_visibility="collapsed")


def collect_answers(questions: list) -> dict:
    """{concept_id: "1".."n" | "0" | "да" | "нет" | ""} — формат, который понимает решатель."""
    answers = {}
    for q in questions:
        value = st.session_state.get(f"diag_q_{q['concept_id']}")
        if q["kind"] == "choice":
            answers[q["concept_id"]] = "" if value in (None, SKIP) else str(value)
        else:
            answers[q["concept_id"]] = "" if value in (None, "Пропустить") else value
    return answers


def show_result(resp: dict) -> None:
    data = resp["data"]
    status = data["status"]

    if status == "ready":
        st.success(data["message"])
    elif status == "no_prerequisites":
        st.info(data["message"])
    else:
        st.warning(data["message"])

    if status in ("ready", "plan_built"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Освоено", len(data["mastered"]))
        c2.metric("Пробелов", len(data["gaps"]))
        c3.metric("Без ответа", len(data["unanswered"]))

        col_ok, col_gap = st.columns(2)
        with col_ok:
            st.markdown("**✅ Освоено**")
            for cid in data["mastered"]:
                st.markdown(f"- {concept_label(cid)}")
            if not data["mastered"]:
                st.caption("—")
        with col_gap:
            st.markdown("**❌ Пробелы**")
            for cid in data["gaps"]:
                note = " _(нет ответа)_" if cid in data["unanswered"] else ""
                st.markdown(f"- {concept_label(cid)}{note}")
            if not data["gaps"]:
                st.caption("—")

    if data["plan"]:
        st.subheader("План изучения")
        for idx, step in enumerate(data["plan"], 1):
            title = f"{idx}. [{step['concept_id']}] {step['term']}"
            if step["is_target"]:
                title += "  ← цель"
            with st.expander(title, expanded=step["is_target"]):
                st.write(f"**Обоснование:** {step['reason']}")

    if data["cycle"]:
        st.error("Обнаружен цикл зависимостей среди: " + ", ".join(data["cycle"]))

    if data["gaps"]:
        if st.button("Построить траекторию по найденным пробелам", type="primary"):
            st.session_state["plan_gaps"] = data["gaps"]
            st.session_state["plan_target"] = data["target_id"]
            st.session_state.pop("plan_result", None)   # чтобы не показать старый план
            st.switch_page("views/plan.py")


# страница
st.title("🔍 Сценарий 4. Диагностика пробелов")
st.caption("Укажите, что хотите изучить. Система найдёт нужные для этого понятия, задаст "
           "проверочные вопросы и покажет, где у вас пробелы и в каком порядке их закрыть.")

questions = st.session_state.get(K_QUESTIONS)
result = st.session_state.get(K_RESULT)

#  ввод цели
if not questions and not result:
    target = concept_picker("Целевое понятие", key="diag_target_picker")
    student = st.text_input("Имя или псевдоним (для статистики группы)", key="diag_student_input")
    if st.button("Начать диагностику", type="primary"):
        start_diagnostic(target, student)
        if st.session_state.get(K_QUESTIONS) or st.session_state.get(K_RESULT):
            st.rerun()

#  вопросы
elif questions and not result:
    st.info(f"Цель: **{concept_label(st.session_state[K_TARGET])}**. "
            f"Нужно проверить пререквизитов: {len(questions)}. "
            "Если не уверены — выберите «Не знаю» или оставьте «Пропустить» "
            "(пропущенный вопрос считается пробелом).")

    with st.form("diag_form"):
        for i, q in enumerate(questions, 1):
            render_question(i, len(questions), q)
            st.divider()
        submitted = st.form_submit_button("Получить результат", type="primary")

    if submitted:
        resp = call("diagnose", {"target": st.session_state[K_TARGET],
                                 "answers": collect_answers(questions)})
        if resp["status"] == "error":
            show_error(resp)
        else:
            st.session_state[K_RESULT] = resp
            if save_diagnostic(st.session_state.get(K_STUDENT, ""), resp["data"]):
                st.session_state[K_SAVED] = True
            st.rerun()

    if st.button("Отмена"):
        reset_diagnostic()
        st.rerun()

# результат
else:
    show_warnings(result)
    show_result(result)
    if st.session_state.get(K_SAVED):
        st.caption("Результат сохранён для аналитики преподавателя.")
    if st.button("Пройти заново"):
        reset_diagnostic()
        st.rerun()
    show_router_debug(result)
