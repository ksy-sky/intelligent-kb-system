"""Сценарий 6. Сравнение двух понятий: чем отличаются, что общего, в каком порядке учить."""
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
    "linked": "Связаны по смыслу",
    "text_similar": "Похожие определения",
    "same_topic": "Один раздел, явных связей нет",
    "unrelated": "В базе знаний не связаны",
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


st.title("Сравнение двух понятий")
st.caption(
    "Чем отличаются два понятия курса: тип родства, ближайший общий предок (LCA) и путь через него, "
    "общее, различия, явные противопоставления и порядок изучения. "
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
            st.caption("Выберите два разных понятия, чтобы увидеть сходства и различия.")
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

        with st.expander("Из чего складывается близость"):
            p = data["similarity_parts"]
            st.table([
                {"Составляющая": "Иерархия (Ву–Палмер)", "Значение": p["hierarchy"], "Вес": 0.6},
                {"Составляющая": "Общие связи", "Значение": p["context"], "Вес": 0.2},
                {"Составляющая": "Общие слова определений", "Значение": p["lexical"], "Вес": 0.2},
            ])
            st.caption("Итог = 0.6·иерархия + 0.2·связи + 0.2·лексика. Ву–Палмер по is-a: "
                       f"{data['wu_palmer']}.")

        # --- путь
        if data["path"]:
            st.markdown("#### Путь по иерархии")
            st.markdown(" ".join(
                f"{ROLE_ICON.get(n['role'], '')} **{n['term']}** `[{n['concept_id']}]`"
                for n in data["path"]
            ))
            st.caption(data["path_text"] + "   (стрелка идёт от потомка к предку; 🔶 — общий предок)")

        # --- сравнительная таблица
        d1, d2 = data["differences"]["concept_1"], data["differences"]["concept_2"]
        t1 = pick_label(d1["concept_id"])
        t2 = pick_label(d2["concept_id"])
        st.markdown("#### Сравнительная таблица")
        rows = [
            ("Раздел курса", f"{d1['topic_id']} — {d1['topic_title']}", f"{d2['topic_id']} — {d2['topic_title']}"),
            ("Определение", d1["definition"], d2["definition"]),
            ("Надкласс", ", ".join(d1["superclasses"]), ", ".join(d2["superclasses"])),
            ("Подклассы", ", ".join(d1["subclasses"]), ", ".join(d2["subclasses"])),
            ("Состоит из", ", ".join(d1["parts"]), ", ".join(d2["parts"])),
            ("Пример", "; ".join(d1["examples"][:1]), "; ".join(d2["examples"][:1])),
        ]
        st.table([
            {"Критерий": name, t1: a or "—", t2: b or "—"}
            for name, a, b in rows if a or b or name in ("Раздел курса", "Определение")
        ])

        # --- общее
        st.markdown("#### Что общего")
        com = data["common"]
        shown = False
        if com["same_topic"]:
            shown = True
            st.success(f"**Один раздел:** {com['topic_id']}")
        anc = data["common_ancestors"]
        if anc and data["relationship"] in ("siblings", "cousins", "common_whole"):
            shown = True
            st.success("**Общие предки:** " + ", ".join(a["term"] for a in anc))
        if com["relation_types"]:
            shown = True
            st.success("**Описаны через одинаковые отношения:** " + ", ".join(com["relation_types"]))
        if com["linked_concepts"]:
            shown = True
            st.success("**Общие связанные понятия:** " + ", ".join(c["term"] for c in com["linked_concepts"]))
        if com["keywords"]:
            shown = True
            st.success("**Общие слова определений:** " + ", ".join(com["keywords"]))
        if not shown:
            st.caption("Явного сходства в базе знаний не найдено.")

        # --- различия
        st.markdown("#### В чём различия")
        c_left, c_right = st.columns(2)
        for col, d in ((c_left, d1), (c_right, d2)):
            with col:
                st.markdown(f"**Только у «{d['term']}»:**")
                if d["distinctive_words"]:
                    for w in d["distinctive_words"]:
                        st.markdown(f"- {w}")
                else:
                    st.caption("Отличительных слов в определении нет.")

        for link in data["direct_links"]:
            st.caption(f"Прямая связь в БЗ: «{link['from_term']}» —{link['relation']}→ «{link['to_term']}»")

        # --- как учить
        st.markdown("#### Как не перепутать")
        st.info(data["tip"])
        study = data["study"]
        st.markdown("**Порядок изучения:** " + " → ".join(x["term"] for x in study["order"]))
        if study["labs"]:
            st.markdown("**Лабораторные работы:** " + ", ".join(study["labs"]))

        if len(anc) > 1:
            with st.expander(f"Все общие предки ({len(anc)})"):
                st.table(anc)

        show_router_debug(resp)