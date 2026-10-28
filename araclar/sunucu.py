"""Geliştirme sunucusu: klasörü yayınlar, ayrıca tarayıcıdan gelen görselleri site/gorseller içine kaydeder.

POST /kaydet/<dosya-adi>  ->  gövdeyi site/gorseller/<dosya-adi> olarak yazar (sadece .jpg/.png/.webp).
Kullanım: python sunucu.py [port]
"""
import http.server
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GORSELLER = os.path.join(KOK, "site", "gorseller")


class Isleyici(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=KOK, **kwargs)

    def do_POST(self):
        eslesme = re.fullmatch(r"/kaydet/([a-z0-9-]+\.(?:jpg|png|webp))", self.path)
        if not eslesme:
            self.send_error(400, "Gecersiz dosya adi")
            return
        uzunluk = int(self.headers.get("Content-Length", 0))
        os.makedirs(GORSELLER, exist_ok=True)
        with open(os.path.join(GORSELLER, eslesme.group(1)), "wb") as f:
            f.write(self.rfile.read(uzunluk))
        self.send_response(204)
        self.end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Isleyici).serve_forever()
