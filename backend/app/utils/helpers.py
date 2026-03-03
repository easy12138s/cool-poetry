import re


def clean_poem_content(content: str) -> str:
    content = re.sub(r"[^\u4e00-\u9fa5，。！？、；：""''（）\s]", "", content)
    return content.strip()


def format_poem_for_display(title: str, author: str, content: str) -> str:
    return f"《{title}》\n{author}\n\n{content}"


def extract_poem_info(text: str) -> dict:
    title_pattern = r"《(.+?)》"
    title_match = re.search(title_pattern, text)

    title = title_match.group(1) if title_match else None

    return {"title": title, "raw_text": text}
