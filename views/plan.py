"""Сценарий 5. План изучения и рекомендации.

ЗАГЛУШКА. Замените содержимое этого файла своей страницей (остальные файлы не трогать).
Вызов: call("plan", {"gaps": [ids], "target": id}) -> data["plan"], data["recommendations"].
Пробелы берутся из st.session_state.get("plan_gaps") (кладёт страница диагностики) или из concept_multipicker.
"""
import streamlit as st
from ui_common import call, concept_picker, concept_multipicker, show_error, show_warnings, show_router_debug

st.title("План изучения")
st.info("Страница в разработке.")
