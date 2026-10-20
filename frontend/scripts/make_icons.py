"""Genera los íconos PNG de la app (monograma «PC» dorado sobre fondo oscuro).

Uso (necesita Pillow): python frontend/scripts/make_icons.py
Los PNG resultantes se guardan en frontend/public/icons y SÍ se suben al repositorio, así que este script solo
hace falta si quieres cambiar el diseño.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "public" / "icons"
BG, GOLD, LINE = (10, 10, 12), (201, 169, 106), (201, 169, 106, 90)
FONT = next((p for p in (r"C:\Windows\Fonts\georgiab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf") if Path(p).exists()), None)


def draw(size: int, maskable: bool) -> Image.Image:
    scale = 4  # se dibuja grande y se reduce: bordes suaves
    s = size * scale
    img = Image.new("RGBA", (s, s), BG + (255,))
    d = ImageDraw.Draw(img)
    if not maskable:  # «any»: cuadrado redondeado con borde fino; «maskable»: sin bordes, el sistema lo recorta
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=255)
        img.putalpha(mask)
        d.rounded_rectangle((s * 0.03, s * 0.03, s * 0.97, s * 0.97), radius=int(s * 0.2), outline=LINE, width=max(2, s // 120))
    # en maskable el contenido debe caber en el 80 % central (zona segura)
    target = s * (0.46 if maskable else 0.5)
    font = ImageFont.truetype(FONT, int(target)) if FONT else ImageFont.load_default()
    box = d.textbbox((0, 0), "PC", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((s - w) / 2 - box[0], (s - h) / 2 - box[1]), "PC", font=font, fill=GOLD)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw(size, False).save(OUT / f"icon-{size}.png", optimize=True)
        draw(size, True).convert("RGB").save(OUT / f"icon-maskable-{size}.png", optimize=True)
    draw(180, True).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)  # iPhone: sin transparencia
    print("íconos en", OUT)


if __name__ == "__main__":
    main()
