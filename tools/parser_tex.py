import re
import json
import os
from collections import defaultdict

# ================= УТИЛИТЫ =================
def is_valid_relation_value(val: str) -> bool:
    """Отфильтровывает заглушки, артефакты и пустые строки."""
    if not val:
        return False
    v = val.strip().lower()
    trash = {'...', '—', '–', '-', 'нет', 'не указано', 'т.д.', 'и т.д.', 'и др.', 'см. выше', 'аналогично', ''}
    return v not in trash and len(v) > 1

def is_abbreviation(s: str) -> bool:
    """Определяет, является ли строка короткой аббревиатурой (КИТ, UCS, UTF и т.п.)."""
    if not s:
        return False
    s = s.strip()
    # Короткие строки (<=4 символа), состоящие только из заглавных букв, цифр и пробелов/дефисов
    if len(s) <= 4 and re.match(r'^[A-ZА-ЯЁ0-9\s\-]+$', s):
        return True
    # Очень короткие строки, которые точно не являются определениями
    if len(s) <= 3:
        return True
    return False

def normalize_term(term: str) -> str:
    """Убирает артефакты слайдов: (продолжение), (часть N), (окончание) для склейки понятий."""
    if not term:
        return ""
    # Удаляем маркеры в скобках в конце строки: (продолжение), (прод.), (часть 2), (окончание)
    term = re.sub(r'\s*\(\s*продолжени[ея]\s*\)\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s*\(\s*прод\.\s*\)\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s*\(\s*ч\.?\s*\d+\s*\)\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s*\(\s*окончани[ея]\s*\)\s*$', '', term, flags=re.IGNORECASE)
    # Также поддерживаем варианты без скобок (на всякий случай)
    term = re.sub(r'\s+продолжени[ея]\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s+прод\.\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s+ч\.?\s*\d+\s*$', '', term, flags=re.IGNORECASE)
    term = re.sub(r'\s+окончани[ея]\s*$', '', term, flags=re.IGNORECASE)
    return term.strip()

def clean_latex(text: str) -> str:
    """Удаляет LaTeX-разметку, оставляет чистый текст."""
    if not text:
        return ""
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\uline\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\url\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\scnkeyword\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+(?:\[[^\]]*\])?', '', text)
    text = re.sub(r'\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_brace_content(text: str, start_idx: int) -> str:
    """Надёжно извлекает текст между парными фигурными скобками, учитывая вложенность."""
    if start_idx >= len(text) or text[start_idx] != '{':
        return ""
    depth = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start_idx+1:i]
    return ""

def parse_tex_file(filepath: str) -> list[dict]:
    """Парсит один .tex файл и возвращает сырые понятия."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    concepts = []
    blocks = re.split(r'\\scnheader\{', content)[1:]

    for block in blocks:
        term_match = re.match(r'([^}]*)\}', block)
        if not term_match:
            continue
        term = clean_latex(term_match.group(1).strip())
        if not term:
            continue
        term = normalize_term(term)

        # ================= ОПРЕДЕЛЕНИЕ (ИСПРАВЛЕНИЕ ПРОБЛЕМЫ 1) =================
        definition = ""
        # 1. Приоритет: явное \scntext{определение}
        def_match = re.search(r'\\scntext\s*\{\s*определение\s*\}\s*\{', block)
        if def_match:
            definition = extract_brace_content(block, def_match.end() - 1)
        else:
            # 2. Fallback: собираем ВСЕ \scnidtf{} и выбираем наилучший
            idtf_candidates = []
            for m in re.finditer(r'\\scnidtf\s*\{', block):
                val = extract_brace_content(block, m.end() - 1)
                cleaned = clean_latex(val).strip()
                if cleaned:
                    idtf_candidates.append(cleaned)
            
            if idtf_candidates:
                # Фильтруем короткие аббревиатуры (КИТ, UCS, UTF и т.п.)
                full_defs = [c for c in idtf_candidates if not is_abbreviation(c)]
                # Берём самое длинное не-аббревиатурное определение
                if full_defs:
                    definition = max(full_defs, key=len)
                else:
                    # Если только аббревиатуры, берём самую длинную из них
                    definition = max(idtf_candidates, key=len)
        definition = clean_latex(definition)
        # ========================================================================

        # 3. ОТНОШЕНИЯ
        relations = {}
        
        # 3.1 scnrelfromset / scnrelfromlist (умный парсинг вложенных структур)
        rel_pattern = r'\\begin\{scnrelfrom(?:set|list)\}\s*\{([^}]*)\}'
        for m in re.finditer(rel_pattern, block):
            rel_name = clean_latex(m.group(1)).strip()
            end_match = re.search(r'\\end\{scnrelfrom(?:set|list)\}', block[m.end():])
            if end_match:
                rel_body = block[m.end():m.end() + end_match.start()]
                extracted = []

                # Разбиваем блок на отдельные \scnitem{...} секции
                item_parts = re.split(r'\\scnitem\s*\{', rel_body)[1:]
                for part in item_parts:
                    item_content_match = re.match(r'((?:[^{}]|\{[^}]*\})*)\}', part)
                    if item_content_match:
                        main_val = clean_latex(item_content_match.group(1)).strip()

                        if is_valid_relation_value(main_val):
                            extracted.append(main_val)
                        else:
                            # Если заглушка "...", ищем значение в \scnindent
                            indent_match = re.search(r'\\begin\{scnindent\}(.*?)\\end\{scnindent\}', part, re.DOTALL)
                            if indent_match:
                                indent_text = indent_match.group(1)
                                found = False
                                # Ищем явные маркеры: период, этап, название
                                for key in ['период', 'этап', 'название', 'имя', 'дата']:
                                    markers = re.findall(rf'\\scnrelfrom\s*\{{\s*{key}\s*\}}\s*\{{([^}}]*)\}}', indent_text)
                                    for val in markers:
                                        v = clean_latex(val).strip()
                                        if is_valid_relation_value(v):
                                            extracted.append(v)
                                            found = True
                                # Fallback: берем первое валидное значение, если маркеры не найдены
                                if not found:
                                    fallback = re.findall(r'\\scnrelfrom\s*\{[^}]*\}\s*\{([^}]*)\}', indent_text)
                                    for val in fallback:
                                        v = clean_latex(val).strip()
                                        if is_valid_relation_value(v):
                                            extracted.append(v)
                                            break

                if extracted:
                    relations[rel_name] = extracted

        # 3.2 Списки из scneqtoset / scneqtovector
        for env_name in ['scneqtoset', 'scneqtovector']:
            env_pattern = rf'\\begin\{{{env_name}\}}'
            for m in re.finditer(env_pattern, block):
                end_match = re.search(rf'\\end\{{{env_name}\}}', block[m.end():])
                if end_match:
                    rel_body = block[m.end():m.end() + end_match.start()]
                    items = re.findall(r'\\scn(?:file)?item\s*\{((?:[^{}]|\{[^}]*\})*)\}', rel_body, re.DOTALL)
                    cleaned = [clean_latex(i).strip() for i in items if is_valid_relation_value(clean_latex(i).strip())]
                    if cleaned:
                        rel_key = "этапы" if "этап" in term.lower() else "состав"
                        relations[rel_key] = relations.get(rel_key, []) + cleaned

        # 3.3 scnhaselement -> маппим в "состав"
        elem_items = re.findall(r'\\scnhaselement\s*\{([^}]*)\}', block)
        if elem_items:
            relations['состав'] = [clean_latex(i).strip() for i in elem_items if is_valid_relation_value(clean_latex(i).strip())]

        # 3.4 scnsuperset -> маппим в "надклассы"
        sup_items = re.findall(r'\\scnsuperset\s*\{([^}]*)\}', block)
        if sup_items:
            relations['надклассы'] = [clean_latex(i).strip() for i in sup_items if is_valid_relation_value(clean_latex(i).strip())]

        # 4. Примеры и пояснения
        examples = []
        for ex_m in re.finditer(r'\\scntext\s*\{\s*пример\s*\}\s*\{', block):
            ex_content = extract_brace_content(block, ex_m.end() - 1)
            cleaned_ex = clean_latex(ex_content)
            if cleaned_ex:
                examples.append(cleaned_ex)

        expl_match = re.search(r'\\scntext\s*\{\s*пояснение\s*\}\s*\{', block)
        if expl_match:
            expl_content = extract_brace_content(block, expl_match.end() - 1)
            cleaned_expl = clean_latex(expl_content).strip()
            if cleaned_expl and is_valid_relation_value(cleaned_expl):
                relations.setdefault("пояснение", []).append(cleaned_expl)

        if term and (definition or relations or examples):
            concepts.append({
                "term": term,
                "definition": definition,
                "relations": relations,
                "examples": examples,
                "topic_id": None
            })
    return concepts

# ================= ОБРАБОТКА И СБОРКА =================
def build_glossary(file_map: dict[str, tuple[str, str]]) -> dict:
    all_concepts = []
    
    for fp, (tid, tname) in file_map.items():
        if not os.path.exists(fp):
            print(f" Файл не найден: {fp}")
            continue
        raw = parse_tex_file(fp)
        merged = {}
        for c in raw:
            key = c["term"].lower()
            if key not in merged:
                merged[key] = {
                    "term": c["term"],
                    "definition": c["definition"],
                    "relations": {k: list(v) for k, v in c["relations"].items()},
                    "examples": list(c["examples"]),
                    "topic_id": tid
                }
            else:
                t = merged[key]
                # Заполняем определение ТОЛЬКО если оно пустое
                if not t["definition"] and c["definition"]:
                    t["definition"] = c["definition"]
                # Объединяем отношения без дубликатов
                for r_type, targets in c["relations"].items():
                    if r_type not in t["relations"]:
                        t["relations"][r_type] = []
                    for x in targets:
                        if x not in t["relations"][r_type]:
                            t["relations"][r_type].append(x)
                for e in c["examples"]:
                    if e not in t["examples"]:
                        t["examples"].append(e)
        all_concepts.extend(merged.values())

    term_to_id = {}
    counter = 1
    for c in all_concepts:
        key = c["term"].lower()
        if key not in term_to_id:
            term_to_id[key] = f"C{counter:03d}"
            counter += 1

    topics_map = defaultdict(lambda: {"topic_id": "", "title": "", "concepts": []})
    tid_to_name = {v[0]: v[1] for v in file_map.values()}

    for c in all_concepts:
        tid = c["topic_id"]
        cid = term_to_id[c["term"].lower()]
        entry = {"concept_id": cid, "term": c["term"], "topic_id": tid}
        if c["definition"]:
            entry["definition"] = c["definition"]

        resolved_relations = {}
        for r_type, targets in c["relations"].items():
            resolved_targets = []
            for t in targets:
                t_clean = t.lower().strip().replace("«", "").replace("»", "").replace('"', "").replace("'", "").strip()
                resolved_targets.append(term_to_id.get(t_clean, t))
            if resolved_targets:
                resolved_relations[r_type] = resolved_targets
        if resolved_relations:
            entry["relations"] = resolved_relations
        if c["examples"]:
            entry["examples"] = c["examples"]

        topics_map[tid]["concepts"].append(entry)
        topics_map[tid]["topic_id"] = tid
        topics_map[tid]["title"] = tid_to_name.get(tid, "Неизвестно")

    sorted_topics = [topics_map[k] for k in sorted(topics_map.keys())]

    return {
        "metadata": {
            "discipline": "ПиОИвИС",
            "version": "1.0",
            "author": "Ганецкая К.Я.",
            "created": "2026-04-05"
        },
        "topics": sorted_topics
    }

# ================= НАСТРОЙКИ =================
TEX_FILES = {
    "01_basics.tex": ("T01", "Основные понятия и типы технологий"),
    "02_information_tech.tex": ("T02", "Информационные технологии и данные"),
    "03_information_quantity_quality.tex": ("T03", "Качество и количество информации"),
    "04_text_information.tex": ("T04", "Текстовая информация и кодирование"),
    "05_math_structs.tex": ("T05", "Математические структуры и алгоритмы"),
    "06_graphic_information.tex": ("T06", "Представление и обработка графической информации"),
    "07_intelligent_information_tech.tex": ("T07", "Интеллектуальные информационные технологии")
}

if __name__ == "__main__":
    print("🔍 Запуск парсинга лекций...")
    result = build_glossary(TEX_FILES)
    total = sum(len(t["concepts"]) for t in result["topics"])
    with open("glossary.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Готово! Сформировано {total} записей понятий по {len(result['topics'])} темам.")
    print("Файл сохранён: glossary.json")