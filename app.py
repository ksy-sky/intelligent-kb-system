"""
Веб-интерфейс (Streamlit) к решателю задач ИОС по дисциплине «ПиОИвИС».

Запуск из корня проекта:   streamlit run app.py

Этот файл только собирает меню. Общие функции — в ui_common.py, страницы — в views/.
Править app.py и ui_common.py может только тот, кто собирает каркас (договорённость в команде);
каждый участник меняет ТОЛЬКО свой файл в views/.
"""
import streamlit as st

st.set_page_config(page_title="ИОС: решатель задач", page_icon="🎓", layout="wide")

role = st.sidebar.radio("Роль", ["Студент", "Преподаватель"])
pages = [
    st.Page("views/home.py", title="Главная", default=True),
    st.Page("views/diagnose.py", title="Диагностика (сц. 4)"),
    st.Page("views/plan.py", title="План изучения (сц. 5)"),
    st.Page("views/compare.py", title="Сравнение (сц. 6)"),
]
if role == "Преподаватель":
    pages += [st.Page("views/validate.py", title="Проверка БЗ (сц. 7)"),
              st.Page("views/analytics.py", title="Аналитика группы (сц. 8)")]
pg = st.navigation(pages)
pg.run()
