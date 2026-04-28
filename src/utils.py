import re

def normalize_text(text: str) -> str:
    """Приводит строку к нижнему регистру, убирает лишние пробелы и артефакты."""
    return re.sub(r'\s+', ' ', text.strip().lower())