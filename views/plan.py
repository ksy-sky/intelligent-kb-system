"""Сценарий 5. План изучения и рекомендации.

ЗАГЛУШКА заменена рабочей страницей.
Вызов: call("plan", {"gaps": [ids], "target": id}) -> data["plan"], data["recommendations"].
Пробелы берутся из st.session_state.get("plan_gaps") (кладёт страница диагностики) или из concept_multipicker.
"""
import streamlit as st
from ui_common import call, concept_picker, concept_multipicker, show_error, show_warnings, show_router_debug

st.title("📚 Сценарий 5. План изучения и рекомендации")
st.caption(
    "Решатель строит упорядоченный план изучения понятий (алгоритм Кана) "
    "и подбирает к каждому понятию определение, примеры, связи и номера "
    "лабораторных работ."
)

incoming_gaps = st.session_state.get("plan_gaps")
incoming_target = st.session_state.get("plan_target")

if incoming_gaps:
    label = f"Пробелы получены от диагностики (сц. 4): {', '.join(incoming_gaps)}"
    if incoming_target:
        label += f" (цель: {incoming_target})"
    st.info(label)

    if st.button("Очистить и выбрать вручную"):
        st.session_state.pop("plan_gaps", None)
        st.session_state.pop("plan_target", None)
        st.session_state.pop("plan_result", None)
        st.rerun()

    gaps = incoming_gaps
    target = incoming_target
else:
    gaps = concept_multipicker("Понятия для изучения (пробелы)", key="plan_gaps_picker")
    use_target = st.checkbox("Указать целевое понятие (объяснение строится как путь до него)")
    target = concept_picker("Целевое понятие", key="plan_target_picker") if use_target else None

build_clicked = st.button("Построить план", type="primary", disabled=not gaps)

if build_clicked:
    st.session_state["plan_result"] = call("plan", {"gaps": gaps, "target": target})

resp = st.session_state.get("plan_result")

if resp:
    show_warnings(resp)

    if resp["status"] == "error":
        show_error(resp)
    else:
        plan = resp["data"]["plan"]
        recs_by_id = {r["concept_id"]: r for r in resp["data"]["recommendations"]}

        if not plan:
            st.success("Пробелов нет — траектория не нужна.")
        else:
            st.success(f"Построен план из {len(plan)} шагов.")

            for idx, step in enumerate(plan, 1):
                rec = recs_by_id.get(step["concept_id"])
                title = f"Шаг {idx}. [{step['concept_id']}] {step['term']}"

                with st.expander(title, expanded=(idx == 1)):
                    st.markdown(f"**Причина включения:** {step['reason']}")

                    if not rec:
                        continue

                    if rec.get("criticality", 0) > 0:
                        st.metric("Критичность", f"{rec['criticality']} понятий зависит в БЗ")

                    if rec.get("topic_title"):
                        st.caption(f"Раздел: {rec['topic_id']} — {rec['topic_title']}")

                    if rec.get("definition"):
                        inh = (
                            f" _(унаследовано от «{rec['inherited_from']}»)_"
                            if rec.get("inherited_from") else ""
                        )
                        st.markdown(f"**Определение{inh}:**")
                        st.write(rec["definition"])

                    if rec.get("examples"):
                        st.markdown("**Примеры:**")
                        for ex in rec["examples"]:
                            st.markdown(f"- {ex}")

                    if rec.get("related"):
                        st.markdown("**Связано с:**")
                        for rel_type, terms in rec["related"].items():
                            st.markdown(f"- *{rel_type}*: {', '.join(terms)}")
                    elif rec.get("similar_by_text"):
                        st.markdown("**Явных связей в БЗ нет. Похожие по смыслу понятия:**")
                        for sim in rec["similar_by_text"]:
                            st.markdown(f"- {sim['term']} (сходство: {sim['similarity']})")

                    if rec.get("lab_ids"):
                        st.markdown(f"**Лабораторные работы:** {', '.join(rec['lab_ids'])}")

        show_router_debug(resp)