"""Общие функции интерфейса. Меняет только владелец каркаса."""
from typing import List, Optional

import streamlit as st

from main import KB_FILES
from src.kb_loader import KnowledgeBaseLoader
from src.solver_router import SolverRouter


@st.cache_resource(show_spinner="Загрузка базы знаний...")
def get_router() -> SolverRouter:
    """БЗ и роутер создаются один раз на запуск приложения, а не при каждом клике."""
    loader = KnowledgeBaseLoader(KB_FILES)
    loader.load()
    return SolverRouter(loader)


def call(action: str, params: Optional[dict] = None) -> dict:
    """Единая точка вызова решателей из интерфейса."""
    return get_router().handle_request({"action": action, "params": params or {}})


def concept_label(concept_id: str) -> str:
    c = get_router().loader.concepts_by_id.get(concept_id, {})
    return f'{c.get("term", "?")} [{concept_id}]'


def concept_options() -> List[str]:
    """Все concept_id, отсортированные по термину."""
    by_id = get_router().loader.concepts_by_id
    return sorted(by_id, key=lambda i: by_id[i].get("term", "").lower())


def concept_picker(label: str, key: str, index: int = 0) -> str:
    """Выпадающий список с поиском вместо ручного ввода ID. Возвращает concept_id."""
    return st.selectbox(label, concept_options(), index=index, key=key, format_func=concept_label)


def concept_multipicker(label: str, key: str, default: Optional[List[str]] = None) -> List[str]:
    return st.multiselect(label, concept_options(), default=default or [], key=key,
                          format_func=concept_label)


def show_error(resp: dict) -> None:
    """Единый вывод ошибки роутера (status == 'error')."""
    err = resp["error"]
    st.error(f'{err["message"]}  (код: `{err["code"]}`)')
    details = err.get("details")
    if isinstance(details, dict):
        if details.get("similar"):
            st.info("Возможно, вы имели в виду: " + ", ".join(details["similar"]))
        if details.get("candidates"):
            st.info("Уточните концепт: " + ", ".join(c["concept_id"] for c in details["candidates"]))
    elif details:
        with st.expander("Подробности"):
            st.code(str(details))


def show_warnings(resp: dict) -> None:
    for w in resp.get("metadata", {}).get("warnings", []):
        st.warning(w)


def show_router_debug(resp: dict) -> None:
    """Ответ роутера целиком: status, explanation, elapsed_ms. Удобно для скриншотов в п. 3.7."""
    with st.expander("Ответ роутера (для отладки и демонстрации)"):
        st.caption(f'Время решения: {resp.get("metadata", {}).get("elapsed_ms")} мс')
        st.json(resp, expanded=False)
