"""Bir klasördeki her .glb dosyasını {"glb": "<base64>"} biçiminde aynı adlı .json dosyasına çevirir.

Yayın ortamı .glb dosyası sunmadığı için modeller sayfaya JSON olarak eklenir.
Kullanım: python glb_json.py <klasor>
"""
import base64
import json
import os
import sys

klasor = sys.argv[1]
for ad in sorted(os.listdir(klasor)):
    if not ad.endswith(".glb"):
        continue
    with open(os.path.join(klasor, ad), "rb") as f:
        veri = base64.b64encode(f.read()).decode("ascii")
    hedef = os.path.join(klasor, ad[:-4] + ".json")
    with open(hedef, "w", encoding="ascii") as f:
        json.dump({"glb": veri}, f)
    print(f"{os.path.basename(hedef)}: {os.path.getsize(hedef) / 1024 / 1024:.1f} MB")
