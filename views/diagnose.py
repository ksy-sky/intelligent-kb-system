"""Сценарий 4. Адаптивная диагностика пробелов.

ЗАГЛУШКА. Замените содержимое этого файла своей страницей (остальные файлы не трогать).
Вызов: call("diagnose", {"target": id})  -> status "need_input" + data["questions"];
затем call("diagnose", {"target": id, "answers": {concept_id: ответ}}) -> результат.
После результата: save_diagnostic(student, resp["data"]) из src.results_store,
st.session_state["plan_gaps"] = data["gaps"]; st.session_state["plan_target"] = data["target_id"].
"""
import streamlit as st
from ui_common import call, concept_picker, concept_multipicker, show_error, show_warnings, show_router_debug

st.title("Диагностика пробелов")
st.info("Страница в разработке.")
