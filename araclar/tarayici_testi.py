"""Sitenin kapak animasyonunu dört ortamda otomatik test eder: Chrome (masaüstü), Chrome (Android telefon),
Safari motoru WebKit (masaüstü) ve WebKit (iPhone).

Her ortamda: animasyon başlıyor mu (video ya da resim yedeği), herhangi bir anda iki yazı aynı anda
görünüyor mu, dikey ekranda yazı videonun üstüne biniyor mu, sonda düğmeler geliyor mu. Ekran görüntüleri de alınır.

Kullanım: python tarayici_testi.py <adres> <ekran-goruntusu-klasoru>
Adres yerel sunucu da olabilir, yayındaki claude.ai bağlantısı da (sayfa içteki çerçevede aranır).
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

ADRES, KLASOR = sys.argv[1], sys.argv[2]
os.makedirs(KLASOR, exist_ok=True)

DURUM_JS = """() => {
  const b = document.getElementById('montajBolum');
  if (!b) return null;
  const v = document.getElementById('montajVideo');
  const adimlar = [...b.querySelectorAll('.montaj-adim')];
  const gorunen = adimlar.filter(a => { const s = getComputedStyle(a); return s.visibility !== 'hidden' && parseFloat(s.opacity) > 0.05; });
  const m = b.querySelector('.montaj-metin').getBoundingClientRect();
  const yedek = b.querySelector('.montaj-yedek');
  const gorsel = (yedek || v).getBoundingClientRect();
  const dikey = innerWidth < innerHeight;
  return {
    gorunenYazi: gorunen.length,
    yazi: gorunen.map(a => a.querySelector('h1,h2').textContent.trim()),
    videoZaman: +v.currentTime.toFixed(2), videoBitti: v.ended, videoHata: v.error ? v.error.code : null,
    yedek: !!yedek,
    tekrar: !document.getElementById('montajTekrar').hidden,
    yaziGorselinUstunde: dikey ? m.top < gorsel.bottom - 2 : null,
    yatayTasma: document.documentElement.scrollWidth > innerWidth + 1,
    baslikIlkEkranda: (() => { const h = b.querySelector('.montaj-adim h1').getBoundingClientRect(); return h.bottom <= innerHeight; })(),
    dugmelerIlkEkranda: (() => { const e = b.querySelector('.montaj-eylemler').getBoundingClientRect(); return e.bottom <= innerHeight; })(),
    tekrarYaziyaBiniyor: (() => { const t = document.getElementById('montajTekrar'); if (t.hidden) return false;
      const r = t.getBoundingClientRect(); return gorunen.some(a => { const q = a.getBoundingClientRect(); return r.bottom > q.top && r.top < q.bottom && r.right > q.left && r.left < q.right; }); })(),
  };
}"""


def cerceve_bul(sayfa):
    for _ in range(60):
        for c in sayfa.frames:
            try:
                if c.evaluate("() => !!document.getElementById('montajBolum')"):
                    return c
            except Exception:
                pass
        time.sleep(0.25)
    return None


def test(p, ad, tarayici, baslat, baglam):
    t = getattr(p, tarayici).launch(**baslat)
    s = t.new_context(**baglam).new_page()
    s.goto(ADRES, wait_until="load")
    c = cerceve_bul(s)
    if not c:
        t.close()
        return {"ortam": ad, "sonuc": "SAYFA BULUNAMADI"}
    olcumler, en_cok = [], 0
    bas = time.time()
    while time.time() - bas < 12:
        d = c.evaluate(DURUM_JS)
        olcumler.append(d)
        en_cok = max(en_cok, d["gorunenYazi"])
        time.sleep(0.08)
    son = olcumler[-1]
    s.screenshot(path=os.path.join(KLASOR, f"{ad}.png"))
    t.close()
    oynadi = son["videoBitti"] or son["yedek"]
    hata = []
    if not oynadi:
        hata.append("animasyon oynamadı")
    if en_cok > 1:
        hata.append(f"aynı anda {en_cok} yazı göründü")
    if any(o["yaziGorselinUstunde"] for o in olcumler):
        hata.append("yazı görselin üstüne biniyor")
    if not son["tekrar"]:
        hata.append("sonda 'Tekrar oynat' çıkmadı")
    if son["yatayTasma"]:
        hata.append("sayfa yana taşıyor")
    if not son["baslikIlkEkranda"]:
        hata.append("ana başlık ilk ekrana sığmıyor")
    if not son["dugmelerIlkEkranda"]:
        hata.append("düğmeler ilk ekrana sığmıyor")
    if son["tekrarYaziyaBiniyor"]:
        hata.append("'Tekrar oynat' yazının üstüne biniyor")
    return {"ortam": ad, "sonuc": "TAMAM" if not hata else "SORUN: " + "; ".join(hata),
            "yol": "resim yedeği" if son["yedek"] else "video", "sonYazi": son["yazi"], "enCokAyniAndaYazi": en_cok}


with sync_playwright() as p:
    ortamlar = [
        ("chrome-masaustu", "chromium", {"channel": "chrome"}, {"viewport": {"width": 1366, "height": 768}}),
        ("chrome-android", "chromium", {"channel": "chrome"}, p.devices["Pixel 7"]),
        ("safari-masaustu", "webkit", {}, {"viewport": {"width": 1440, "height": 900}}),
        # Bu cihaz tanımının ekran alanı (390x664) Safari'nin üst ve alt çubukları düşülmüş halidir
        ("safari-iphone", "webkit", {}, p.devices["iPhone 14"]),
    ]
    # İsteğe bağlı 3. argüman: yalnızca adı bu metni içeren ortamlar çalışır (ör. "iphone")
    if len(sys.argv) > 3:
        ortamlar = [o for o in ortamlar if sys.argv[3] in o[0]]
    sonuclar = []
    for ortam in ortamlar:
        try:
            sonuclar.append(test(p, *ortam))
        except Exception as e:
            sonuclar.append({"ortam": ortam[0], "sonuc": f"HATA: {e}"[:300]})
    print(json.dumps(sonuclar, ensure_ascii=False, indent=1))
