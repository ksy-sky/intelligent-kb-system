"""Сценарий 6. Семантическое сравнение понятий: общий род, видовые отличия, матрица характеристик."""
import streamlit as st
from ui_common import call, concept_label, concept_options, get_router, show_error, show_warnings, show_router_debug

RELATION_TITLES = {
    "identical": "Это одно и то же понятие",
    "ancestor": "Надкласс — подкласс",
    "descendant": "Подкласс — надкласс",
    "siblings": "«Соседи»: общий прямой надкласс",
    "cousins": "Одна ветка иерархии",
    "part_whole": "Часть — целое",
    "common_whole": "Элементы одного целого",
    "linked": "Нет таксономии, есть горизонтальные связи",
    "same_topic": "Один раздел, явных связей нет",
    "unrelated": "В базе знаний не связаны",
}
STATUS_TITLES = {
    "common": "✅ общее",
    "partly": "🟡 частично общее",
    "different": "🔀 различается",
    "only_1": "◀ только у первого",
    "only_2": "▶ только у второго",
}
ROLE_ICON = {"lca": "🔶", "start": "🟦", "end": "🟦", "up": "▫️", "down": "▫️", "via": "▫️"}


def _homonyms() -> set:
    """Термины, которым соответствует несколько ID (теория и лабораторный практикум)."""
    by_term = get_router().loader.concepts_by_term
    return {t for t, items in by_term.items() if len(items) > 1}


def pick_label(concept_id: str) -> str:
    """Обычные понятия — «термин [ID]»; омонимы — с пометкой «теория» / «лабораторный практикум»."""
    c = get_router().loader.concepts_by_id.get(concept_id, {})
    if str(c.get("term", "")).lower() in _homonyms():
        source = "лабораторный практикум" if str(c.get("topic_id", "")).startswith("L") else "теория"
        return f'{c["term"]} — {source} [{concept_id}]'
    return concept_label(concept_id)


def picker(label: str, key: str, index: int = 0) -> str:
    return st.selectbox(label, concept_options(), index=index, key=key, format_func=pick_label)


def _chain(nodes) -> str:
    return " → ".join(f"**{n['term']}** `[{n['concept_id']}]`" for n in nodes)


st.title("Сравнение двух понятий")
st.caption(
    "Что объединяет два понятия (общий предок и его определение — «род»), чем каждое отличается "
    "(определение и характеристики), что оба наследуют от предка и как их лучше изучать. "
    "Если у термина два ID (теория и лабораторный практикум), выберите нужный в списке."
)

col1, col2 = st.columns(2)
with col1:
    c1 = picker("Первое понятие", key="cmp_c1", index=0)
with col2:
    c2 = picker("Второе понятие", key="cmp_c2", index=1)

if st.button("Сравнить", type="primary", use_container_width=True):
    resp = call("compare", {"concept_1": c1, "concept_2": c2})
    show_warnings(resp)

    if resp["status"] == "error":
        show_error(resp)
    else:
        data = resp["data"]
        st.subheader(f"Тип связи: {RELATION_TITLES.get(data['relationship'], data['relationship'])}")
        st.info(data["message"].split("\nБлизость")[0])

        if data["status"] == "identical":
            st.caption("Уникальных характеристик нет. Выберите два разных понятия.")
            show_router_debug(resp)
            st.stop()

        if data["contrasted"]:
            st.warning("В базе знаний эти понятия прямо противопоставлены — запомните, чем именно они различаются.")

        # --- метрики
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ближайший общий предок", data["lca_term"] or "Нет")
        m2.metric("Близость", f"{data['semantic_similarity']:.2f}", data["similarity_level"], delta_color="off")
        m3.metric("Шагов от 1-го до LCA", data["distance_1"] if data["lca_id"] else "—")
        m4.metric("Шагов от 2-го до LCA", data["distance_2"] if data["lca_id"] else "—")
        with st.expander("Как считается близость"):
            p = data["similarity_parts"]
            st.table([
                {"Составляющая": "Иерархия (Ву–Палмер)", "Значение": p["hierarchy"]},
                {"Составляющая": "Общие горизонтальные связи", "Значение": p["context"]},
            ])
            st.caption("Основа — мера Ву–Палмера по иерархии. Общие горизонтальные связи только повышают "
                       "близость (до 30% оставшегося до 1.0), но не снижают её.")

        # --- род и пути
        if data["genus"] and data["genus"]["definition"]:
            st.markdown("#### Общий род")
            st.success(f"**{data['genus']['term']}** — {data['genus']['definition']}")
        if data["path_1"] and data["path_2"]:
            st.markdown("#### Путь от общего предка до каждого понятия")
            st.markdown(f"**1:** {_chain(data['path_1'])}")
            st.markdown(f"**2:** {_chain(data['path_2'])}")
        elif data["path"]:
            st.markdown("#### Цепочка связей")
            st.markdown(" — ".join(f"**{n['term']}** `[{n['concept_id']}]`" for n in data["path"]))

        # --- видовое отличие: определения рядом
        d1, d2 = data["differences"]["concept_1"], data["differences"]["concept_2"]
        t1, t2 = pick_label(d1["concept_id"]), pick_label(d2["concept_id"])
        st.markdown("#### Чем отличаются")
        rows = [
            ("Раздел курса", f"{d1['topic_id']} — {d1['topic_title']}", f"{d2['topic_id']} — {d2['topic_title']}"),
            ("Определение", d1["definition"], d2["definition"]),
            ("Пояснение", d1["explanation"], d2["explanation"]),
            ("Надкласс", ", ".join(d1["superclasses"]), ", ".join(d2["superclasses"])),
            ("Подклассы", ", ".join(d1["subclasses"]), ", ".join(d2["subclasses"])),
            ("Состоит из", ", ".join(d1["parts"]), ", ".join(d2["parts"])),
            ("Пример", "; ".join(d1["examples"][:1]), "; ".join(d2["examples"][:1])),
        ]
        st.table([
            {"Критерий": name, t1: a or "—", t2: b or "—"}
            for name, a, b in rows if a or b or name in ("Раздел курса", "Определение")
        ])

        # --- матрица характеристик
        st.markdown("#### Матрица характеристик")
        if data["characteristics"]:
            st.table([
                {
                    "Характеристика": r["name"],
                    "Статус": STATUS_TITLES[r["status"]],
                    t1: "; ".join(r["values_1"]) or "—",
                    t2: "; ".join(r["values_2"]) or "—",
                }
                for r in data["characteristics"]
            ])
        else:
            st.caption("В базе знаний у этих понятий не заданы структурные характеристики — "
                       "сравнивайте по определениям выше.")
        if data["inherited"]:
            st.markdown("**Оба наследуют от общих предков:**")
            for r in data["inherited"]:
                st.markdown(f"- **{r['name']}** (от «{r['from_term']}»): {'; '.join(r['values'])}")

        # --- горизонтальные связи
        hor = data["horizontal"]
        if hor["direct_links"] or hor["shared_links"] or len(hor["link_path"]) > 2:
            st.markdown("#### Горизонтальные связи")
            for link in hor["direct_links"]:
                st.markdown(f"- «{link['from_term']}» —**{link['relation']}**→ «{link['to_term']}»")
            if hor["shared_links"]:
                st.markdown("- общие связанные понятия: " + ", ".join(x["term"] for x in hor["shared_links"]))
            if len(hor["link_path"]) > 2:
                st.markdown("- цепочка: " + " — ".join(x["term"] for x in hor["link_path"]))
        com = data["common"]
        if com["same_topic"]:
            st.caption(f"Оба понятия относятся к разделу {com['topic_id']}.")

        # --- как учить
        st.markdown("#### Как не перепутать")
        st.info(data["tip"])
        study = data["study"]
        st.markdown("**Порядок изучения:** " + " → ".join(x["term"] for x in study["order"]))
        if study["labs"]:
            st.markdown("**Лабораторные работы:** " + ", ".join(study["labs"]))

        if len(data["common_ancestors"]) > 1:
            with st.expander(f"Все общие предки ({len(data['common_ancestors'])})"):
                st.table(data["common_ancestors"])

        show_router_debug(resp)