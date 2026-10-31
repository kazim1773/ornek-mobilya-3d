"""Sitenin ana sayfalarının ekran görüntülerini Chrome ve Safari motoru WebKit'te, masaüstü ve telefonda alır.
Her sayfada konsol hatalarını ve yana taşmayı da raporlar.

Kullanım: python sayfa_goruntuleri.py <site-adresi> <klasor> [ortam-filtresi]
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

ADRES, KLASOR = sys.argv[1].rstrip('/'), sys.argv[2]
os.makedirs(KLASOR, exist_ok=True)

SAYFALAR = [
    ('anasayfa', '#anasayfa', None),
    ('menu', '#anasayfa', 'menu'),
    ('tasarla', '#tasarla', None),
    ('tasarla-komodin', '#tasarla-komodin', None),
    ('tasarla-masa', '#tasarla-masa', None),
    ('tasarla-yatak', '#tasarla-yatak', None),
    ('tasarla-tezgah', '#tasarla-tezgah', None),
    ('koleksiyon', '#koleksiyon', None),
]

with sync_playwright() as p:
    ortamlar = [
        ('chrome-masaustu', 'chromium', {'channel': 'chrome'}, {'viewport': {'width': 1366, 'height': 768}}),
        ('chrome-android', 'chromium', {'channel': 'chrome'}, p.devices['Pixel 7']),
        ('safari-masaustu', 'webkit', {}, {'viewport': {'width': 1440, 'height': 900}}),
        ('safari-iphone', 'webkit', {}, p.devices['iPhone 14']),
    ]
    if len(sys.argv) > 3:
        ortamlar = [o for o in ortamlar if sys.argv[3] in o[0]]
    rapor = []
    for ad, tarayici, baslat, baglam in ortamlar:
        t = getattr(p, tarayici).launch(**baslat)
        s = t.new_context(**baglam).new_page()
        hatalar = []
        s.on('pageerror', lambda e: hatalar.append(str(e)[:200]))
        s.on('console', lambda m: m.type == 'error' and hatalar.append(m.text[:200]))
        s.goto(ADRES + '/magaza.html', wait_until='load')
        s.wait_for_timeout(1500)
        for sayfa, hash_, eylem in SAYFALAR:
            # İlk açılış her zaman ana sayfadır; diğer bölümlere menüden gidilir gibi hash ile geçilir
            s.evaluate(f"location.hash = '{hash_}'")
            s.wait_for_timeout(3500 if sayfa.startswith('tasarla-') else 900)
            if eylem == 'menu':
                s.click('#tasarlaMenu')
                s.wait_for_timeout(400)
            tasma = s.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
            s.screenshot(path=os.path.join(KLASOR, f'{ad}-{sayfa}.png'), full_page=sayfa in ('anasayfa', 'koleksiyon'))
            if eylem == 'menu':
                s.keyboard.press('Escape')
                s.click('#tasarlaMenu')
            rapor.append({'ortam': ad, 'sayfa': sayfa, 'yanaTasma': tasma})
        rapor.append({'ortam': ad, 'hatalar': hatalar})
        t.close()
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
