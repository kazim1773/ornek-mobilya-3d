"""Ayrı dosyalı bir glTF modelini (model.gltf + .bin + dokular) tek bir .glb dosyasına paketler.

Kullanım: python glb_paketle.py <girdi.gltf> <cikti.glb>
"""
import json
import mimetypes
import os
import struct
import sys


def hizala(veri: bytearray, dolgu: bytes = b"\x00") -> None:
    while len(veri) % 4:
        veri += dolgu


def paketle(girdi: str, cikti: str) -> None:
    klasor = os.path.dirname(os.path.abspath(girdi))
    with open(girdi, encoding="utf-8") as f:
        gltf = json.load(f)

    ikili = bytearray()
    baslangic = []
    for tampon in gltf.get("buffers", []):
        hizala(ikili)
        baslangic.append(len(ikili))
        with open(os.path.join(klasor, tampon["uri"]), "rb") as f:
            ikili += f.read()

    for gorunum in gltf.get("bufferViews", []):
        gorunum["byteOffset"] = gorunum.get("byteOffset", 0) + baslangic[gorunum["buffer"]]
        gorunum["buffer"] = 0

    gorunumler = gltf.setdefault("bufferViews", [])
    for resim in gltf.get("images", []):
        uri = resim.pop("uri", None)
        if uri is None:
            continue
        hizala(ikili)
        with open(os.path.join(klasor, uri), "rb") as f:
            veri = f.read()
        gorunumler.append({"buffer": 0, "byteOffset": len(ikili), "byteLength": len(veri)})
        ikili += veri
        resim["bufferView"] = len(gorunumler) - 1
        resim["mimeType"] = mimetypes.guess_type(uri)[0] or "image/jpeg"

    hizala(ikili)
    gltf["buffers"] = [{"byteLength": len(ikili)}]

    metin = bytearray(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    hizala(metin, b" ")

    toplam = 12 + 8 + len(metin) + 8 + len(ikili)
    with open(cikti, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, toplam))
        f.write(struct.pack("<II", len(metin), 0x4E4F534A))
        f.write(metin)
        f.write(struct.pack("<II", len(ikili), 0x004E4942))
        f.write(ikili)

    malzemeler = [m.get("name", "?") for m in gltf.get("materials", [])]
    print(f"{os.path.basename(cikti)}: {toplam / 1024 / 1024:.1f} MB, malzemeler: {malzemeler}")


if __name__ == "__main__":
    paketle(sys.argv[1], sys.argv[2])
