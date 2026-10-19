"""Soft-edge matting, background detection, color maps and trimming on generated art."""

import random
import unittest

from PIL import Image, ImageDraw

from logo_sizes.imaging import (color_map, detect_background, remove_background,
                                trim_to_art)


CREAM = (250, 246, 238)
NAVY = (15, 35, 64)
ORANGE = (230, 120, 20)
DARK = (16, 16, 16)


def noisy_cream_disc(size=160, radius=50, noise=2, seed=1):
    """Cream background with per-pixel noise and an anti-aliased navy disc."""
    rng = random.Random(seed)
    scale = 4
    big = Image.new("RGB", (size * scale, size * scale), CREAM)
    center = size * scale // 2
    ImageDraw.Draw(big).ellipse((center - radius * scale, center - radius * scale,
                                 center + radius * scale, center + radius * scale), fill=NAVY)
    image = big.resize((size, size), Image.Resampling.LANCZOS)
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            r, g, b = pixels[x, y]
            if (r, g, b) == CREAM:
                pixels[x, y] = tuple(max(0, min(255, c + rng.randint(-noise, noise))) for c in (r, g, b))
    return image.convert("RGBA")


def luminance(pixel):
    r, g, b = pixel[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def edge_ring_max_luminance(image, radius=50, band=3):
    composite = Image.alpha_composite(Image.new("RGBA", image.size, DARK + (255,)), image)
    center = image.width / 2
    worst = 0
    for y in range(image.height):
        for x in range(image.width):
            distance = ((x + 0.5 - center) ** 2 + (y + 0.5 - center) ** 2) ** 0.5
            if radius - band <= distance <= radius + band:
                worst = max(worst, luminance(composite.getpixel((x, y))))
    return worst


class SoftMattingTests(unittest.TestCase):
    def test_hard_cut_leaves_a_light_halo_on_a_dark_surface(self):
        hard = remove_background(noisy_cream_disc(), CREAM, tolerance=4, mode="edge")
        self.assertGreater(edge_ring_max_luminance(hard), 120)

    def test_feathered_matte_leaves_no_halo_on_a_dark_surface(self):
        soft = remove_background(noisy_cream_disc(), CREAM, tolerance=4, mode="edge", feather=230)
        self.assertLess(edge_ring_max_luminance(soft), 70)
        self.assertEqual(soft.getpixel((80, 80)), NAVY + (255,))
        self.assertEqual(soft.getpixel((2, 2))[3], 0)

    def test_feathered_edge_mode_keeps_enclosed_background_colored_areas(self):
        image = Image.new("RGBA", (60, 60), CREAM + (255,))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 49, 49), fill=NAVY + (255,))
        draw.ellipse((22, 22, 37, 37), fill=CREAM + (255,))
        result = remove_background(image, CREAM, tolerance=4, mode="edge", feather=230)
        self.assertEqual(result.getpixel((30, 30)), CREAM + (255,))
        self.assertEqual(result.getpixel((1, 1))[3], 0)

    def test_feathered_all_mode_clears_enclosed_background_color(self):
        image = Image.new("RGBA", (60, 60), CREAM + (255,))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 49, 49), fill=NAVY + (255,))
        draw.ellipse((22, 22, 37, 37), fill=CREAM + (255,))
        result = remove_background(image, CREAM, tolerance=4, mode="all", feather=230)
        self.assertEqual(result.getpixel((30, 30))[3], 0)

    def test_feather_zero_matches_the_previous_hard_behaviour(self):
        image = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        ImageDraw.Draw(image).rectangle((4, 4, 15, 15), fill=(0, 0, 0, 255))
        hard = remove_background(image, (255, 255, 255), tolerance=0, mode="edge")
        self.assertEqual(sorted(set(hard.getchannel("A").getdata())), [0, 255])


class BackgroundDetectionTests(unittest.TestCase):
    def test_detects_border_color_and_noise_based_tolerance(self):
        detected = detect_background(noisy_cream_disc(noise=2))
        for channel, expected in zip(detected.color, CREAM):
            self.assertLessEqual(abs(channel - expected), 2)
        self.assertGreaterEqual(detected.tolerance, 2)
        self.assertLessEqual(detected.tolerance, 12)
        # The ramp should span the cream-to-navy contrast so edge alpha matches coverage.
        self.assertGreaterEqual(detected.feather, 180)
        self.assertLessEqual(detected.feather, 240)

    def test_detection_tolerates_a_nearly_opaque_antialiased_border(self):
        image = noisy_cream_disc(noise=0)
        edge = Image.new("L", image.size, 254)
        edge.paste(Image.new("L", (image.width - 2, image.height - 2), 255), (1, 1))
        image.putalpha(edge)
        detected = detect_background(image)
        self.assertEqual(detected.color, CREAM)

    def test_detection_refuses_a_transparent_border(self):
        image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 10, 29, 29), fill=NAVY + (255,))
        with self.assertRaises(ValueError):
            detect_background(image)


class ColorMapTests(unittest.TestCase):
    def shield(self):
        image = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((5, 5, 54, 54), fill=NAVY + (255,))
        draw.rectangle((15, 15, 44, 44), fill=CREAM + (255,))
        draw.rectangle((25, 25, 34, 34), fill=ORANGE + (255,))
        image.putpixel((16, 16), (248, 244, 236, 255))
        return image

    def test_maps_outline_to_white_and_enclosed_fill_to_clear(self):
        result = color_map(self.shield(), [
            {"from": NAVY, "to": (255, 255, 255), "tolerance": 0},
            {"from": CREAM, "to": None, "tolerance": 4},
        ])
        self.assertEqual(result.getpixel((7, 7)), (255, 255, 255, 255))
        self.assertEqual(result.getpixel((20, 20))[3], 0)
        self.assertEqual(result.getpixel((16, 16))[3], 0)
        self.assertEqual(result.getpixel((30, 30)), ORANGE + (255,))
        self.assertEqual(result.getpixel((1, 1))[3], 0)

    def test_map_with_feather_blends_near_colors_partially(self):
        image = Image.new("RGBA", (4, 1), (0, 0, 0, 0))
        image.putpixel((0, 0), NAVY + (255,))
        image.putpixel((1, 0), (15 + 20, 35 + 20, 64 + 20, 255))
        image.putpixel((2, 0), (15 + 80, 35 + 80, 64 + 80, 255))
        result = color_map(image, [{"from": NAVY, "to": (255, 255, 255), "tolerance": 10, "feather": 20}])
        self.assertEqual(result.getpixel((0, 0)), (255, 255, 255, 255))
        half = result.getpixel((1, 0))
        for channel, source in zip(half[:3], (35, 55, 84)):
            self.assertAlmostEqual(channel, (source + 255) / 2, delta=2)
        self.assertEqual(result.getpixel((2, 0)), (95, 115, 144, 255))


class TrimTests(unittest.TestCase):
    def test_trim_crops_to_the_opaque_bounding_box(self):
        image = Image.new("RGBA", (100, 80), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((20, 10, 59, 49), fill=NAVY + (255,))
        image.putpixel((90, 70), NAVY + (3,))
        trimmed, box = trim_to_art(image, threshold=8)
        self.assertEqual(trimmed.size, (40, 40))
        self.assertEqual(box, (20, 10, 60, 50))

    def test_trim_with_zero_threshold_keeps_faint_pixels(self):
        image = Image.new("RGBA", (100, 80), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((20, 10, 59, 49), fill=NAVY + (255,))
        image.putpixel((90, 70), NAVY + (3,))
        trimmed, _ = trim_to_art(image, threshold=0)
        self.assertEqual(trimmed.size, (71, 61))


if __name__ == "__main__":
    unittest.main()


class ReviewFindingMattingTests(unittest.TestCase):
    def test_feathered_edge_mode_does_not_cross_a_one_pixel_outline(self):
        image = Image.new("RGBA", (60, 60), CREAM + (255,))
        ImageDraw.Draw(image).rectangle((15, 15, 44, 44), outline=NAVY + (255,), width=1)
        result = remove_background(image, CREAM, tolerance=4, mode="edge", feather=230)
        self.assertEqual(result.getpixel((30, 30)), CREAM + (255,))
        self.assertEqual(result.getpixel((17, 17)), CREAM + (255,))
        self.assertEqual(result.getpixel((2, 2))[3], 0)
