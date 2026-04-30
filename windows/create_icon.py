"""Erzeugt windows/icon.ico für PyInstaller und Inno Setup."""

import os
from PIL import Image, ImageDraw, ImageFont


def create_icon(output_path: str = "windows/icon.ico"):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        margin = max(1, size // 16)
        d.ellipse([margin, margin, size - margin - 1, size - margin - 1], fill="#2563eb")

        font_size = max(8, int(size * 0.48))
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("Arial Bold.ttf", font_size)
            except OSError:
                font = ImageFont.load_default(size=font_size)

        bbox = d.textbbox((0, 0), "M", font=font)
        x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
        y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
        d.text((x, y), "M", fill="white", font=font)
        images.append(img)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Icon erstellt: {output_path}")


if __name__ == "__main__":
    create_icon()
