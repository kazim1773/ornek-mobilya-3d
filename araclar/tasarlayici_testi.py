"""Tasarlayıcıların her adımını gezer, paneldeki her seçeneğe sırayla basar; hata, yavaş tıklama ve yana taşmayı raporlar.
Her adımın ekran görüntüsü klasöre kaydedilir.

Kullanım: python tasarlayici_testi.py <site-adresi> <klasor> <tur,tur,...> [ortam-filtresi]
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ADRES, KLASOR, TURLER =sys.argv[1].rstrip('/'), sys.argv[2], sys.argv[3].split(',')
os.makedirs(KLASOR, exist_ok=True)

with sync_playwright() as p:
    ortamlar = [
        ('chrome-masaustu', 'chromium', {'channel': 'chrome'}, {'viewport': {'width': 1366, 'height': 768}}),
        ('chrome-android', 'chromium', {'channel': 'chrome'}, p.devices['Pixel 7']),
        ('safari-masaustu', 'webkit', {}, {'viewport': {'width': 1440, 'height': 900}}),
        ('safari-iphone', 'webkit', {}, p.devices['iPhone 14']),
    ]
    if len(sys.argv) > 4:
        ortamlar = [o for o in ortamlar if sys.argv[4] in o[0]]
    rapor = []
    for ad, tarayici, baslat, baglam in ortamlar:
        t = getattr(p, tarayici).launch(**baslat)
        for tur in TURLER:
            s = t.new_context(**baglam).new_page()
            hatalar = []
            s.on('pageerror', lambda e: hatalar.append(str(e)[:300]))
            s.on('console', lambda m: m.type == 'error' and 'favicon' not in m.text and hatalar.append(m.text[:300]))
            s.goto(f'{ADRES}/planlayici.html?mod=tasarla&tur={tur}', wait_until='load')
            s.wait_for_timeout(2500)
            adim_say = s.locator('#adimlar .adim').count()
            en_yavas, tiklama = 0, 0
            for adim in range(adim_say):
                s.locator('#adimlar .adim').nth(adim).click()
                s.wait_for_timeout(300)
                # Her seçeneğe sırayla bas (panel her tıklamada yeniden çizilir; sayıyı her seferinde yeniden al)
                i = 0
                while i < s.locator('#konfPanel [data-ayar]:not([disabled])').count() and i < 40:
                    b = s.locator('#konfPanel [data-ayar]:not([disabled])').nth(i)
                    t0 = time.perf_counter()
                    b.click()
                    s.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
                    en_yavas = max(en_yavas, time.perf_counter() - t0)
                    tiklama += 1
                    i += 1
                s.wait_for_timeout(500)
                s.screenshot(path=os.path.join(KLASOR, f'{ad}-{tur}-{adim}.png'))
            # Kaydırıcıları uçtan uca dene (ölçü adımı)
            s.locator('#adimlar .adim').nth(1).click()
            for el in s.locator('#konfPanel input[type=number]').all():
                for v in (el.get_attribute('min'), el.get_attribute('max'), '120'):
                    el.fill(v)
                    el.dispatch_event('change')
            # İçini göster düğmesi
            if s.locator('#kapakDugme').is_visible():
                s.click('#kapakDugme')
                s.wait_for_timeout(900)
                s.screenshot(path=os.path.join(KLASOR, f'{ad}-{tur}-ici.png'))
            tasma = s.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            rapor.append({'ortam': ad, 'tur': tur, 'adim': adim_say, 'tiklama': tiklama, 'enYavasTiklamaSn': round(en_yavas, 2),
                          'yanaTasma': tasma, 'fiyat': s.text_content('#konfFiyat'), 'hatalar': hatalar})
            s.context.close()
        t.close()
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
