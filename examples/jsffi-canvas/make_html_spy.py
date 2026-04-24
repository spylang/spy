from pathlib import Path

from util_create_html import demo_page

Path("index.html").write_text(str(demo_page("SPy")), encoding="utf-8")
print("Written demo.html")
