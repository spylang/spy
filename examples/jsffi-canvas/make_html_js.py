from pathlib import Path

from util_create_html import demo_page

Path("demo.html").write_text(str(demo_page("JS")), encoding="utf-8")
print("Written demo.html")
