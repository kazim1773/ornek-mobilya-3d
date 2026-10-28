"""Render edilmiş kare dizisini (kareler/kare_####.jpg) web için tek bir H.264 MP4 videoya çevirir.

Kullanım: blender --background --factory-startup --python video.py -- fps=45 cikti=kapak.mp4
Kareler zaten renk dönüşümünden geçmiş JPEG'ler olduğu için burada "Standard" görünüm kullanılır;
aksi halde Blender görüntüyü ikinci kez tonlayıp soluklaştırır.
"""
import os
import sys

import bpy

KOK = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SEC = dict(a.split("=", 1) for a in argv if "=" in a)
KARELER = os.path.join(KOK, "kareler")

dosyalar = sorted(f for f in os.listdir(KARELER) if f.startswith("kare_") and f.endswith(".jpg"))
sahne = bpy.context.scene
duzen = sahne.sequence_editor_create()
seritler = duzen.strips if hasattr(duzen, "strips") else duzen.sequences  # Blender 4.4+ "strips"
serit = seritler.new_image("kareler", os.path.join(KARELER, dosyalar[0]), channel=1, frame_start=1)
for f in dosyalar[1:]:
    serit.elements.append(f)

sahne.frame_start = 1
sahne.frame_end = len(dosyalar)
r = sahne.render
r.fps = int(SEC.get("fps", 45))
r.fps_base = 1.0
r.resolution_x, r.resolution_y, r.resolution_percentage = 1280, 720, 100
sahne.view_settings.view_transform = "Standard"
sahne.view_settings.look = "None"
sahne.view_settings.exposure = 0
sahne.view_settings.gamma = 1
if hasattr(r.image_settings, "media_type"):  # Blender 5: önce çıkış türü video seçilir
    r.image_settings.media_type = "VIDEO"
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = SEC.get("kalite", "HIGH")
r.ffmpeg.ffmpeg_preset = "BEST"
r.ffmpeg.gopsize = 12
r.ffmpeg.audio_codec = "NONE"
r.filepath = os.path.join(KOK, SEC.get("cikti", "kapak.mp4"))
r.use_file_extension = False
bpy.ops.render.render(animation=True)
print("VIDEO", r.filepath, len(dosyalar), "kare", r.fps, "fps")
