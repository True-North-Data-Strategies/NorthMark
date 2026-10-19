"""Create a generic geometric example in the ignored local artwork folder."""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    target = Path(__file__).resolve().parents[1] / "local-assets" / "input" / "demo-mark.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(256, 48), (464, 256), (256, 464), (48, 256)], fill="#d95f02")
    draw.polygon([(256, 136), (376, 256), (256, 376), (136, 256)], fill="#222222")
    draw.ellipse((208, 208, 304, 304), fill="#ffffff")
    # Exclusive creation keeps an existing example or a user's replacement safe.
    with target.open("xb") as output:
        image.save(output, format="PNG")
    print(f"Created generic example: {target}")


if __name__ == "__main__":
    main()
