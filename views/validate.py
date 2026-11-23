"""Сценарий 7. Проверка целостности базы знаний (преподаватель). Образец страницы."""
import streamlit as st
from ui_common import call, show_error, show_router_debug

st.title("Проверка базы знаний")
st.write("Преподаватель правит JSON-файлы в папке `data/` и запускает проверку: "
         "уникальность `concept_id`, обязательные поля, ссылки в `relations`, "
         "ацикличность иерархии «надкласс».")

if st.button("Запустить проверку", type="primary"):
    resp = call("admin")
    if resp["status"] == "error":
        show_error(resp)
    else:
        data = resp["data"]
        st.success(data.get("message", "База знаний прошла проверку."))
        stats = data.get("stats", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Файлов проверено", data.get("files_checked"))
        c2.metric("Концептов", stats.get("concepts_count"))
        c3.metric("Разделов", stats.get("topics_count"))
    show_router_debug(resp)
