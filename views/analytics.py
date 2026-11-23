"""Сценарий 8. Аналитика группы (преподаватель).

ЗАГЛУШКА. Замените содержимое этого файла своей страницей (остальные файлы не трогать).
Данные: src.results_store -> list_targets(), load_latest(target_id), to_analytics_params(records, threshold).
Вызов: call("analytics", to_analytics_params(records, threshold)) -> data: список концептов с gap_ratio.
"""
import streamlit as st
from ui_common import call, concept_picker, concept_multipicker, show_error, show_warnings, show_router_debug

st.title("Аналитика группы")
st.info("Страница в разработке.")
