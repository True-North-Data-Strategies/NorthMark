<!-- TNDS-HEADER:BEGIN -->
<div align="center">
  <h1>Create Logos All Sizes</h1>
  <h3>Makes logo sizes, color variants and brand kits from your source artwork.</h3>
  <img src="https://raw.githubusercontent.com/Jjohnston70/Jjohnston70/main/true-north-logo-layered-v3.png" alt="True North Data Strategies" width="240" />
  <br /><br />
  <a href="#stack"><img src="https://img.shields.io/badge/Built%20with-Python%20%7C%20Pillow-0A8EA0?style=for-the-badge" alt="Built with Python | Pillow" /></a>
  <a href="https://truenorthstrategyops.com"><img src="https://img.shields.io/badge/Built%20by-TNDS-1F6FEB?style=for-the-badge" alt="Built by TNDS" /></a>
  <a href="#contact"><img src="https://img.shields.io/badge/Contact-TNDS-181717?style=for-the-badge" alt="Contact" /></a>
</div>
<!-- TNDS-HEADER:END -->

## Table of Contents

[What This Is](#what-this-is) | [Quick start](#quick-start) |
[Keep your artwork private](#keep-your-artwork-private) | [Color versions](#color-versions) |
[Background removal](#explicit-background-removal) | [Layouts](#horizontal-stacked-and-symbol-artwork) |
[SVG originals](#svg-originals) | [Kit contents](#what-is-in-a-kit) |
[Standard sizes](#standard-export-sizes) | [Safe reruns](#safe-reruns-and-other-folders) |
[Development](#development-and-installation) | [Stack](#stack) | [License](#license) | [Contact](#contact)

## What This Is

Turn source artwork into correctly proportioned PNGs, optional lossless WebP files,
color variants, browser/app icons, previews and a ZIP you can hand to someone else.
Runs locally. No account, upload service or AI is required.

## Quick start

Requires Python 3.10 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p local-assets/input
```

On Windows, use `python` instead of `python3` and activate with
`.venv\Scripts\activate`. You can create `local-assets/input` in Explorer.

Put your original images in `local-assets/input`, then run:

```sh
python make_logo_sizes.py
```

Each image gets its own folder and ZIP under `local-assets/exports`. The default
keeps the original colors, fits the complete source inside each canvas, and adds
8% padding per side. Nothing is cropped or stretched. Existing output is refused.

To try the tool without your own artwork:

```sh
python examples/make_demo.py
python make_logo_sizes.py local-assets/input/demo-mark.png --variants all
```

The example is a generic geometric mark generated locally; no brand artwork ships
with this repository.

## Keep your artwork private

```text
create-logos-all-sizes/
  make_logo_sizes.py       command you run
  logo_sizes/             public program code
  tests/                  tests generate their own temporary artwork
  examples/               generic example generator
  local-assets/           IGNORED BY GIT: keep all your own material here
    input/                original artwork
    exports/              generated kits, previews and ZIPs
      example/
      example.zip
      .backups/           previous kits kept by --overwrite
    archive/              optional old files or other private material
```

The entire `local-assets/` folder is ignored, including product and client files.
Common artwork and archive extensions are also ignored outside that folder to
reduce accidental additions. Git ignore is not encryption or access control, and
`git add -f` can bypass it. Never force-add your artwork to a public repository.

Before publishing changes, run:

```sh
python tools/check_public_files.py
```

This checks tracked filenames and obvious credential patterns. Review your staged
changes too; it cannot recognize every private detail inside an arbitrary text file.
The Python package explicitly includes only `logo_sizes`, not `local-assets`.

## Color versions

```sh
python make_logo_sizes.py --variants all
python make_logo_sizes.py --variants original white black
python make_logo_sizes.py --variants grayscale inverted
```

| Version | Result |
| --- | --- |
| `original` | Original colors and existing transparency |
| `white` | White artwork with the source alpha channel |
| `black` | Black artwork with the source alpha channel |
| `grayscale` | Neutral shades with the source alpha channel |
| `inverted` | Every RGB color negated; transparency stays the same |

White and black versions need transparent source artwork. The tool refuses an
opaque source for those versions so it does not silently produce a solid rectangle.
An automatic color negative changes brand colors; inspect it before using it as a
brand's reverse version. A designer-supplied reverse source may be more suitable.

## Explicit background removal

Converting an image to PNG does not remove its background. For a clean, flat
background, you can choose the background color yourself:

```sh
python make_logo_sizes.py logo.png --remove-background "#ffffff" --variants all
python make_logo_sizes.py logo.png --remove-background white --tolerance 8
```

The default `edge` mode removes matching regions connected to the image boundary.
It preserves enclosed details, such as a white feature inside a black shape.
Tolerance is the maximum difference in any RGB channel, from 0 to 255; the default
is an exact match. Low values are safer.

To remove matching colors everywhere, including enclosed details, explicitly use:

```sh
python make_logo_sizes.py logo.png --remove-background white --background-mode all
```

Background removal is not a substitute for a clean transparent master. Textured
backgrounds, shadows and antialiased edges need careful inspection. The tool never
guesses which color should be removed. An original copy remains in the kit.

## Horizontal, stacked and symbol artwork

Provide a separate source design for each layout. The tool sizes them; it does not
rearrange lettering, invent a symbol or trace raster artwork into vector paths.
Use custom rectangular canvases for horizontal logos and banners:

```sh
python make_logo_sizes.py brand-horizontal.png --size header=1200x300 --size signature=600x150
python make_logo_sizes.py brand-stacked.png --size stacked=800x1000
python make_logo_sizes.py brand-symbol.png --group web --variants all
```

Custom sizes replace the standard list unless you also select a `--group` or
`--preset`, in which case they are added. Each name must be unique. Padding is a
fraction of each canvas dimension on each side:

```sh
python make_logo_sizes.py --padding 0.12
python make_logo_sizes.py --no-upscale
python make_logo_sizes.py --formats png webp
```

`--no-upscale` keeps raster artwork at or below its source pixel dimensions inside
the requested canvas. Raster enlargement otherwise produces a warning. PNG/WebP
exports use RGB color; print size, DPI and CMYK requirements belong to your printer's
specifications, not the preset's pixel count.

## SVG originals

Install optional SVG support:

```sh
python -m pip install -e ".[svg]"
```

CairoSVG also needs the Cairo system library. On macOS, install it with
`brew install cairo`; on Debian/Ubuntu use `sudo apt-get install libcairo2`.
For Windows setup, see the [CairoSVG installation instructions](https://cairosvg.org/documentation/).
Raster inputs work without CairoSVG or Cairo.

Provide a plain, self-contained SVG with a `viewBox` or numeric pixel width and
height. Path-based artwork is preferable to text that depends on installed fonts.
External resources, embedded images, stylesheets, scripts, entities and unsupported
SVG elements are refused. Export SVG styles as inline attributes if necessary.

The original SVG is copied unchanged to `masters/source.svg`. It stays vector.
PNG and WebP outputs are rendered derivatives. The tool does not create a true
vector master from a PNG or JPEG. SVG features supported by CairoSVG have limits;
check the output against your source.

## What is in a kit

- A folder for each selected color version, containing the requested image sizes.
- `app-icons/` per version: six-size `favicon.ico`, 192/512 regular and maskable
  icons, an opaque 180px Apple touch icon, and a web manifest icon fragment.
- `preview.png` and `preview.html`: white, dark and checkerboard backgrounds with
  16, 32 and 48 pixel samples to reveal unreadable details.
- `masters/source.*`: the untouched original, including any source metadata.
- `GUIDE.txt`: which files to use and the important limitations.
- `kit.json`: options, source checksum, notes and file checksums, without absolute
  local paths.
- A sibling ZIP containing only that complete kit.

Maskable icons get extra padding to keep the complete artwork inside the safe
circle. Their backgrounds are opaque. White variants default to a dark background;
other variants default to white. Override every variant's icon background with
`--icon-background "#123456"`. Merge `manifest.webmanifest`'s icon entries into your
application manifest and adjust paths; the fragment is not a complete app manifest.

Skip parts with `--no-icons`, `--no-preview` or `--no-zip`.

## Standard export sizes

Use `--list` for the complete list. The original 15 presets remain available:

| Group | Sizes in pixels |
| --- | --- |
| `youtube` | Watermark 150, profile 800 |
| `web` | 16, 32, 180, 192, 512 |
| `social` | LinkedIn 400, X 400, Facebook 500, Instagram 320 |
| `docs` | Document 600, email 200, slide 1000 |
| `master` | 2048 raster derivative |

```sh
python make_logo_sizes.py --group web
python make_logo_sizes.py --preset favicon-32
python make_logo_sizes.py --list
```

These are convenient starting sizes, not current platform acceptance guarantees.
Requirements can change. `master-2048.png` is an export, not a replacement for the
untouched original or a vector master.

## Safe reruns and other folders

```sh
python make_logo_sizes.py --dry-run
python make_logo_sizes.py --overwrite
python make_logo_sizes.py -i /path/to/originals -o /path/to/exports
```

`--overwrite` backs up the previous entire kit and ZIP before publishing the new
ones. Files you added inside the old kit are preserved in that backup. Failed
builds do not replace a previous kit. Duplicate output names are caught before any
batch writes. Rename colliding sources such as `brand.png` and `brand.jpg`.

Dry runs check paths, names and options, but do not decode or validate artwork.
A failed source produces a nonzero exit status; other valid sources can still
finish. An output lock prevents two processes from publishing into the same output
folder at once. If a run is killed, remove `.logo-kit.lock` only after checking that
no export is still running.

## Development and installation

```sh
python -m pip install -e ".[svg]"
python -m unittest discover -s tests -v
python tools/check_public_files.py
```

You can also run `python -m logo_sizes` or the installed `logo-sizes` command.
When run from the checkout, default folders belong to the checkout. A standalone
package installation uses `local-assets` in the current working directory.

Tests create temporary generic images and exercise real exports, pixels,
transparency, background removal, duplicate protection, backups, icons, ZIPs and
SVG refusal rules. CI runs the suite with SVG support on Python 3.10, 3.12 and 3.14.

## License

[MIT](LICENSE) for the software. No personal or client artwork is included.
The software license grants no rights to any source artwork you process.

## Stack

| Layer | Tools |
| --- | --- |
| Runtime | Python 3.10 or newer |
| Image processing | Pillow |
| Optional SVG rendering | CairoSVG and Cairo |
| Checks | Python unittest, GitHub Actions and the public-file check |

<!-- TNDS-FOOTER:BEGIN -->
## Contact

Jacob Johnston | True North Data Strategies LLC, SDVOSB | Colorado Springs, Colorado

jacob@truenorthstrategyops.com | [truenorthstrategyops.com](https://truenorthstrategyops.com) | [pipelinepunks.com](https://pipelinepunks.com)
<!-- TNDS-FOOTER:END -->
