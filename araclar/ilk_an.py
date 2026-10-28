"""Safari motorunda (WebKit) sayfa açılırken ilk 1,5 saniyede hangi kapak yazılarının göründüğünü ölçer."""
import sys
import time

from playwright.sync_api import sync_playwright

ADRES = sys.argv[1]
JS = """() => [...document.querySelectorAll('.montaj-adim')].map(a => {
  const s = getComputedStyle(a);
  return (a.classList.contains('gorunur') ? '*' : '') + (+s.opacity).toFixed(2) + '/' + s.visibility[0];
}).join(' ')"""
with sync_playwright() as p:
    t = p.webkit.launch()
    s = t.new_context(**p.devices["iPhone 14"]).new_page()
    s.goto(ADRES, wait_until="commit")
    bas = time.time()
    while time.time() - bas < 1.5:
        try:
            print(f"{time.time() - bas:4.2f}s", s.evaluate(JS))
        except Exception as e:
            print("bekleniyor", str(e)[:60])
        time.sleep(0.05)
    t.close()
