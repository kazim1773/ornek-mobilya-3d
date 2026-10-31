"""Telefonda müşteri akışını gerçek dokunuşlarla dener (iPhone Safari ve Android Chrome).
Her tasarlayıcı için: menüden aç, adımları İleri ile gez, seçeneklere dokun, sepete ekle, "Odamda dene" ile odaya gönder,
odada "İçini gör"e dokun. Her adımın sonucu ve sayfa hataları raporlanır.

Kullanım: python mobil_akis_testi.py <site-adresi> <klasor> [tur,tur,...] [ortam-filtresi]
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ADRES, KLASOR = sys.argv[1].rstrip('/'), sys.argv[2]
TURLER = sys.argv[3].split(',') if len(sys.argv) > 3 else ['dolap', 'egimli', 'komodin', 'tv', 'masa', 'yatak', 'mutfak', 'banyo']
os.makedirs(KLASOR, exist_ok=True)

with sync_playwright() as p:
    ortamlar = [('safari-iphone', 'webkit', {}, p.devices['iPhone 14']), ('chrome-android', 'chromium', {'channel': 'chrome'}, p.devices['Pixel 7'])]
    if len(sys.argv) > 4:
        ortamlar = [o for o in ortamlar if sys.argv[4] in o[0]]
    rapor = []
    for ad, tarayici, baslat, baglam in ortamlar:
        t = getattr(p, tarayici).launch(**baslat)
        for tur in TURLER:
            s = t.new_context(**baglam).new_page()
            hatalar, sonuc = [], {}
            s.on('pageerror', lambda e: hatalar.append(str(e)[:200]))
            s.on('console', lambda m: m.type == 'error' and 'favicon' not in m.text and '404' not in m.text and hatalar.append(m.text[:200]))
            s.goto(ADRES + '/magaza.html', wait_until='load')
            s.wait_for_timeout(1500)
            # Menü: Kendin Tasarla > tür kartı
            s.tap('#tasarlaMenu')
            s.wait_for_timeout(400)
            s.locator(f'#megaKartlar a[href="#tasarla-{tur}"]').tap()
            s.wait_for_timeout(5000)
            sonuc['menu'] = s.evaluate('location.hash') == f'#tasarla-{tur}'
            # Tasarlayıcı açılınca alt çubuk kaydırmadan ekranda görünmeli
            sonuc['altGorunur'] = s.evaluate("document.querySelector('#tasarlaCerceve iframe').getBoundingClientRect().bottom <= innerHeight + 1")
            fr = s.frame_locator('#tasarlaCerceve iframe')
            if tur == TURLER[0] and ad.startswith('safari'):
                s.screenshot(path=os.path.join(KLASOR, f'{ad}-{tur}-acilis.png'))
            # Adımlar: her adımda ilk iki seçeneğe dokun, sonra İleri
            adim = fr.locator('#adimlar .adim').count()
            dokunus = 0
            for i in range(adim):
                for j in range(2):
                    sec = fr.locator('#konfPanel [data-ayar]:not([disabled])')
                    if sec.count() > j:
                        sec.nth(j).scroll_into_view_if_needed()
                        sec.nth(j).tap()
                        dokunus += 1
                if i < adim - 1:
                    fr.locator('#konfIleri').scroll_into_view_if_needed()
                    fr.locator('#konfIleri').tap()
                    s.wait_for_timeout(250)
            sonuc['sonAdim'] = fr.locator('#adimlar .adim.aktif').count() == 1 and fr.locator('#konfIleri').is_hidden()
            sonuc['dokunus'] = dokunus
            # Sepete ekle
            once = int(s.text_content('#sepetSayac') or 0)
            fr.locator('#konfSepet').scroll_into_view_if_needed()
            fr.locator('#konfSepet').tap()
            s.wait_for_timeout(1200)
            sonuc['sepet'] = int(s.text_content('#sepetSayac') or 0) == once + 1
            # Odamda dene
            fr.locator('#odayaEkle').scroll_into_view_if_needed()
            fr.locator('#odayaEkle').tap()
            s.wait_for_timeout(10000)
            sonuc['odaya'] = s.evaluate('location.hash') == '#planlayici'
            oda = [f for f in s.frames if f.url.endswith('planlayici.html')]
            if oda:
                sonuc['odadaSecili'] = oda[0].evaluate("!!document.getElementById('duzenle') && !document.getElementById('duzenle').closest('[hidden]')")
                icgor = s.frame_locator('#planlayiciCerceve iframe').locator('#icGor')
                if icgor.count() and icgor.is_visible():
                    icgor.scroll_into_view_if_needed()
                    icgor.tap()
                    s.wait_for_timeout(1200)
                    sonuc['icGor'] = icgor.text_content().strip()
            s.screenshot(path=os.path.join(KLASOR, f'{ad}-{tur}-oda.png'))
            sonuc.update({'ortam': ad, 'tur': tur, 'hatalar': hatalar})
            rapor.append(sonuc)
            print(json.dumps(sonuc, ensure_ascii=False), flush=True)
            s.context.close()
        t.close()
