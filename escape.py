import html

def escape_html(text: str) -> str:
    """Экранирует специальные символы HTML, чтобы предотвратить ошибку ParseMode.HTML"""
    if not text:
        return ""
    return html.escape(str(text))
