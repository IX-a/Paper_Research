import os
import re

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")


def save_markdown(title: str, content: str, output_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)

    filename = _sanitize_filename(title) + ".md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def _sanitize_filename(title: str) -> str:
    # Replace Windows-illegal characters with hyphens
    clean = re.sub(r'[\\/:*?"<>|]', "-", title)
    clean = clean.strip(" .-")
    if len(clean) > 100:
        clean = clean[:100].rsplit("-", 1)[0]
    return clean or "untitled"
