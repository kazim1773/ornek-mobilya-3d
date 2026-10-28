"""MP4'ü web için "hızlı başlatma" düzenine çevirir: moov kutusunu mdat'ın önüne taşır ve
parça konumlarını (stco/co64) buna göre kaydırır. Telefonlar videoyu dosyanın sonunu beklemeden oynatabilir.

Kullanım: python hizli_baslat.py <girdi.mp4> <cikti.mp4>
"""
import struct
import sys


def kutular(veri, bas=0, son=None):
    """(tür, başlangıç, boyut, başlık uzunluğu) listesi"""
    son = len(veri) if son is None else son
    i, liste = bas, []
    while i + 8 <= son:
        boyut, tur = struct.unpack(">I4s", veri[i:i + 8])
        baslik = 8
        if boyut == 1:
            boyut = struct.unpack(">Q", veri[i + 8:i + 16])[0]
            baslik = 16
        elif boyut == 0:
            boyut = son - i
        liste.append((tur.decode("latin-1"), i, boyut, baslik))
        i += boyut
    return liste


KAPSAYICI = {"moov", "trak", "mdia", "minf", "stbl", "edts", "udta", "dinf"}


def kaydir(moov, fark):
    """moov içindeki bütün stco/co64 konumlarına fark ekler"""
    moov = bytearray(moov)

    def dolas(bas, son):
        for tur, i, boyut, baslik in kutular(moov, bas, son):
            if tur in KAPSAYICI:
                dolas(i + baslik, i + boyut)
            elif tur == "stco":
                adet = struct.unpack(">I", moov[i + 12:i + 16])[0]
                for k in range(adet):
                    p = i + 16 + 4 * k
                    struct.pack_into(">I", moov, p, struct.unpack(">I", moov[p:p + 4])[0] + fark)
            elif tur == "co64":
                adet = struct.unpack(">I", moov[i + 12:i + 16])[0]
                for k in range(adet):
                    p = i + 16 + 8 * k
                    struct.pack_into(">Q", moov, p, struct.unpack(">Q", moov[p:p + 8])[0] + fark)

    ust = kutular(moov)[0]
    dolas(ust[1] + ust[3], ust[1] + ust[2])
    return bytes(moov)


def main(girdi, cikti):
    with open(girdi, "rb") as f:
        veri = f.read()
    ust = kutular(veri)
    sira = [k[0] for k in ust]
    if "moov" not in sira or "mdat" not in sira:
        raise SystemExit("moov ya da mdat bulunamadı")
    if sira.index("moov") < sira.index("mdat"):
        print("zaten hızlı başlatma düzeninde")
        with open(cikti, "wb") as f:
            f.write(veri)
        return
    moov = next(k for k in ust if k[0] == "moov")
    moov_veri = kaydir(veri[moov[1]:moov[1] + moov[2]], moov[2])
    parcalar = []
    for tur, i, boyut, _ in ust:
        if tur == "moov":
            continue
        if tur == "mdat":
            parcalar.append(moov_veri)
        parcalar.append(veri[i:i + boyut])
    with open(cikti, "wb") as f:
        f.write(b"".join(parcalar))
    print("tamam:", [k[0] for k in kutular(b"".join(parcalar))])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
