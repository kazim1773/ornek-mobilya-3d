# Örnek Mobilya: 3D mobilya sitesi demosu

Mobilya üreticileri ve mağazaları için hazırlanmış bir demo. Müşteri mobilyaları gerçek ölçüleriyle 3D olarak
inceleyebiliyor, kendi odasına yerleştirebiliyor ve ölçüye özel üretimin nasıl çalıştığını bir montaj
animasyonunda görüyor. Marka adı, ürünler, fiyatlar ve iletişim bilgileri örnektir; her firma için değiştirilir.

**Canlı site:** https://kazim1773.github.io/ornek-mobilya-3d/

## İçerik

| Klasör / dosya | Ne var |
|---|---|
| `site/` | Örnek Mobilya mağaza sitesi (`magaza.html`): açılışta Blender'da render edilmiş montaj animasyonu, ürün kataloğu, ürün sayfaları, sepet ve sitenin içine gömülü 3D oda planlayıcı (`planlayici.html`) |
| `site/montaj/` | Kapak animasyonu: `kapak.mp4` (160 kare, 45 fps) ve video oynatılamayan cihazlar için kare kare yedek resimler |
| `site/modeller/` | Planlayıcıdaki 3D mobilya modelleri (`.glb` içeriği base64 olarak `.json` içinde) |
| `oda-planlayici.html` | Tek başına çalışan ilk oda planlayıcı sürümü |
| `demo/` | Ölçüye göre raf ve masa üreten 3D motoru (`mobilya.js`), kitaplık montaj animasyonu sayfası (`montaj.html`), ahşap dokuları ve stüdyo ışığı |
| `blender/` | Montaj animasyonunu Blender Cycles ile render eden betik (`kitaplik.py`), kareleri web videosuna çeviren betik (`video.py`), render kareleri ve kaydırmalı kapak sayfası (`kapak.html`) |
| `modeller/` | Planlayıcı modellerinin özgün `.glb` dosyaları |
| `araclar/` | Yardımcı betikler: glTF paketleme, `.glb` → `.json`, MP4 hızlı başlatma, yerel geliştirme sunucusu, Chrome/Safari test betiği |

## Yerelde çalıştırma

Sayfalar dosyaları `fetch` ile okuduğu için bir yerel sunucu gerekir:

```bash
python araclar/sunucu.py 8765
```

Sonra tarayıcıda `http://localhost:8765/site/magaza.html` adresini açın.

## GitHub Pages

Site GitHub Pages'te `main` dalının kökünden yayınlanır; kökteki `index.html` ziyaretçiyi `site/`'e yönlendirir.
`site/magaza.html` belge iskeleti olmadan yazıldığı için (claude.ai yayını bunu kendisi ekler) Pages için
`site/index.html` üretilir. `magaza.html` her değiştiğinde:

```bash
python araclar/pages_hazirla.py
```

## Montaj animasyonunu yeniden render etme

[Blender](https://www.blender.org/) 5.x gerekir.

```bash
blender --background --factory-startup --python blender/kitaplik.py -- animasyon bas=1 son=160 cikti=kareler ornek=64
blender --background --factory-startup --python blender/video.py -- fps=45 cikti=kapak.mp4
python araclar/hizli_baslat.py blender/kapak.mp4 site/montaj/kapak.mp4
```

## Testler

`araclar/tarayici_testi.py`, kapak animasyonunu Chrome (masaüstü ve Android) ile Safari motoru WebKit'te
(masaüstü ve iPhone) [Playwright](https://playwright.dev/python/) kullanarak dener: animasyon oynuyor mu, yazılar
üst üste biniyor mu, telefonda başlık ve düğmeler ilk ekrana sığıyor mu.

```bash
python araclar/tarayici_testi.py http://localhost:8765/site/magaza.html sonuclar
```

## Kaynaklar ve lisanslar

- 3D mobilya modelleri, ürün görselleri, ahşap dokuları ve stüdyo ışık haritası: [Poly Haven](https://polyhaven.com) (CC0, ticari kullanım serbest)
- 3D çizim: [three.js](https://threejs.org), gerçekçi fotoğraf: [three-gpu-pathtracer](https://github.com/gkjohnson/three-gpu-pathtracer)
- Yazı tipleri: Google Fonts (Bricolage Grotesque, Figtree, Instrument Serif, Hanken Grotesk, IBM Plex Mono)
