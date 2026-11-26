"""Сценарий 8. Аналитика группы (преподаватель)."""
import streamlit as st
from src.results_store import list_targets, load_latest, to_analytics_params
from ui_common import call, concept_label, show_error, show_warnings, show_router_debug

st.title("Аналитика группы")
st.write("Показывает концепты, по которым доля студентов с пробелом не ниже порога. "
         "Данные берутся из результатов диагностики (сценарий 4): учитывается последняя попытка каждого студента.")

targets = list_targets()
if not targets:
    st.info("Результатов диагностики пока нет. Пройдите диагностику на странице «Диагностика».")
    st.stop()

target = st.selectbox("Целевой концепт", sorted(targets), format_func=lambda t: f"{concept_label(t)} — студентов: {targets[t]}")
threshold = st.slider("Порог доли студентов с пробелом (θ)", 0.0, 1.0, 0.5, 0.05)

records = load_latest(target)
resp = call("analytics", to_analytics_params(records, threshold))

if resp["status"] == "error":
    show_error(resp)
else:
    show_warnings(resp)
    rows = resp["data"]
    summary = (resp.get("explanation") or {}).get("summary", "")
    c1, c2 = st.columns(2)
    c1.metric("Студентов в выборке", len(records))
    c2.metric("Проблемных концептов", len(rows))
    if rows:
        st.dataframe(
            [{"Концепт": r["term"], "Идентификатор": r["concept_id"], "Раздел": r["topic_id"],
              "Доля студентов с пробелом": r["gap_ratio"], "Студентов с пробелом": r["students_with_gap"]}
             for r in rows],
            hide_index=True, use_container_width=True)
        st.bar_chart({r["term"]: r["gap_ratio"] for r in rows})
        st.caption(summary)
    else:
        st.success(summary or "Групповых пробелов выше порога не выявлено.")
    with st.expander("Студенты в выборке"):
        st.table([{"Студент": r["student"], "Время": r["time"], "Пробелов": len(r["gaps"])} for r in records])
show_router_debug(resp)
