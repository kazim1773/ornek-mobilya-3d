"""GitHub Pages için site/index.html üretir.

site/magaza.html, claude.ai yayınının istediği biçimde belge iskeleti (doctype/html) olmadan yazılır; claude.ai bunu
yayınlarken kendisi ekler. GitHub Pages dosyayı olduğu gibi sunduğu için burada iskeletin başı eklenir, böylece
tarayıcı sayfayı standart modda açar. magaza.html her değiştiğinde bu betik yeniden çalıştırılır.

Kullanım: python araclar/pages_hazirla.py
"""
import os

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(KOK, "site", "magaza.html"), encoding="utf-8") as f:
    icerik = f.read()
with open(os.path.join(KOK, "site", "index.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write('<!doctype html>\n<html lang="tr">\n<!-- Bu dosya araclar/pages_hazirla.py ile site/magaza.html\'den üretilir; doğrudan düzenlemeyin. -->\n')
    f.write(icerik)
print("site/index.html hazır")
