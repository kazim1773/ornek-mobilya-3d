"""Chrome masaüstü testinde yayındaki sayfanın neden bulunamadığını gösterir: ekran görüntüsü, başlık ve çerçeveler."""
import sys
import time

from playwright.sync_api import sync_playwright

ADRES, CIKTI, UA = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else None)
with sync_playwright() as p:
    t = p.chromium.launch(channel="chrome")
    baglam = {"viewport": {"width": 1366, "height": 768}}
    if UA:
        baglam["user_agent"] = UA
    s = t.new_context(**baglam).new_page()
    s.goto(ADRES, wait_until="load")
    time.sleep(10)
    print("baslik:", s.title())
    print("varsayilan UA:", s.evaluate("navigator.userAgent")[:120])
    print("cerceveler:", [f.url[:90] for f in s.frames])
    s.screenshot(path=CIKTI)
    t.close()
