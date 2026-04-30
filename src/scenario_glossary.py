import json
import os
from difflib import get_close_matches
from typing import Optional
from src.utils import normalize_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH_THEORY = os.path.join(BASE_DIR, "data", "glossary.json")
KB_PATH_LABS = os.path.join(BASE_DIR, "data", "glossary_labs.json")

_knowledge_base: Optional[list] = None
_labs_base: Optional[list] = None

def _load_from_file(filepath: str, source_label: str) -> list:
    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}")
        return []
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    concepts = []
    for topic in data.get("topics", []):
        topic_title = topic.get("title", "")
        topic_id = topic.get("topic_id", "")
        for concept in topic.get("concepts", []):
            concept = dict(concept)
            concept["topic_title"] = topic_title
            concept["source"] = source_label
            concepts.append(concept)
    return concepts

def load_knowledge_base() -> list:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = _load_from_file(KB_PATH_THEORY, "theory")
    return _knowledge_base

def load_labs_base() -> list:
    global _labs_base
    if _labs_base is None:
        _labs_base = _load_from_file(KB_PATH_LABS, "labs")
    return _labs_base

def load_all() -> list:
    return load_knowledge_base() + load_labs_base()

def find_entry_by_label(term: str, source: str = "all") -> Optional[dict]:
    normalized = normalize_text(term)
    if source == "theory":
        pool = load_knowledge_base()
    elif source == "labs":
        pool = load_labs_base()
    else:
        pool = load_all()
    for entry in pool:
        if normalize_text(entry.get("term", "")) == normalized:
            return entry
    return None

def get_similar_terms(term: str, n: int = 5, source: str = "all") -> list:
    if source == "theory":
        pool = load_knowledge_base()
    elif source == "labs":
        pool = load_labs_base()
    else:
        pool = load_all()
    all_terms = list({entry.get("term", "") for entry in pool})
    return get_close_matches(term, all_terms, n=n, cutoff=0.4)

def search_term(term: str, source: str = "all") -> dict:
    entry = find_entry_by_label(term, source=source)
    if entry:
        return {
            "found": True,
            "term": entry.get("term"),
            "concept_id": entry.get("concept_id"),
            "topic_id": entry.get("topic_id"),
            "topic_title": entry.get("topic_title"),
            "source": entry.get("source"),
            "definition": entry.get("definition", "Определение отсутствует."),
            "relations": entry.get("relations", {}),
            "examples": entry.get("examples", []),
        }
    else:
        similar = get_similar_terms(term, source=source)
        return {
            "found": False,
            "term": term,
            "message": "Термин не найден в базе знаний.",
            "similar_terms": similar,
        }

def get_all_terms(source: str = "all") -> list:
    if source == "theory":
        pool = load_knowledge_base()
    elif source == "labs":
        pool = load_labs_base()
    else:
        pool = load_all()
    return sorted({entry.get("term", "") for entry in pool if entry.get("term")})

def get_terms_by_topic(topic_id: str) -> list:
    return [
        entry for entry in load_all()
        if entry.get("topic_id") == topic_id
    ]

def get_stats() -> dict:
    theory = load_knowledge_base()
    labs = load_labs_base()
    return {
        "theory_concepts": len(theory),
        "labs_concepts": len(labs),
        "total": len(theory) + len(labs),
        "theory_topics": len({e.get("topic_id") for e in theory}),
        "labs_topics": len({e.get("topic_id") for e in labs}),
    }
