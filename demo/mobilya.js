// Ölçüye göre mobilya üreten ve stüdyo kalitesinde gösteren 3D motoru.
// Sayfadan bağımsızdır: hem kapak animasyonu hem tasarla (konfigüratör) bölümü bunu kullanır.
// Birimler: girişler cm / mm, sahne metre. Ön yüz +z yönünde, taban y = 0.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { HorizontalBlurShader } from 'three/addons/shaders/HorizontalBlurShader.js';
import { VerticalBlurShader } from 'three/addons/shaders/VerticalBlurShader.js';

const DOKU_M = 1.2; // bir ahşap doku karesinin gerçekte kapladığı alan (metre)

// ---------- Küçük yardımcılar ----------
// Tohumlu rastgele sayı: aynı ölçülerde aynı damar düzeni ve aynı dekor çıksın, ölçü değişince titremesin
export function tohumlu(tohum) {
  let s = tohum >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}
const yumusak = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const kenet = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

// ---------- Malzemeler ----------
// Her görüntüleyici (ayrı WebGL bağlamı) kendi doku önbelleğini tutar.
export class MalzemeKutusu {
  constructor(renderer, kok) {
    this.renderer = renderer;
    this.kok = kok;
    this.yukleyici = new THREE.TextureLoader();
    this.onbellek = new Map();
  }
  doku(yol, renkli) {
    const anahtar = yol;
    if (this.onbellek.has(anahtar)) return this.onbellek.get(anahtar);
    const t = this.yukleyici.load(this.kok + yol);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = this.renderer.capabilities.getMaxAnisotropy();
    if (renkli) t.colorSpace = THREE.SRGBColorSpace;
    this.onbellek.set(anahtar, t);
    return t;
  }
  // tanim: { tur: 'ahsap', dosya } | { tur: 'lak', renk } | { tur: 'metal', renk }
  al(tanim) {
    const anahtar = 'm:' + JSON.stringify(tanim);
    if (this.onbellek.has(anahtar)) return this.onbellek.get(anahtar);
    let m;
    if (tanim.tur === 'ahsap') {
      // Yağlı ahşap: saten mat yüzey. Taranmış pürüzlülük haritası stüdyo ışığını fazla yansıttığı için sabit değer kullanılır.
      m = new THREE.MeshPhysicalMaterial({
        map: this.doku(`dokular/${tanim.dosya}-renk.jpg`, true),
        normalMap: this.doku(`dokular/${tanim.dosya}-normal.jpg`),
        normalScale: new THREE.Vector2(0.35, 0.35),
        roughness: 0.72,
        specularIntensity: 0.6,
        sheen: 0.15,
        sheenRoughness: 0.8,
        color: tanim.ton || '#ffffff',
      });
    } else if (tanim.tur === 'metal') {
      m = new THREE.MeshStandardMaterial({ color: tanim.renk, metalness: 0.55, roughness: 0.38 });
    } else {
      // İpek mat lake: hafif parlaklık, ince vernik katmanı
      m = new THREE.MeshPhysicalMaterial({ color: tanim.renk, roughness: 0.42, clearcoat: 0.25, clearcoatRoughness: 0.5 });
    }
    this.onbellek.set(anahtar, m);
    return m;
  }
}

// Pahlı kenarlı levha. UV'ler gerçek ölçüye göre yeniden hesaplanır; damar levhanın uzun kenarı boyunca akar.
function levha(sx, sy, sz, yaricap, rnd) {
  const r = Math.min(yaricap, Math.min(sx, sy, sz) / 2 - 0.0002);
  const geo = new RoundedBoxGeometry(sx, sy, sz, 2, Math.max(r, 0.0001));
  const pos = geo.attributes.position, nor = geo.attributes.normal, uv = geo.attributes.uv;
  const boy = [sx, sy, sz];
  const lif = boy.indexOf(Math.max(...boy));
  const ox = rnd() * 4, oy = rnd() * 4;
  for (let i = 0; i < pos.count; i++) {
    const n = [Math.abs(nor.getX(i)), Math.abs(nor.getY(i)), Math.abs(nor.getZ(i))];
    const ana = n[0] >= n[1] && n[0] >= n[2] ? 0 : n[1] >= n[2] ? 1 : 2;
    const eks = [0, 1, 2].filter(a => a !== ana);
    const v = eks.includes(lif) ? lif : eks[1];
    const u = eks.find(a => a !== v);
    const p = [pos.getX(i), pos.getY(i), pos.getZ(i)];
    uv.setXY(i, (p[u] + ox) / DOKU_M, (p[v] + oy) / DOKU_M);
  }
  uv.needsUpdate = true;
  return geo;
}

// Parça toplayıcı: hem sahneye mesh ekler hem üretim listesine satır yazar
class Montaj {
  constructor(tohum) {
    this.grup = new THREE.Group();
    this.parcalar = [];
    this.rnd = tohumlu(tohum);
  }
  // olcu: [x, y, z] metre; liste: üretim listesindeki ad ve kenar bandı (metre). liste=null ise listeye girmez (aksesuar).
  levha(ad, malzeme, malzemeAd, sx, sy, sz, x, y, z, { yaricap = 0.0015, kant = 0, liste = true } = {}) {
    const m = new THREE.Mesh(levha(sx, sy, sz, yaricap, this.rnd), malzeme);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    this.grup.add(m);
    const mm = [sx, sy, sz].map(v => Math.round(v * 1000)).sort((a, b) => b - a);
    this.parcalar.push({ mesh: m, ad, malzeme: malzemeAd, uzunluk: mm[0], genislik: mm[1], kalinlik: mm[2], kant, liste });
    return m;
  }
  mesh(ad, geo, malzeme, x, y, z, malzemeAd = '', liste = false) {
    const m = new THREE.Mesh(geo, malzeme);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    this.grup.add(m);
    this.parcalar.push({ mesh: m, ad, malzeme: malzemeAd, liste });
    return m;
  }
  sonuc(boyut) {
    patlatmaHazirla(this.parcalar, boyut);
    return { grup: this.grup, parcalar: this.parcalar, boyut };
  }
}

// ---------- Raf / kitaplık (Regal) ----------
// p: { genislik, yukseklik, derinlik (cm), sutun, satir, arkalik, alt: 'yok'|'kapak'|'cekmece', taban: 'sockel'|'ayak'|'yok' }
// m: { govde, on, metal } THREE malzemeleri; adlar: { govde, on } listede görünen malzeme adları
export function regalYap(p, m, adlar) {
  const W = p.genislik / 100, H = p.yukseklik / 100, D = p.derinlik / 100, t = 0.019, b = 0.008;
  const tabanH = p.taban === 'sockel' ? 0.06 : p.taban === 'ayak' ? 0.12 : 0;
  const kH = H - tabanH;
  const n = p.sutun, s = p.satir;
  const ic = new Montaj(Math.round(W * 1000 + H * 7 + D * 13 + n * 17 + s * 31));
  const y0 = tabanH;
  const icD = p.arkalik ? D - 0.012 : D; // raflar ve ara dikmeler arkalık kanalının önünde durur
  const icZ = p.arkalik ? 0.006 : 0;

  // Yan dikmeler (tam boy), üst ve alt tabla (yanların arasında)
  for (const k of [-1, 1]) ic.levha('Seitenwand', m.govde, adlar.govde, t, kH, D, k * (W / 2 - t / 2), y0 + kH / 2, 0, { kant: kH });
  ic.levha('Boden', m.govde, adlar.govde, W - 2 * t, t, D, 0, y0 + t / 2, 0, { kant: W - 2 * t });
  ic.levha('Deckel', m.govde, adlar.govde, W - 2 * t, t, D, 0, y0 + kH - t / 2, 0, { kant: W - 2 * t });

  // Sütunlar ve ara dikmeler
  const icG = W - 2 * t, cw = (icG - (n - 1) * t) / n;
  const dikmeX = [];
  for (let k = 0; k < n - 1; k++) {
    const x = -W / 2 + t + cw * (k + 1) + t * k + t / 2;
    dikmeX.push(x);
    ic.levha('Mittelwand', m.govde, adlar.govde, t, kH - 2 * t, icD, x, y0 + kH / 2, icZ, { kant: kH - 2 * t });
  }
  // Raflar: her sütunda satir-1 adet
  const icH = kH - 2 * t, rh = (icH - (s - 1) * t) / s;
  const rafY = [];
  for (let j = 0; j < s - 1; j++) rafY.push(y0 + t + rh * (j + 1) + t * j + t / 2);
  const sutunX = k => -W / 2 + t + cw * k + t * k + cw / 2;
  for (let k = 0; k < n; k++)
    for (const y of rafY) ic.levha('Fachboden', m.govde, adlar.govde, cw - 0.001, t, icD - 0.002, sutunX(k), y, icZ, { kant: cw });

  // Arkalık (kanala oturan ince levha)
  if (p.arkalik) ic.levha('Rückwand', m.govde, adlar.govde, W - 2 * t + 0.016, kH - 2 * t + 0.016, b, 0, y0 + kH / 2, -D / 2 + 0.006, { yaricap: 0.0005 });

  // Alt sırada kapak ya da çekmece
  const kapaklar = [];
  if (p.alt !== 'yok' && s >= 2) {
    const bosluk = 0.003;
    const ust = rafY[0] - 0.0015, alt = y0 + 0.002;
    for (let k = 0; k < n; k++) {
      const sol = k === 0 ? -W / 2 : dikmeX[k - 1], sag = k === n - 1 ? W / 2 : dikmeX[k];
      const gx = (sol + sag) / 2, gw = sag - sol - bosluk, gh = ust - alt;
      const ad = p.alt === 'kapak' ? 'Tür' : 'Schubladenfront';
      const on = ic.levha(ad, m.on, adlar.on, gw, gh, t, gx, alt + gh / 2, D / 2 + t / 2 + 0.001, { kant: 2 * (gw + gh), yaricap: 0.002 });
      kapaklar.push(on);
      // İnce, çubuk kulp (üst kenara yakın, ortalı)
      const kw = Math.min(0.18, gw * 0.45);
      ic.mesh('Griff', new RoundedBoxGeometry(kw, 0.012, 0.022, 2, 0.004), m.metal, gx, alt + gh - 0.045, D / 2 + t + 0.012);
    }
  }

  // Taban: geri çekilmiş kaide ya da metal ayaklar
  if (p.taban === 'sockel') {
    ic.levha('Sockelblende', m.govde, adlar.govde, W - 0.08, tabanH - 0.002, t, 0, tabanH / 2, D / 2 - 0.04, { kant: 0 });
    ic.levha('Sockelblende', m.govde, adlar.govde, W - 0.08, tabanH - 0.002, t, 0, tabanH / 2, -D / 2 + 0.04, { kant: 0 });
    for (const k of [-1, 1]) ic.levha('Sockelblende', m.govde, adlar.govde, t, tabanH - 0.002, D - 0.08 - 2 * t, k * (W / 2 - 0.04 - t / 2), tabanH / 2, 0, { kant: 0 });
  } else if (p.taban === 'ayak') {
    const xs = [-W / 2 + 0.05, ...dikmeX.filter((_, i) => n > 3 && i % 2 === 1), W / 2 - 0.05];
    const geo = new THREE.CylinderGeometry(0.011, 0.009, tabanH, 24);
    for (const x of xs) for (const z of [-D / 2 + 0.05, D / 2 - 0.05]) ic.mesh('Fuß', geo, m.metal, x, tabanH / 2, z);
  }

  const sonuc = ic.sonuc({ w: W, h: H, d: D + (kapaklar.length ? t : 0) });
  sonuc.bolmeler = []; // dekor için açık bölmeler
  const ilkSatir = p.alt !== 'yok' && s >= 2 ? 1 : 0;
  for (let k = 0; k < n; k++) for (let j = ilkSatir; j < s; j++) {
    const altY = j === 0 ? y0 + t : rafY[j - 1] + t / 2;
    sonuc.bolmeler.push({ x: sutunX(k), y: altY, w: cw, h: rh, d: icD, z: icZ });
  }
  return sonuc;
}

// ---------- Masa (Tisch) ----------
// p: { uzunluk, genislik, yukseklik (cm), kalinlik (mm), gestell: 'dort'|'kizak'|'panel' }
export function masaYap(p, m, adlar) {
  const L = p.uzunluk / 100, B = p.genislik / 100, H = p.yukseklik / 100, T = p.kalinlik / 1000;
  const ic = new Montaj(Math.round(L * 1000 + B * 7 + H * 13 + T * 1e4));
  ic.levha('Tischplatte', m.govde, adlar.govde, L, T, B, 0, H - T / 2, 0, { yaricap: 0.004, kant: 2 * (L + B) });
  const bacakH = H - T;
  if (p.gestell === 'dort') {
    const a = 0.065, iceri = 0.07;
    for (const sx of [-1, 1]) for (const sz of [-1, 1])
      ic.levha('Tischbein', m.govde, adlar.govde, a, bacakH, a, sx * (L / 2 - iceri - a / 2), bacakH / 2, sz * (B / 2 - iceri - a / 2), { yaricap: 0.004 });
    const zH = 0.08, zt = 0.022;
    for (const sz of [-1, 1]) ic.levha('Zarge', m.govde, adlar.govde, L - 2 * (iceri + a), zH, zt, 0, bacakH - zH / 2, sz * (B / 2 - iceri - a / 2), { yaricap: 0.002 });
    for (const sx of [-1, 1]) ic.levha('Zarge', m.govde, adlar.govde, zt, zH, B - 2 * (iceri + a), sx * (L / 2 - iceri - a / 2), bacakH - zH / 2, 0, { yaricap: 0.002 });
  } else if (p.gestell === 'kizak') {
    // Toz boyalı çelik kızak ayak: iki dikey boru, üst ve alt yatay
    const a = 0.04, cx = L / 2 - 0.12, zz = B / 2 - 0.07;
    for (const sx of [-1, 1]) {
      const x = sx * cx;
      for (const sz of [-1, 1]) ic.mesh('Kufe', new RoundedBoxGeometry(a, bacakH - 2 * a, a, 2, 0.003), m.metal, x, bacakH / 2, sz * zz);
      ic.mesh('Kufe', new RoundedBoxGeometry(a, a, 2 * zz + a, 2, 0.003), m.metal, x, bacakH - a / 2, 0);
      ic.mesh('Kufe', new RoundedBoxGeometry(a, a, 2 * zz + a, 2, 0.003), m.metal, x, a / 2, 0);
    }
  } else {
    // Masif panel ayaklar ve aradaki traverse
    const pt = 0.04, px = L / 2 - 0.16;
    for (const sx of [-1, 1]) ic.levha('Wange', m.govde, adlar.govde, pt, bacakH, B - 0.2, sx * px, bacakH / 2, 0, { yaricap: 0.003, kant: 2 * bacakH });
    ic.levha('Traverse', m.govde, adlar.govde, 2 * px - pt, 0.09, 0.035, 0, 0.32, 0, { yaricap: 0.003 });
  }
  const sonuc = ic.sonuc({ w: L, h: H, d: B });
  sonuc.duvaraYasla = false;
  return sonuc;
}

// ---------- Montaj animasyonu ----------
// Her parçaya bir "dağınık" konum verilir; montajAyarla(t) ile 0 = parçalar havada, 1 = monte edilmiş.
function patlatmaHazirla(parcalar, boyut) {
  const merkez = new THREE.Vector3(0, boyut.h / 2, 0);
  const rnd = tohumlu(parcalar.length * 97 + 3);
  const sirali = parcalar.slice().sort((a, b) => a.mesh.position.y - b.mesh.position.y);
  sirali.forEach((p, i) => {
    const m = p.mesh;
    const yon = m.position.clone().sub(merkez);
    yon.y *= 0.6;
    if (yon.lengthSq() < 1e-4) yon.set(0, 1, 0);
    yon.normalize();
    // Parçalar merkezden hafifçe dışa ve kameraya doğru açılır; teknik bir "patlatılmış çizim" gibi düzenli kalır
    const olcek = Math.max(boyut.w, boyut.h);
    const mesafe = olcek * (0.1 + rnd() * 0.06);
    m.userData.hedef = m.position.clone();
    m.userData.kayma = yon.multiplyScalar(mesafe).add(new THREE.Vector3(0, olcek * (0.05 + rnd() * 0.05), olcek * (0.12 + rnd() * 0.1)));
    m.userData.donme = new THREE.Euler((rnd() - 0.5) * 0.18, (rnd() - 0.5) * 0.25, (rnd() - 0.5) * 0.12);
    m.userData.sira = i / Math.max(1, sirali.length - 1);
  });
}
export function montajAyarla(nesne, t) {
  for (const p of nesne.parcalar) {
    const m = p.mesh, u = m.userData;
    if (!u.hedef) continue;
    const yerel = yumusak(kenet((t - u.sira * 0.55) / 0.45));
    const k = 1 - yerel;
    m.position.copy(u.hedef).addScaledVector(u.kayma, k);
    m.rotation.set(u.donme.x * k, u.donme.y * k, u.donme.z * k);
  }
  for (const d of nesne.dekor || []) d.visible = t > 0.985;
}

// ---------- Dekor: raflara kitap, vazo, kase ----------
const KITAP_RENKLERI = ['#c9bfae', '#8e9a8c', '#3f4a52', '#b8836a', '#e3ded4', '#6d5d4f', '#9aa6ad', '#2f3a34', '#d4c2a2'];
export function dekorEkle(nesne, tohum = 7) {
  const rnd = tohumlu(tohum);
  const kitapMallar = KITAP_RENKLERI.map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.85 }));
  const seramik = [
    new THREE.MeshPhysicalMaterial({ color: '#efeae2', roughness: 0.35, clearcoat: 0.6 }),
    new THREE.MeshStandardMaterial({ color: '#b46f4f', roughness: 0.8 }),
    new THREE.MeshPhysicalMaterial({ color: '#2d3330', roughness: 0.3, clearcoat: 0.7 }),
  ];
  const parcalar = [];
  const ekle = (geo, mat, x, y, z, ry = 0, rz = 0) => {
    const o = new THREE.Mesh(geo, mat);
    o.position.set(x, y, z);
    o.rotation.set(0, ry, rz);
    o.castShadow = o.receiveShadow = true;
    nesne.grup.add(o);
    parcalar.push(o);
  };
  const vazo = (yukseklik, gen, mat, x, y, z) => {
    const pts = [];
    for (let i = 0; i <= 16; i++) {
      const v = i / 16;
      const r = gen * (0.55 + 0.45 * Math.sin(Math.PI * (0.15 + v * 0.75))) * (v > 0.92 ? 0.7 : 1);
      pts.push(new THREE.Vector2(Math.max(0.004, r), v * yukseklik));
    }
    ekle(new THREE.LatheGeometry(pts, 40), mat, x, y, z);
  };
  for (const b of nesne.bolmeler || []) {
    const tur = rnd();
    const onZ = b.z + b.d / 2 - 0.03;
    if (tur < 0.5 && b.h > 0.2) {
      // Kitap sırası, bazen sona yaslanmış bir kitap
      let x = b.x - b.w / 2 + 0.015 + rnd() * 0.05;
      const bitis = b.x - b.w / 2 + b.w * (0.45 + rnd() * 0.45);
      while (x < bitis) {
        const kal = 0.018 + rnd() * 0.022, boy = Math.min(b.h - 0.02, 0.17 + rnd() * 0.09), der = Math.min(b.d - 0.06, 0.13 + rnd() * 0.06);
        ekle(new RoundedBoxGeometry(kal, boy, der, 1, 0.002), kitapMallar[Math.floor(rnd() * kitapMallar.length)], x + kal / 2, b.y + boy / 2, onZ - der / 2 - 0.01);
        x += kal + 0.001;
      }
      if (rnd() < 0.5 && x + 0.1 < b.x + b.w / 2) {
        const boy = 0.2;
        ekle(new RoundedBoxGeometry(0.025, boy, 0.15, 1, 0.002), kitapMallar[Math.floor(rnd() * kitapMallar.length)], x + 0.06, b.y + boy / 2 * Math.cos(0.3) + 0.002, onZ - 0.09, 0, 0.3);
      }
    } else if (tur < 0.72 && b.h > 0.16) {
      vazo(Math.min(b.h - 0.04, 0.16 + rnd() * 0.12), 0.045 + rnd() * 0.02, seramik[Math.floor(rnd() * seramik.length)], b.x + (rnd() - 0.5) * b.w * 0.3, b.y, b.z);
    } else if (tur < 0.86) {
      // Yatay üst üste kitaplar ve üstünde küçük kase
      let y = b.y;
      for (let i = 0; i < 2 + Math.floor(rnd() * 3); i++) {
        const kal = 0.02 + rnd() * 0.015, w = 0.2 + rnd() * 0.06;
        if (y + kal > b.y + b.h - 0.05) break;
        ekle(new RoundedBoxGeometry(Math.min(w, b.w - 0.04), kal, Math.min(0.15, b.d - 0.06), 1, 0.002), kitapMallar[Math.floor(rnd() * kitapMallar.length)], b.x, y + kal / 2, onZ - 0.085, (rnd() - 0.5) * 0.2);
        y += kal;
      }
      const kase = new THREE.SphereGeometry(0.05, 32, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
      kase.scale(1, 0.55, 1);
      kase.translate(0, 0.0275, 0);
      kase.rotateX(Math.PI);
      kase.translate(0, 0.0275, 0);
      ekle(kase, seramik[0], b.x, y, onZ - 0.085);
    }
    // kalan bölmeler boş: nefes alan bir düzen
  }
  nesne.dekor = parcalar;
}

// ---------- Görüntüleyici (stüdyo) ----------
// Yumuşak zemin gölgesi (contact shadow): nesne alttan derinlik olarak çizilip bulanıklaştırılır.
class ZeminGolgesi {
  constructor(renderer, scene, { boyut = 4, yukseklik = 2.5, koyuluk = 1.4, bulanik = 2.6, saydamlik = 0.75 } = {}) {
    Object.assign(this, { renderer, scene, koyuluk, bulanik });
    this.grup = new THREE.Group();
    this.grup.userData.aoHaric = true;
    scene.add(this.grup);
    this.rt = new THREE.WebGLRenderTarget(1024, 1024);
    this.rtBlur = new THREE.WebGLRenderTarget(1024, 1024);
    this.rt.texture.generateMipmaps = this.rtBlur.texture.generateMipmaps = false;
    const geo = new THREE.PlaneGeometry(1, 1).rotateX(Math.PI / 2);
    this.duzlem = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: this.rt.texture, opacity: saydamlik, transparent: true, depthWrite: false }));
    this.duzlem.renderOrder = 1;
    this.duzlem.position.y = 0.0005;
    this.grup.add(this.duzlem);
    this.bulanikDuzlem = new THREE.Mesh(geo);
    this.bulanikDuzlem.visible = false;
    this.grup.add(this.bulanikDuzlem);
    this.kam = new THREE.OrthographicCamera(-0.5, 0.5, 0.5, -0.5, 0, yukseklik);
    this.kam.rotation.x = Math.PI / 2;
    this.grup.add(this.kam);
    this.derinlik = new THREE.MeshDepthMaterial();
    this.derinlik.userData.koyuluk = { value: koyuluk };
    this.derinlik.onBeforeCompile = shader => {
      shader.uniforms.darkness = this.derinlik.userData.koyuluk;
      shader.fragmentShader = `uniform float darkness;\n${shader.fragmentShader.replace(
        'gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );',
        'gl_FragColor = vec4( vec3( 0.0 ), ( 1.0 - fragCoordZ ) * darkness );')}`;
    };
    this.derinlik.depthTest = this.derinlik.depthWrite = false;
    this.yatay = new THREE.ShaderMaterial(HorizontalBlurShader);
    this.dikey = new THREE.ShaderMaterial(VerticalBlurShader);
    this.yatay.depthTest = this.dikey.depthTest = false;
    this.boyutla(boyut, yukseklik);
  }
  boyutla(boyut, yukseklik) {
    this.duzlem.scale.set(boyut, 1, -boyut);
    this.bulanikDuzlem.scale.set(boyut, 1, boyut);
    Object.assign(this.kam, { left: -boyut / 2, right: boyut / 2, top: boyut / 2, bottom: -boyut / 2, far: yukseklik });
    this.kam.updateProjectionMatrix();
  }
  bulaniklastir(miktar) {
    const p = this.bulanikDuzlem, r = this.renderer;
    p.visible = true;
    p.material = this.yatay;
    this.yatay.uniforms.tDiffuse.value = this.rt.texture;
    this.yatay.uniforms.h.value = miktar / 256;
    r.setRenderTarget(this.rtBlur);
    r.render(p, this.kam);
    p.material = this.dikey;
    this.dikey.uniforms.tDiffuse.value = this.rtBlur.texture;
    this.dikey.uniforms.v.value = miktar / 256;
    r.setRenderTarget(this.rt);
    r.render(p, this.kam);
    p.visible = false;
  }
  ciz(gizlenecekler = []) {
    const { renderer: r, scene: s } = this;
    const arka = s.background, eskiAlfa = r.getClearAlpha();
    const gizli = gizlenecekler.filter(o => o.visible);
    gizli.forEach(o => (o.visible = false));
    this.duzlem.visible = false;
    s.background = null;
    s.overrideMaterial = this.derinlik;
    r.setClearAlpha(0);
    r.setRenderTarget(this.rt);
    r.clear();
    r.render(s, this.kam);
    s.overrideMaterial = null;
    this.bulaniklastir(this.bulanik);
    this.bulaniklastir(this.bulanik * 0.4);
    r.setRenderTarget(null);
    r.setClearAlpha(eskiAlfa);
    s.background = arka;
    this.duzlem.visible = true;
    gizli.forEach(o => (o.visible = true));
  }
}

// Yumuşak, odaklı stüdyo ışığı + HDR ortam + zemin gölgesi + köşe gölgeleri (masaüstünde).
export class Vitrin {
  constructor(kap, { kok = './', hdr = 'isik/studio.json', etkilesim = true, arkaplan = '#f1f0ec' } = {}) {
    this.kap = kap;
    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true }));
    r.setPixelRatio(Math.min(devicePixelRatio, 2));
    r.toneMapping = THREE.NeutralToneMapping;
    r.toneMappingExposure = 1.0;
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.VSMShadowMap;
    kap.appendChild(r.domElement);
    r.domElement.style.display = 'block';

    this.scene = new THREE.Scene();
    this.arkaplan(arkaplan);
    this.kamera = new THREE.PerspectiveCamera(28, 1, 0.05, 60);
    this.malzemeler = new MalzemeKutusu(r, kok);

    // Ana ışık: üst sol önden yumuşak gölge veren tek bir "softbox"
    const anaIsik = (this.anaIsik = new THREE.DirectionalLight('#fff6ec', 1.4));
    anaIsik.position.set(-2.5, 4.5, 3.5);
    anaIsik.castShadow = true;
    anaIsik.shadow.mapSize.set(2048, 2048);
    anaIsik.shadow.radius = 12;
    anaIsik.shadow.blurSamples = 16;
    anaIsik.shadow.bias = -0.0004;
    Object.assign(anaIsik.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.5, far: 15 });
    this.scene.add(anaIsik);
    // Sadece gölge alan, kendisi görünmeyen zemin
    this.golgeZemin = new THREE.Mesh(new THREE.PlaneGeometry(30, 30).rotateX(-Math.PI / 2), new THREE.ShadowMaterial({ opacity: 0.12 }));
    this.golgeZemin.receiveShadow = true;
    this.golgeZemin.userData.aoHaric = true;
    this.scene.add(this.golgeZemin);

    this.zeminGolgesi = new ZeminGolgesi(r, this.scene);
    this.hazir = fetch(kok + hdr).then(y => y.json()).then(({ hdr: b64 }) => {
      const ikili = atob(b64), dizi = new Uint8Array(ikili.length);
      for (let i = 0; i < ikili.length; i++) dizi[i] = ikili.charCodeAt(i);
      const veri = new RGBELoader().parse(dizi.buffer);
      const tex = new THREE.DataTexture(veri.data, veri.width, veri.height, THREE.RGBAFormat, veri.type);
      tex.colorSpace = THREE.LinearSRGBColorSpace;
      tex.mapping = THREE.EquirectangularReflectionMapping;
      tex.minFilter = tex.magFilter = THREE.LinearFilter;
      tex.generateMipmaps = false;
      tex.flipY = true;
      tex.needsUpdate = true;
      const pm = new THREE.PMREMGenerator(r);
      this.scene.environment = pm.fromEquirectangular(tex).texture;
      this.scene.environmentIntensity = 0.85;
      this.scene.environmentRotation = new THREE.Euler(0, 2.2, 0);
      tex.dispose();
      pm.dispose();
    });

    if (etkilesim) {
      const c = (this.kontrol = new OrbitControls(this.kamera, r.domElement));
      c.enableDamping = true;
      c.dampingFactor = 0.08;
      c.enablePan = false;
      c.minPolarAngle = 0.15;
      c.maxPolarAngle = Math.PI / 2 - 0.04;
      c.addEventListener('start', () => (this.kullaniciDondu = true));
    }

    // Köşe gölgeleri: raf bölmelerinin içini ve birleşim yerlerini koyulaştırır (telefonda kapalı)
    this.composer = null;
    if (!matchMedia('(pointer: coarse)').matches) {
      const hedef = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
      const comp = new EffectComposer(r, hedef);
      comp.addPass(new RenderPass(this.scene, this.kamera));
      const ao = new GTAOPass(this.scene, this.kamera, 1, 1);
      ao.updateGtaoMaterial({ radius: 0.12, distanceExponent: 1.5, thickness: 0.5, scale: 1.1, samples: 16 });
      ao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
      ao.blendIntensity = 1;
      // Saydam gölge düzlemleri köşe gölgesi hesabına girmesin
      const gizle = ao.overrideVisibility.bind(ao);
      ao.overrideVisibility = () => { gizle(); this.scene.traverse(o => { if (o.userData.aoHaric) o.visible = false; }); };
      comp.addPass(ao);
      comp.addPass(new OutputPass());
      this.composer = comp;
    }

    this.nesne = null;
    this.oda = null;
    this.kamHedef = { konum: new THREE.Vector3(), bakis: new THREE.Vector3(), aktif: false };
    this.aci = { yatay: 0.5, dikey: 0.32 };
    this.gorunur = true;
    this.golgeKirli = true;
    new ResizeObserver(() => this.boyutla()).observe(kap);
    new IntersectionObserver(([g]) => (this.gorunur = g.isIntersecting), { rootMargin: '200px' }).observe(kap);
    this.boyutla();
    r.setAnimationLoop(() => this.kare());
  }

  arkaplan(renk) {
    this.scene.background = new THREE.Color(renk);
    if (this.golgeZemin) this.golgeZemin.material.color.set('#000');
  }

  boyutla() {
    const w = this.kap.clientWidth, h = this.kap.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.composer?.setSize(w, h);
    this.kamera.aspect = w / h;
    this.kamera.updateProjectionMatrix();
    if (this.nesne) this.cercevele(true);
  }

  // Yeni mobilyayı yerleştirir; eskisini temizler
  koy(nesne) {
    if (this.nesne) {
      this.scene.remove(this.nesne.grup);
      this.nesne.grup.traverse(o => o.geometry && o.geometry.dispose());
    }
    this.nesne = nesne;
    this.scene.add(nesne.grup);
    const { w, h, d } = nesne.boyut;
    const k = Math.max(w, d) + 1.6;
    this.zeminGolgesi.boyutla(k, h + 0.4);
    const s = Math.max(w, h, d) * 1.4 + 1;
    Object.assign(this.anaIsik.shadow.camera, { left: -s, right: s, top: s, bottom: -s });
    this.anaIsik.shadow.camera.updateProjectionMatrix();
    this.golgeKirli = true;
    this.cercevele(!this.kamIlk);
    this.kamIlk = true;
  }

  // Kamerayı nesneyi kadraja alacak uzaklığa götürür (yumuşak geçişle); kullanıcının seçtiği açıyı korur
  cercevele(aninda = false) {
    const { w, h, d } = this.nesne.boyut;
    const merkez = new THREE.Vector3(0, h * 0.48, 0);
    const yaricap = Math.sqrt(w * w + h * h + d * d) / 2;
    const fov = THREE.MathUtils.degToRad(this.kamera.fov);
    const yatayFov = 2 * Math.atan(Math.tan(fov / 2) * this.kamera.aspect);
    const uzak = (yaricap / Math.sin(Math.min(fov, yatayFov) / 2)) * (this.kadrajPayi || 1.22);
    let yon;
    if (this.kontrol && this.kamIlk && !aninda) yon = this.kamera.position.clone().sub(this.kontrol.target).normalize();
    else yon = new THREE.Vector3(Math.sin(this.aci.yatay) * Math.cos(this.aci.dikey), Math.sin(this.aci.dikey), Math.cos(this.aci.yatay) * Math.cos(this.aci.dikey));
    const konum = merkez.clone().addScaledVector(yon, uzak);
    if (aninda) {
      this.kamera.position.copy(konum);
      (this.kontrol ? this.kontrol.target : (this._bakis ||= new THREE.Vector3())).copy(merkez);
      this.kamera.lookAt(merkez);
      this.kamHedef.aktif = false;
    } else {
      this.kamHedef.konum.copy(konum);
      this.kamHedef.bakis.copy(merkez);
      this.kamHedef.aktif = true;
    }
    if (this.kontrol) {
      this.kontrol.minDistance = uzak * 0.45;
      this.kontrol.maxDistance = uzak * 2.2;
    }
  }

  // Basit ve şık oda: duvar, mikro beton görünümlü zemin, süpürgelik
  odaGoster(acik) {
    if (acik && !this.oda) {
      const g = new THREE.Group();
      const duvar = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), new THREE.MeshStandardMaterial({ color: '#e9e6df', roughness: 0.95 }));
      duvar.position.set(0, 3, -0.004);
      duvar.receiveShadow = true;
      // Açık renk mikro beton zemin: düşük kontrastlı, el yapımı dalgalanma dokusu
      const c = document.createElement('canvas');
      c.width = c.height = 512;
      const cx = c.getContext('2d');
      cx.fillStyle = '#d9d5ce';
      cx.fillRect(0, 0, 512, 512);
      const rnd = tohumlu(42);
      for (let i = 0; i < 900; i++) {
        const x = rnd() * 512, y = rnd() * 512, r = 6 + rnd() * 40;
        const grd = cx.createRadialGradient(x, y, 0, x, y, r);
        const a = rnd() * 0.05;
        grd.addColorStop(0, rnd() < 0.5 ? `rgba(255,255,255,${a})` : `rgba(90,80,70,${a})`);
        grd.addColorStop(1, 'rgba(0,0,0,0)');
        cx.fillStyle = grd;
        cx.fillRect(x - r, y - r, 2 * r, 2 * r);
      }
      const beton = new THREE.CanvasTexture(c);
      beton.colorSpace = THREE.SRGBColorSpace;
      beton.wrapS = beton.wrapT = THREE.RepeatWrapping;
      beton.repeat.set(14 / 2.5, 10 / 2.5);
      const zemin = new THREE.Mesh(new THREE.PlaneGeometry(14, 10).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ map: beton, roughness: 0.82 }));
      zemin.position.z = 4.996;
      zemin.receiveShadow = true;
      const sup = new THREE.Mesh(new THREE.BoxGeometry(14, 0.07, 0.012), new THREE.MeshStandardMaterial({ color: '#f3f1ec', roughness: 0.6 }));
      sup.position.set(0, 0.035, 0.002);
      g.add(duvar, zemin, sup);
      g.traverse(o => (o.userData.aoHaric = false));
      this.oda = g;
      this.scene.add(g);
    }
    if (this.oda) this.oda.visible = acik;
    this.golgeZemin.visible = !acik;
    if (this.nesne) {
      // Dolaplar duvara yaslanır, masalar odanın içinde durur
      const bosluk = this.nesne.duvaraYasla === false ? 0.7 : 0.002;
      this.nesne.grup.position.z = acik ? -0.004 + this.nesne.boyut.d / 2 + bosluk : 0;
    }
    this.golgeKirli = true;
  }

  kare() {
    if (!this.gorunur) return;
    if (this.kamHedef.aktif) {
      this.kamera.position.lerp(this.kamHedef.konum, 0.12);
      const hedef = this.kontrol ? this.kontrol.target : (this._bakis ||= new THREE.Vector3());
      hedef.lerp(this.kamHedef.bakis, 0.12);
      if (!this.kontrol) this.kamera.lookAt(hedef);
      if (this.kamera.position.distanceTo(this.kamHedef.konum) < 0.002) this.kamHedef.aktif = false;
    }
    this.onKare?.();
    this.kontrol?.update();
    if (this.golgeKirli && this.nesne) {
      // Zemin gölgesi mobilyanın konumuna göre çizilir (odada duvara yaslıysa da)
      this.zeminGolgesi.grup.position.set(0, 0, this.nesne.grup.position.z);
      this.zeminGolgesi.ciz([this.oda, this.golgeZemin].filter(Boolean));
      this.golgeKirli = !!this.animasyonda;
    }
    if (this.composer) this.composer.render();
    else this.renderer.render(this.scene, this.kamera);
  }

  // Ekran görüntüsü (yüksek çözünürlüklü tek kare)
  goruntu() {
    if (this.composer) this.composer.render(); else this.renderer.render(this.scene, this.kamera);
    return this.renderer.domElement.toDataURL('image/jpeg', 0.92);
  }
}
