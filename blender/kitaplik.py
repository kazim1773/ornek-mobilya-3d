"""Kitaplık montaj animasyonunu Blender'da kurar ve Cycles ile render eder.

Tarayıcıdaki demo/mobilya.js ile aynı ölçüler, parça düzeni, damar yönü ve montaj sırası kullanılır.
Burada eksenler: X genişlik, Y derinlik (ön yüz -Y), Z yükseklik. Parçalar mobilya.js'teki gibi
(x, y=yükseklik, z=öne doğru) koordinatlarla tanımlanır ve `b()` ile Blender eksenine çevrilir.

Kullanım (Blender'ın kendi Python'u ile):
  blender --background --factory-startup --python kitaplik.py -- kare=150 cikti=kareler/deneme.jpg
  blender --background --factory-startup --python kitaplik.py -- animasyon bas=1 son=150 cikti=kareler
Seçenekler: ornek=96 (ışık örneği), boyut=1280x720, malzeme=eiche|nussbaum|raeuchereiche, kaydet=sahne.blend
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

KOK = os.path.dirname(os.path.abspath(__file__))
DOKULAR = os.path.normpath(os.path.join(KOK, "..", "demo", "dokular"))
HDR = os.path.join(KOK, "hdr", "studio.hdr")
DOKU_M = 1.2  # bir doku karesinin gerçekte kapladığı alan (metre)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SEC = dict(a.split("=", 1) for a in argv if "=" in a)
ANIMASYON = "animasyon" in argv

# Kitaplık ölçüleri (cm) — montaj.html ile aynı
OLCU = dict(genislik=200, yukseklik=190, derinlik=38, sutun=4, satir=5, arkalik=True, alt="kapak", taban="ayak")
MONTAJ_KARE = 120     # parçaların yerine oturduğu kare sayısı
DEKOR_KARE = 22       # montajdan sonra dekorun belirmesi
TOPLAM = 160          # son karede kısa bir bekleme

# ---------- Sahne sıfırlama ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sahne = bpy.context.scene
koleksiyon = sahne.collection


def b(x, y, z):
    """mobilya.js ekseni (y yukarı, z öne) -> Blender ekseni (z yukarı, -y öne)"""
    return Vector((x, -z, y))


# ---------- Malzemeler ----------
def dugum_malzeme(ad):
    m = bpy.data.materials.new(ad)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def ahsap(dosya):
    m, n, l, p = dugum_malzeme(f"ahsap-{dosya}")
    renk = n.new("ShaderNodeTexImage")
    renk.image = bpy.data.images.load(os.path.join(DOKULAR, f"{dosya}-renk.jpg"))
    normal = n.new("ShaderNodeTexImage")
    normal.image = bpy.data.images.load(os.path.join(DOKULAR, f"{dosya}-normal.jpg"))
    normal.image.colorspace_settings.name = "Non-Color"
    nmap = n.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = 0.35
    l.new(renk.outputs["Color"], p.inputs["Base Color"])
    l.new(normal.outputs["Color"], nmap.inputs["Color"])
    l.new(nmap.outputs["Normal"], p.inputs["Normal"])
    # Yağlı ahşap: saten parlaklık, çok ince vernik
    p.inputs["Roughness"].default_value = 0.52
    p.inputs["Specular IOR Level"].default_value = 0.42
    p.inputs["Coat Weight"].default_value = 0.08
    p.inputs["Coat Roughness"].default_value = 0.35
    return m


def duz(ad, renk, puruz=0.5, metal=0.0, coat=0.0):
    m, _, _, p = dugum_malzeme(ad)
    p.inputs["Base Color"].default_value = (*renk, 1)
    p.inputs["Roughness"].default_value = puruz
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    return m


def hex_renk(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


GOVDE = ahsap(SEC.get("malzeme", "eiche"))
METAL = duz("metal", hex_renk("#1c1d1d"), puruz=0.35, metal=0.6)

# ---------- Parça üretimi ----------
parcalar = []  # (nesne, hedef konum, ad)


def levha(ad, mat, sx, sy, sz, x, y, z, rnd, pah=0.0015):
    """Pahlı levha. UV'ler gerçek ölçüye göre; damar levhanın uzun kenarı boyunca akar."""
    boy = [sx, sy, sz]  # mobilya.js ekseninde
    bx, by, bz = sx, sz, sy  # Blender ekseninde
    me = bpy.data.meshes.new(ad)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= bx
        v.co.y *= by
        v.co.z *= bz
    bm.normal_update()
    uv = bm.loops.layers.uv.new()
    bboy = [bx, by, bz]
    lif = bboy.index(max(bboy))
    ox, oy = rnd.random() * 4, rnd.random() * 4
    for f in bm.faces:
        ana = max(range(3), key=lambda i: abs(f.normal[i]))
        eks = [i for i in range(3) if i != ana]
        v_ = lif if lif in eks else eks[1]
        u_ = next(i for i in eks if i != v_)
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = ((co[u_] + ox) / DOKU_M, (co[v_] + oy) / DOKU_M)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(ad, me)
    koleksiyon.objects.link(ob)
    ob.data.materials.append(mat)
    ob.location = b(x, y, z)
    mod = ob.modifiers.new("pah", "BEVEL")
    mod.width = min(pah, min(boy) / 2.2)
    mod.segments = 2
    mod.limit_method = "NONE"
    mod.harden_normals = True
    parcalar.append((ob, ob.location.copy(), ad))
    return ob


def silindir(ad, mat, r1, r2, h, x, y, z):
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=r2, radius2=r1, depth=h, location=b(x, y, z))
    ob = bpy.context.active_object
    ob.name = ad
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    parcalar.append((ob, ob.location.copy(), ad))
    return ob


def regal(p, rnd):
    W, H, D = p["genislik"] / 100, p["yukseklik"] / 100, p["derinlik"] / 100
    t, bk = 0.019, 0.008
    tabanH = 0.06 if p["taban"] == "sockel" else 0.12 if p["taban"] == "ayak" else 0
    kH = H - tabanH
    n, s = p["sutun"], p["satir"]
    y0 = tabanH
    icD = D - 0.012 if p["arkalik"] else D
    icZ = 0.006 if p["arkalik"] else 0
    for k in (-1, 1):
        levha("Seitenwand", GOVDE, t, kH, D, k * (W / 2 - t / 2), y0 + kH / 2, 0, rnd)
    levha("Boden", GOVDE, W - 2 * t, t, D, 0, y0 + t / 2, 0, rnd)
    levha("Deckel", GOVDE, W - 2 * t, t, D, 0, y0 + kH - t / 2, 0, rnd)
    icG = W - 2 * t
    cw = (icG - (n - 1) * t) / n
    dikmeX = []
    for k in range(n - 1):
        x = -W / 2 + t + cw * (k + 1) + t * k + t / 2
        dikmeX.append(x)
        levha("Mittelwand", GOVDE, t, kH - 2 * t, icD, x, y0 + kH / 2, icZ, rnd)
    icH = kH - 2 * t
    rh = (icH - (s - 1) * t) / s
    rafY = [y0 + t + rh * (j + 1) + t * j + t / 2 for j in range(s - 1)]

    def sutunX(k):
        return -W / 2 + t + cw * k + t * k + cw / 2

    for k in range(n):
        for y in rafY:
            levha("Fachboden", GOVDE, cw - 0.001, t, icD - 0.002, sutunX(k), y, icZ, rnd)
    if p["arkalik"]:
        levha("Rückwand", GOVDE, W - 2 * t + 0.016, kH - 2 * t + 0.016, bk, 0, y0 + kH / 2, -D / 2 + 0.006, rnd, pah=0.0005)
    if p["alt"] != "yok" and s >= 2:
        bosluk = 0.003
        ust, alt = rafY[0] - 0.0015, y0 + 0.002
        for k in range(n):
            sol = -W / 2 if k == 0 else dikmeX[k - 1]
            sag = W / 2 if k == n - 1 else dikmeX[k]
            gx, gw, gh = (sol + sag) / 2, sag - sol - bosluk, ust - alt
            levha("Tür", GOVDE, gw, gh, t, gx, alt + gh / 2, D / 2 + t / 2 + 0.001, rnd, pah=0.002)
            kw = min(0.18, gw * 0.45)
            levha("Griff", METAL, kw, 0.012, 0.022, gx, alt + gh - 0.045, D / 2 + t + 0.012, rnd, pah=0.004)
    if p["taban"] == "ayak":
        xs = [-W / 2 + 0.05] + [x for i, x in enumerate(dikmeX) if n > 3 and i % 2 == 1] + [W / 2 - 0.05]
        for x in xs:
            for z in (-D / 2 + 0.05, D / 2 - 0.05):
                silindir("Fuß", METAL, 0.011, 0.009, tabanH, x, tabanH / 2, z)
    bolmeler = []
    ilk = 1 if p["alt"] != "yok" and s >= 2 else 0
    for k in range(n):
        for j in range(ilk, s):
            altY = y0 + t if j == 0 else rafY[j - 1] + t / 2
            bolmeler.append(dict(x=sutunX(k), y=altY, w=cw, h=rh, d=icD, z=icZ))
    return dict(w=W, h=H, d=D + t), bolmeler


# ---------- Dekor: kitaplar, vazolar, kase ----------
KITAP = ["#c9bfae", "#8e9a8c", "#3f4a52", "#b8836a", "#e3ded4", "#6d5d4f", "#9aa6ad", "#2f3a34", "#d4c2a2"]
dekor = []


def kutu(ad, mat, sx, sy, sz, x, y, z, rz=0.0, pah=0.002):
    ob = levha(ad, mat, sx, sy, sz, x, y, z, random.Random(0), pah=pah)
    parcalar.pop()  # dekor montaja katılmaz
    # Merkez noktası tabana alınır: belirirken raftan yukarı doğru yükselir
    ob.data.transform(Matrix.Translation((0, 0, sy / 2)))
    ob.location.z -= sy / 2
    ob.rotation_euler = (0, -rz, 0) if rz else (0, 0, 0)
    dekor.append(ob)
    return ob


def vazo(mat, yukseklik, gen, x, y, z):
    bm = bmesh.new()
    prof = []
    for i in range(17):
        v = i / 16
        r = gen * (0.55 + 0.45 * math.sin(math.pi * (0.15 + v * 0.75))) * (0.7 if v > 0.92 else 1)
        prof.append(bm.verts.new((max(0.004, r), 0, v * yukseklik)))
    kenarlar = [bm.edges.new((prof[i], prof[i + 1])) for i in range(16)]
    bmesh.ops.spin(bm, geom=prof + kenarlar, cent=(0, 0, 0), axis=(0, 0, 1), angle=math.tau, steps=48, use_merge=True)
    me = bpy.data.meshes.new("Vazo")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Vazo", me)
    koleksiyon.objects.link(ob)
    ob.data.materials.append(mat)
    ob.location = b(x, y, z)
    dekor.append(ob)


def dekor_ekle(bolmeler, tohum=11):
    rnd = random.Random(tohum)
    kitaplar = [duz(f"kitap{i}", hex_renk(c), puruz=0.8) for i, c in enumerate(KITAP)]
    seramik = [
        duz("seramik-beyaz", hex_renk("#efeae2"), puruz=0.3, coat=0.5),
        duz("seramik-pismis", hex_renk("#b46f4f"), puruz=0.8),
        duz("seramik-koyu", hex_renk("#2d3330"), puruz=0.28, coat=0.6),
    ]
    for bo in bolmeler:
        tur = rnd.random()
        onZ = bo["z"] + bo["d"] / 2 - 0.03
        if tur < 0.5 and bo["h"] > 0.2:
            x = bo["x"] - bo["w"] / 2 + 0.015 + rnd.random() * 0.05
            bitis = bo["x"] - bo["w"] / 2 + bo["w"] * (0.45 + rnd.random() * 0.45)
            while x < bitis:
                kal = 0.018 + rnd.random() * 0.022
                boy = min(bo["h"] - 0.02, 0.17 + rnd.random() * 0.09)
                der = min(bo["d"] - 0.06, 0.13 + rnd.random() * 0.06)
                kutu("Kitap", rnd.choice(kitaplar), kal, boy, der, x + kal / 2, bo["y"] + boy / 2, onZ - der / 2 - 0.01)
                x += kal + 0.001
            if rnd.random() < 0.5 and x + 0.1 < bo["x"] + bo["w"] / 2:
                kutu("Kitap", rnd.choice(kitaplar), 0.025, 0.2, 0.15, x + 0.06, bo["y"] + 0.1 * math.cos(0.3) + 0.002, onZ - 0.09, rz=0.3)
        elif tur < 0.72 and bo["h"] > 0.16:
            vazo(rnd.choice(seramik), min(bo["h"] - 0.04, 0.16 + rnd.random() * 0.12), 0.045 + rnd.random() * 0.02,
                 bo["x"] + (rnd.random() - 0.5) * bo["w"] * 0.3, bo["y"], bo["z"])
        elif tur < 0.86:
            y = bo["y"]
            for _ in range(2 + int(rnd.random() * 3)):
                kal = 0.02 + rnd.random() * 0.015
                w = 0.2 + rnd.random() * 0.06
                if y + kal > bo["y"] + bo["h"] - 0.05:
                    break
                kutu("Kitap", rnd.choice(kitaplar), min(w, bo["w"] - 0.04), kal, min(0.15, bo["d"] - 0.06), bo["x"], y + kal / 2, onZ - 0.085)
                y += kal
            vazo(seramik[0], 0.05, 0.05, bo["x"], y, onZ - 0.085)


# ---------- Montaj animasyonu (mobilya.js ile aynı mantık) ----------
def montaj_anahtarla(boyut):
    rnd = random.Random(len(parcalar) * 97 + 3)
    merkez = b(0, boyut["h"] / 2, 0)
    olcek = max(boyut["w"], boyut["h"])
    # Arkalık önce gelir ve yukarıdan duvarın önüne kayar; diğer parçalar alttan yukarı sırayla onun önüne oturur
    sirali = sorted(parcalar, key=lambda p: (p[2] != "Rückwand", p[1].z))
    for i, (ob, hedef, ad) in enumerate(sirali):
        if ad == "Rückwand":
            sira = 0
            bas, son = 1, 1 + 0.4 * MONTAJ_KARE
            ob.location = hedef + Vector((0, -0.02, olcek * 0.45))
            ob.keyframe_insert("location", frame=bas)
            ob.location = hedef
            ob.keyframe_insert("location", frame=son)
            continue
        yon = hedef - merkez
        yon.z *= 0.6
        if yon.length < 1e-4:
            yon = Vector((0, 0, 1))
        yon.normalize()
        # Kitaplık duvara yaslı: parçalar asla geriye (duvara) gitmez; büyük parçalar dönerken
        # kenarı duvara değmesin diye boyutlarıyla orantılı olarak daha çok öne açılır
        yon.y = min(yon.y, 0)
        en_buyuk = max(ob.dimensions)
        kayma = yon * (olcek * (0.1 + rnd.random() * 0.06)) + b(0, olcek * (0.05 + rnd.random() * 0.05), olcek * (0.12 + rnd.random() * 0.1) + en_buyuk * 0.3)
        donme = ((rnd.random() - 0.5) * 0.18, (rnd.random() - 0.5) * 0.12, (rnd.random() - 0.5) * 0.25)
        sira = (i - 1) / max(1, len(sirali) - 2)
        bas = 1 + 0.12 * MONTAJ_KARE + sira * 0.45 * MONTAJ_KARE
        son = bas + 0.43 * MONTAJ_KARE
        ob.location = hedef + kayma
        ob.rotation_euler = donme
        ob.keyframe_insert("location", frame=bas)
        ob.keyframe_insert("rotation_euler", frame=bas)
        ob.location = hedef
        ob.rotation_euler = (0, 0, 0)
        ob.keyframe_insert("location", frame=son)
        ob.keyframe_insert("rotation_euler", frame=son)
    # Dekor montajdan sonra sırayla raftan yukarı doğru yükselerek belirir
    for i, ob in enumerate(dekor):
        bas = MONTAJ_KARE + 2 + (i / max(1, len(dekor) - 1)) * (DEKOR_KARE - 8)
        ob.scale = (1, 1, 0.001)
        ob.keyframe_insert("scale", frame=bas)
        ob.scale = (1, 1, 1)
        ob.keyframe_insert("scale", frame=bas + 8)


# ---------- Oda, ışık, kamera ----------
def oda(boyut):
    # Duvar kitaplığın arkasına yaslı, zemin açık mikro beton
    duvar_mat = duz("duvar", hex_renk("#e8e5de"), puruz=0.92)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, boyut["d"] / 2 - 0.019 + 0.002, 3))
    duvar = bpy.context.active_object
    duvar.scale = (14, 6, 1)
    duvar.rotation_euler = (math.pi / 2, 0, 0)
    duvar.data.materials.append(duvar_mat)

    zm, n, l, p = dugum_malzeme("zemin")
    gurultu = n.new("ShaderNodeTexNoise")
    gurultu.inputs["Scale"].default_value = 2.5
    gurultu.inputs["Detail"].default_value = 6
    rampa = n.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].color = (*hex_renk("#cfcac2"), 1)
    rampa.color_ramp.elements[1].color = (*hex_renk("#dcd8d1"), 1)
    l.new(gurultu.outputs["Fac"], rampa.inputs["Fac"])
    l.new(rampa.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.78
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -4, 0))
    zemin = bpy.context.active_object
    zemin.scale = (14, 10, 1)
    zemin.data.materials.append(zm)

    sup = duz("supurgelik", hex_renk("#f2f0eb"), puruz=0.5)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, boyut["d"] / 2 - 0.019 - 0.004, 0.035))
    s = bpy.context.active_object
    s.scale = (14, 0.012, 0.07)
    s.data.materials.append(sup)


def isik():
    dunya = bpy.data.worlds.new("dunya")
    sahne.world = dunya
    dunya.use_nodes = True
    n, l = dunya.node_tree.nodes, dunya.node_tree.links
    arka = n["Background"]
    hdr = n.new("ShaderNodeTexEnvironment")
    hdr.image = bpy.data.images.load(HDR)
    harita = n.new("ShaderNodeMapping")
    harita.inputs["Rotation"].default_value = (0, 0, math.radians(125))
    koord = n.new("ShaderNodeTexCoord")
    l.new(koord.outputs["Generated"], harita.inputs["Vector"])
    l.new(harita.outputs["Vector"], hdr.inputs["Vector"])
    l.new(hdr.outputs["Color"], arka.inputs["Color"])
    arka.inputs["Strength"].default_value = 0.55

    # Ana ışık: sol önden büyük, yumuşak softbox (pencere gibi)
    bpy.ops.object.light_add(type="AREA", location=(-2.6, -3.0, 3.1))
    ana = bpy.context.active_object
    ana.data.shape = "RECTANGLE"
    ana.data.size, ana.data.size_y = 2.4, 1.6
    ana.data.energy = 520
    ana.data.color = (1.0, 0.94, 0.86)
    yon = Vector((0, 0, 0.9)) - ana.location
    ana.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()
    # Dolgu: sağdan zayıf, soğuk
    bpy.ops.object.light_add(type="AREA", location=(3.2, -2.4, 1.8))
    dolgu = bpy.context.active_object
    dolgu.data.size = 2.0
    dolgu.data.energy = 90
    dolgu.data.color = (0.9, 0.95, 1.0)
    yon = Vector((0, 0, 0.9)) - dolgu.location
    dolgu.rotation_euler = yon.to_track_quat("-Z", "Y").to_euler()


def kamera(boyut):
    bpy.ops.object.empty_add(location=(0, 0, boyut["h"] * 0.48))
    hedef = bpy.context.active_object
    bpy.ops.object.camera_add()
    kam = bpy.context.active_object
    kam.data.lens = 45
    kam.data.sensor_width = 36
    sahne.camera = kam
    iz = kam.constraints.new("TRACK_TO")
    iz.target = hedef
    iz.track_axis = "TRACK_NEGATIVE_Z"
    iz.up_axis = "UP_Y"
    # Kamera montaj boyunca soldan sağa süzülür, parçalar birleştikçe yaklaşır
    yaricap = math.sqrt(boyut["w"] ** 2 + boyut["h"] ** 2 + boyut["d"] ** 2) / 2
    gen, yuk = (int(v) for v in SEC.get("boyut", "1280x720").split("x"))
    yatay = 2 * math.atan(18 / kam.data.lens)
    dikey = 2 * math.atan(math.tan(yatay / 2) * yuk / gen)
    for kare in range(1, TOPLAM + 1, 2):
        k = (kare - 1) / (TOPLAM - 1)
        t = min(1, (kare - 1) / MONTAJ_KARE)
        y = t * t * (3 - 2 * t)
        aci_y = -0.55 + 0.85 * k
        aci_d = 0.2 - 0.08 * y
        # Kadraj yüksekliğe göre: bitmiş kitaplık ekranın ~%80'ini doldurur, dağınıkken geri çekilir
        uzak = (boyut["h"] / 2) / math.tan(dikey / 2) * (1.22 + 0.75 * (1 - y))
        yon = Vector((math.sin(aci_y) * math.cos(aci_d), -math.cos(aci_y) * math.cos(aci_d), math.sin(aci_d)))
        kam.location = hedef.location + yon * uzak
        kam.keyframe_insert("location", frame=kare)


# ---------- Kurulum ----------
rnd = random.Random(int(OLCU["genislik"] * 10 + OLCU["yukseklik"] * 7 + OLCU["derinlik"] * 13))
boyut, bolmeler = regal(OLCU, rnd)
dekor_ekle(bolmeler)
montaj_anahtarla(boyut)
oda(boyut)
isik()
kamera(boyut)

# ---------- Render ayarları ----------
r = sahne.render
sahne.render.engine = "CYCLES"
sahne.cycles.device = "CPU"
sahne.cycles.samples = int(SEC.get("ornek", 96))
sahne.cycles.adaptive_threshold = 0.03
sahne.cycles.use_denoising = True
sahne.cycles.denoiser = "OPENIMAGEDENOISE"
sahne.cycles.max_bounces = 6
r.use_persistent_data = True
r.resolution_x, r.resolution_y = (int(v) for v in SEC.get("boyut", "1280x720").split("x"))
r.resolution_percentage = 100
r.fps = 30
sahne.frame_start, sahne.frame_end = 1, TOPLAM
r.image_settings.file_format = "JPEG"
r.image_settings.quality = 90
sahne.view_settings.view_transform = "AgX"
sahne.view_settings.exposure = float(SEC.get("pozlama", -0.55))
for gorunum in ("AgX - Medium High Contrast", "Medium High Contrast"):
    try:
        sahne.view_settings.look = gorunum
        break
    except TypeError:
        continue
print("GORUNUM", sahne.view_settings.look)

if SEC.get("kaydet"):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(KOK, SEC["kaydet"]))

cikti = os.path.join(KOK, SEC.get("cikti", "kareler"))
if ANIMASYON:
    sahne.frame_start = int(SEC.get("bas", 1))
    sahne.frame_end = int(SEC.get("son", TOPLAM))
    r.filepath = os.path.join(cikti, "kare_####")
    bpy.ops.render.render(animation=True)
else:
    sahne.frame_set(int(SEC.get("kare", TOPLAM)))
    r.filepath = cikti
    bpy.ops.render.render(write_still=True)
print("BITTI")
