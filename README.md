<!-- TNDS-HEADER:BEGIN -->
<div align="center">
  <h1>NorthMark</h1>
  <h3>One clean master in, a digital kit and print-ready transfers out.</h3>
  <img src="https://raw.githubusercontent.com/Jjohnston70/Jjohnston70/main/true-north-logo-layered-v3.png" alt="True North Data Strategies" width="240" />
  <br /><br />
  <a href="#stack"><img src="https://img.shields.io/badge/Built%20with-Python%20%7C%20Pillow-0A8EA0?style=for-the-badge" alt="Built with Python | Pillow" /></a>
  <a href="https://truenorthstrategyops.com"><img src="https://img.shields.io/badge/Built%20by-TNDS-1F6FEB?style=for-the-badge" alt="Built by TNDS" /></a>
  <a href="#contact"><img src="https://img.shields.io/badge/Contact-TNDS-181717?style=for-the-badge" alt="Contact" /></a>
</div>
<!-- TNDS-HEADER:END -->

## Quick start

**Start here: [Ghostty user manual](docs/USER-MANUAL.md)** for plain-language,
copy-and-paste steps from one image through the final delivery ZIP.


**Already installed? Put your image in `local-assets/input`, then run these commands.**
This macOS example assumes the project is in `~/Pictures/NorthMark`. Change the
`cd` path if you saved it somewhere else. For a new installation, do the
[first-time setup](#first-time-setup) first.

```sh
cd "$HOME/Pictures/NorthMark"
source .venv/bin/activate
python make_logo_sizes.py "local-assets/input/Your Logo.png"
```

Replace `Your Logo.png` with the exact filename, including its extension. Keep both
quotes around the path, especially when the filename contains spaces. Do not add
backslashes before spaces or underscores inside those quotes. If the terminal shows
a continuation prompt instead of running, press **Ctrl+C** and paste the complete command again.

The path must match the file's location: an image inside `input` needs
`local-assets/input/` in the command. If you put it directly in `local-assets`, use
`"local-assets/Your Logo.png"` instead. A "Source is missing or unsupported" error
means you should check the folder, filename and supported file type.

### Open the result

On macOS, open the exports folder:

```sh
open "local-assets/exports"
```

Open the folder named after your image, then open `preview.html`. The matching ZIP
beside that folder is the complete kit to share. The default keeps the original
colors, fits the complete source inside each canvas, and adds 8% padding per side.
Nothing is cropped or stretched.

### Choose the next command

Run these from the project folder with `.venv` active. Replace the example filename
in each command. Choose the task you need; these are not steps to run in sequence.

| Task | Command |
| --- | --- |
| Rebuild the same kit, keeping a dated backup | `python make_logo_sizes.py "local-assets/input/Your Logo.png" --overwrite` |
| Add every standard color version to a transparent logo | `python make_logo_sizes.py "local-assets/input/Your Logo.png" --variants all --overwrite` |
| Create a DTF transfer for the left chest | `python make_logo_sizes.py dtf "local-assets/input/Your Logo.png" --placement left-chest` |
| List available print placements and sizes | `python make_logo_sizes.py dtf --list-placements` |
| Process all images directly inside the input folder | `python make_logo_sizes.py` |

Existing output is refused unless you add `--overwrite`. White and black color
versions require transparent artwork; see [background removal](#background-removal)
if your image has a solid background. DTF output goes into the design's `dtf/`
folder and reports whether the source has enough resolution for the print size.
See [DTF quick start](#dtf-quick-start) for print outputs and resolution checks.

For the complete sequence, use the [ReelRoots walkthrough](#reelroots-walkthrough).
For a single folder and ZIP containing all outputs, use [Bundle everything](#bundle-everything).

## Contents

[Quick start](#quick-start) | [ReelRoots walkthrough](#reelroots-walkthrough) | [Bundle everything](#bundle-everything) | [Troubleshooting](#troubleshooting) | [What this is](#what-this-is) | [First-time setup](#first-time-setup) | [DTF quick start](#dtf-quick-start) |
[Gang sheets](#gang-sheets) | [Keep your artwork private](#keep-your-artwork-private) |
[Color versions](#color-versions) | [Background removal](#background-removal) |
[Config reference](#config-reference) | [One master does it all](#one-master-does-it-all-when-it-does-and-when-it-doesnt) |
[Artwork layouts](#horizontal-stacked-and-symbol-artwork) | [SVG originals](#svg-originals) | [What is in a kit](#what-is-in-a-kit) | [Export sizes](#export-sizes) |
[Safe reruns](#safe-reruns-and-other-folders) | [Development](#development-and-installation) | [Developer notes](#developer-notes) | [Manuals](#manuals)

## ReelRoots walkthrough

Run these blocks in order from a macOS terminal. Commands that rebuild outputs are
marked below. The source artwork stays in `local-assets`; none is included in the repository.

### 1. Enter the project and build the digital kit

```sh
cd "/Users/jj-personal/Pictures/NorthMark"
source .venv/bin/activate
```

Change the `cd` path on another computer. The remaining steps use a source named
`ReelRoots.png` in `local-assets/input`, which produces the output folder `reelroots`.
Use that filename consistently. If your source has a longer name, you can rename it
in Finder before starting, or substitute its matching output folder throughout.

```sh
python make_logo_sizes.py "local-assets/input/ReelRoots.png"
open "local-assets/exports/reelroots/preview.html"
```

If the kit already exists, add `--overwrite` to back it up and rebuild it.
These are alternative source paths, not extra steps to run:

| Source location or name | Kit command | Output folder under `local-assets/exports` |
| --- | --- | --- |
| Image directly in `local-assets` | `python make_logo_sizes.py "local-assets/your-image.png"` | `your-image` |
| Original long filename inside `input` | `python make_logo_sizes.py "local-assets/input/ReelRoots_ Cinematic Family Memories.png"` | `reelroots-cinematic-family-memories` |

For the long filename, its kit preview opens with:

```sh
open "local-assets/exports/reelroots-cinematic-family-memories/preview.html"
```

Do not mix this longer output path with `reelroots`. The path printed after `DONE:`
is the actual destination. The wildcard commands below are convenient only when
**exactly one** PNG starts with `ReelRoots` in `input`. Otherwise use the exact quoted
source path. Leave `*` unquoted and do not put a backslash before it.

### 2. Create the left-chest transfer

```sh
python make_logo_sizes.py dtf local-assets/input/ReelRoots*.png --placement left-chest
open "local-assets/exports/reelroots/dtf"
```

If DTF output already exists, add `--overwrite`. If the source has a solid background
that you want removed, rebuild with automatic background removal:

```sh
python make_logo_sizes.py dtf local-assets/input/ReelRoots*.png --placement left-chest --remove-background auto --overwrite
open "local-assets/exports/reelroots/dtf/mockups"
```

Inspect the mockups to confirm the background is gone and fine details remain intact.
Automatic removal estimates the border color; it is not a guarantee of a clean cutout.

### 3. Add the full-front transfer and review both

```sh
python make_logo_sizes.py dtf local-assets/input/ReelRoots*.png --placement left-chest --placement full-front --remove-background auto --overwrite
open "local-assets/exports/reelroots/dtf/order-sheet.csv"
open "local-assets/exports/reelroots/dtf/mockups"
open "local-assets/exports/reelroots/dtf/adult"
```

Omit `--remove-background auto` if you want to retain the background. Include both
placements when rebuilding: `--overwrite` replaces the design's entire `dtf/`
folder and keeps the previous output in a dated backup.

Check the final written/refused counts, exact inches, source DPI, thin-stroke warnings
and garment contrast. **Do not build a gang sheet until every listed transfer exists.**
A run can print `DONE` while refusing one placement for insufficient resolution.

### 4. Resolve a refused full-front transfer

Skip this step if both transfers were written. The observed 11.00 x 9.97 inch
full-front attempt had only 107 source DPI and was refused. At 300 DPI, that size
needs at least 3300 x 2991 pixels of actual artwork after trimming. Prefer a larger
original or a genuine vector source, then rerun step 3 with that source.

For a **layout proof using the current low-resolution image**, explicitly allow it:

```sh
python make_logo_sizes.py dtf local-assets/input/ReelRoots*.png --placement left-chest --placement full-front --remove-background auto --allow-low-dpi --overwrite
```

This bypasses refusal and enlarges the image; it does not restore detail. The exported
PNG's 300 DPI tag does not change the original's 107 DPI at that print size. A gang
sheet or ZIP made from this output still contains that low-resolution transfer.

### 5. Create the gang-sheet job file

This example requests one copy of each placement. Change `qty` for the quantities
you need and confirm the sheet dimensions with your printer. Paste the entire block,
including the final `YAML` on its own line. This replaces an existing job file of the same name.

```sh
mkdir -p local-assets/orders
cat > local-assets/orders/reelroots-gang.yaml <<'YAML'
job: reelroots-gang

sheet:
  width_in: 22
  lengths_ft: [2, 5, 10]
  gap_in: 0.25
  margin_in: 0.5
  rotate: true

items:
  - design: reelroots
    placement: left-chest
    variant: original
    qty: 1
  - design: reelroots
    placement: full-front
    variant: original
    qty: 1
YAML
```

If your output folder has a different name, change both `design` values to that name.

### 6. Build and inspect the gang sheet

```sh
python make_logo_sizes.py gang local-assets/orders/reelroots-gang.yaml
open "local-assets/exports/gang-sheets/reelroots-gang"
```

Review `preview.png`, `cut-list.csv` and `layout.json`. If you change quantities or
regenerate a transfer, rebuild the gang sheet; it does not update automatically:

```sh
python make_logo_sizes.py gang local-assets/orders/reelroots-gang.yaml --overwrite
```

The generated sheet PNG and PDF contain raster artwork. Confirm the printer's current
accepted format before upload. For individual transfer orders, use each placement's
PNG and the exact dimensions in `order-sheet.csv`. Package the results below.

## Bundle everything

The automatically generated `local-assets/exports/reelroots.zip` is the **digital kit**
from the kit command. It is not updated when DTF files or gang sheets are generated.
Use a separate delivery bundle to collect the current outputs.

After the digital kit, DTF transfers and gang sheet have been built, run this whole
block on macOS from the project root. It checks for the required outputs, creates a
unique delivery folder and stops if a copy fails. The optional longer-name folder
preserves a digital kit created before the source was renamed to `ReelRoots.png`.

```sh
(
  set -e
  test -f "local-assets/exports/reelroots/kit.json" || test -f "local-assets/exports/reelroots-cinematic-family-memories/kit.json"
  test -f "local-assets/exports/reelroots/dtf/dtf.json"
  test -f "local-assets/exports/gang-sheets/reelroots-gang/layout.json"
  test -f "local-assets/orders/reelroots-gang.yaml"
  mkdir -p "local-assets/dist"
  bundle_dir=$(mktemp -d "local-assets/dist/reelroots-delivery-XXXXXX")
  ditto "local-assets/exports/reelroots" "$bundle_dir/reelroots"
  ditto "local-assets/exports/gang-sheets/reelroots-gang" "$bundle_dir/gang-sheet"
  cp "local-assets/orders/reelroots-gang.yaml" "$bundle_dir/reelroots-gang.yaml"
  if [ -d "local-assets/exports/reelroots-cinematic-family-memories" ]; then
    ditto "local-assets/exports/reelroots-cinematic-family-memories" "$bundle_dir/digital-kit"
  fi
  ditto -c -k --sequesterRsrc --keepParent "$bundle_dir" "${bundle_dir}.zip"
  unzip -tq "${bundle_dir}.zip"
  open "local-assets/dist"
)
```

Keep the delivery folder for browsing and share the matching ZIP. It includes kit
assets and source masters when present, DTF files, mockups, the order sheet, gang
sheets and the job YAML. It does not copy unrelated designs or `.backups`. Review
these contents before sharing. Packaging does not validate print quality or detect
stale exports. Rebuild the kit, transfers and sheet after changing the source, then
make a new delivery bundle. The [user manual](docs/USER-MANUAL.md#8-bundle-everything)
explains each step and what to do if a required output is missing.

## Troubleshooting

| Symptom | Cause and next action |
| --- | --- |
| `Source is missing or unsupported` | Check the exact filename, extension and whether it is inside `local-assets/input` or directly in `local-assets`. |
| Continuation prompt after pasting a command | A quote or heredoc is unfinished. Press Ctrl+C and paste the complete block again. |
| Literal backslashes in a filename | Inside quotes, use `_` and `.`, not `\_` or `\.`. An unquoted wildcard is `ReelRoots*.png`, not `ReelRoots\*.png`. |
| Wildcard matches more than one image | Use a single exact quoted filename; the command accepts one source image. |
| `open` says the output does not exist | Use the destination printed after `DONE:`. A longer source filename produces a different folder name. Also verify the export actually succeeded. |
| `no DTF output found` for `full-front` | Check the preceding DTF output for `NOT WRITTEN`. Supply a higher-resolution source, use the explicit proof override, or remove that placement from the gang job. |
| `DONE` followed by a resolution refusal | Some transfers may exist while others were refused. Read the final counts before proceeding. |
| `output already exists` | Add `--overwrite` to back up and replace the existing output. |
| Solid background remains | PNG conversion alone does not remove it. Use the background removal option and inspect the mockups. |
| Thin strokes, poor contrast or size warnings | Review the artwork and dimensions before ordering; successful export is not print approval. |
| PDF support is missing | Install `python -m pip install -e ".[print]"`, or append `--no-pdf` to the gang command for PNG output. |

## What this is

NorthMark (formerly Create Logos All Sizes) turns source artwork into correctly proportioned PNGs, lossless WebP, color variants,
browser and app icons, a web drop-in folder, previews and a ZIP you can hand to someone
else. Then take the same master to print: 300 DPI direct-to-film (DTF) transfer files at
exact placement sizes, garment mockups, an order sheet, a press card, and gang sheets
packed onto 22 inch rolls with a cut list. Runs locally. No account, upload service or
AI is required.

| Problem it removes | How |
| --- | --- |
| Hand-exporting the same logo at fifteen sizes for every new brand | One command writes every size, variant and icon |
| Round logos coming out as ovals or clipped | Fit, never crop or stretch; optional trim to the art first |
| A cream or white halo around a logo that was "transparent" | Soft-edge matting with color decontamination |
| A white box behind a logo that should be transparent | Explicit or measured background removal |
| No real dark-background version of a logo | Named color-map variants, such as `reverse` |
| Guessing the size to type into a printer's custom-size box | Exact inches to two decimals, per placement |
| Ordering a transfer that prints blurry | An honest source-DPI verdict before any resampling |
| A rerun quietly overwriting the last good set of files | Atomic publish with dated backups and a process lock |

![Grid of logo color versions on white, dark and checkerboard backgrounds, with circular profile crops, browser tab mocks and 16, 32 and 48 pixel samples](docs/images/demo-preview.png)

*The kit preview for the generated demo mark. Each color version sits on white, dark and
transparent backgrounds, then in circular profile crops and light and dark browser tabs.
The empty white-on-white and black-on-dark cells are the point: they show which version
not to use where.*

## First-time setup

Requires Python 3.10 or newer. For a guided setup including PDF support, see the
[user manual](docs/USER-MANUAL.md#first-time-setup). On macOS, run this once from your project folder
(change the `cd` path if needed):

```sh
cd "$HOME/Pictures/NorthMark"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p local-assets/input
```

On Windows, use `python` instead of `python3` and activate with
`.venv\Scripts\activate`. You can create `local-assets/input` in Explorer.

Put your original images in `local-assets/input`, then run one image by its exact path:

```sh
python make_logo_sizes.py "local-assets/input/Your Logo.png"
```

Replace `Your Logo.png` with your filename. Each image gets its own folder and ZIP
under `local-assets/exports`. See [Quick start](#quick-start) for previews and the next commands.

To try the tool without your own artwork:

```sh
python examples/make_demo.py
python make_logo_sizes.py local-assets/input/demo-mark.png --variants all
```

The example is a generic geometric mark generated locally; no brand artwork ships with
this repository. The installed command `logo-sizes` and `python -m northmark` do the
same thing as the wrapper script. Every v3 invocation still works unchanged; `kit` is
its explicit name now that `dtf` and `gang` exist.

## DTF quick start

```sh
python make_logo_sizes.py dtf local-assets/input/mark.png --placement full-back
python make_logo_sizes.py dtf --brand local-assets/brands/my-brand.yaml --order local-assets/orders/2026-10-18-tees.yaml
python make_logo_sizes.py dtf --list-placements
```

For each design, placement and variant the tool trims the art to its bounding box, fits
it inside the vendor's average placement box while keeping the aspect ratio, and reports
the exact width and height in inches. That pair of numbers is what you type into the
vendor's custom-size box. The PNG has exactly that many pixels at 300 DPI and carries a
300 DPI tag. It is never mirrored.

| Output | Where | What it is for |
| --- | --- | --- |
| `dtf/<audience>/<placement>/<variant>/<design>-<placement>-<W>x<H>in.png` | per design | The file to upload, 300 DPI, hardened alpha |
| `dtf/mockups/<placement>-<variant>-on-<garment>.png` | per design | Local garment-color previews; confirm the result with your printer |
| `dtf/order-sheet.csv` | per design | One row per transfer: inches, pixels, source DPI, warnings, file, qty |
| `dtf/press-card.pdf` or `.png` | per design | Sizes, positions, variant per garment color, vendor press settings |
| `dtf/dtf.json` | per design | Everything above as data, with checksums |

The resolution verdict is the honest part. Source pixels divided by print inches is the
real resolution, measured before any resampling. At or above 300 DPI is fine. Below 300
warns. Below 150 refuses the file unless you pass `--allow-low-dpi`, and the summary
then says the art was enlarged and gives the true source DPI. Setting a 300 DPI tag on
too few pixels fixes nothing, so the tool never pretends otherwise. Every verdict comes
with the pixel size that would reach 300.

Other checks on every transfer: alpha is thresholded to opaque or clear with at most a
one pixel soft edge (`--no-harden` keeps soft alpha, `--choke 1` trims fringe), strokes
thinner than about 0.5 mm are estimated and flagged as industry guidance, and each
variant's edge color is compared with each garment color so the summary can say, for
example, "navy shirt: use reverse". Placements, average sizes, ranges, positions,
garment swatches, press settings and bulk tiers all live in
[`northmark/data/ninja-placements.yaml`](northmark/data/ninja-placements.yaml) with
the date they were read. Where the vendor's pages disagree, both values are recorded and
the safer one is used. Confirm current specs before ordering.

## Gang sheets

```sh
python make_logo_sizes.py gang local-assets/orders/2026-10-18-gang.yaml
python make_logo_sizes.py gang local-assets/orders/2026-10-18-gang.yaml --dry-run
python make_logo_sizes.py gang job.csv --no-rotate --no-pdf
```

A job file lists designs or PNG files with sizes and quantities; see
[`examples/gang-job.example.yaml`](examples/gang-job.example.yaml) and the CSV template in
[`examples/templates/gang-job.csv`](examples/templates/gang-job.csv). Items that name a
design, placement and variant pick up the matching DTF output automatically.

| Output under `exports/gang-sheets/<job>/` | What it is |
| --- | --- |
| `sheet-22x<L>.png` | The sheet at 300 DPI, written in horizontal bands so long sheets stay in bounded memory |
| `sheet-22x<L>.pdf` | The same sheet as a PDF; each transfer image is embedded once and placed per copy (needs `[print]`) |
| `layout.json` | Every position in inches, sheet lengths, utilization, warnings, optional cost compare |
| `cut-list.csv` | One row per placed copy, with a matching template in `examples/templates/` |
| `preview.png` | Downscaled sheets with labeled boxes |

Packing is deterministic shelf packing on the configured width, with a 0.25 inch gap
(the lowest published industry minimum) and a 0.5 inch edge margin (a conservative
default; 0.25 is the published minimum) and 90 degree rotation allowed. The tool picks
the shortest configured standard length that fits, or splits across sheets, and prints
the utilization. Files over the configured 50 MB threshold get a warning; confirm the current upload limit with the printer. Enter the vendor's
current prices in the job file and the summary compares cost per transfer for gang
sheets against by-size orders with the bulk tiers.

As checked on 2026-11-15, Ninja's [gang-sheet upload page](https://ninjatransfers.com/products/premium-dtf-gang-sheets)
accepts PNG and PDF among other formats and recommends at least 300 DPI for raster
artwork. The generated sheet PNG and PDF contain raster artwork. Check the dimensions
shown by the uploader before ordering. You can also arrange individual transfer PNGs
with the [online builder](https://ninjatransfers.com/products/build-your-own-gang-sheet).
This replaces the older vector-only guidance recorded in the project.

## Keep your artwork private

```text
NorthMark/
  make_logo_sizes.py       command you run
  northmark/               public program code and vendor data files
  tests/                   tests generate their own temporary artwork
  examples/                generic example generator, example configs and CSV templates
  docs/                    manuals, plus docs/images/ with the only tracked images
  local-assets/            IGNORED BY GIT: keep all your own material here
    input/                 original artwork
    brands/<brand>.yaml    one configuration per brand
    orders/                order files and gang-sheet jobs
    exports/<brand>/       kits, dtf/ outputs and previews
    exports/gang-sheets/   packed sheets
    exports/.backups/      previous outputs kept by --overwrite
    private-terms.txt      names that must never appear in tracked YAML or CSV
    archive/               old files or other private material
```

The entire `local-assets/` folder is ignored, including brand files, orders and
exports. Common artwork and archive extensions are also ignored outside that folder.
Git ignore is not encryption or access control, and `git add -f` can bypass it. Never
force-add your artwork to a public repository.

Before publishing changes, run:

```sh
python tools/check_public_files.py
```

This checks tracked filenames, obvious credential patterns, and, when
`local-assets/private-terms.txt` exists, rejects any tracked YAML or CSV that mentions a
listed term without echoing the term. Review your staged changes too; it cannot
recognize every private detail inside an arbitrary text file. The Python package
includes only `northmark` and its data files, never `local-assets`.

## Color versions

```sh
python make_logo_sizes.py --variants all
python make_logo_sizes.py --variants original white black
```

| Version | Result |
| --- | --- |
| `original` | Original colors and existing transparency |
| `white` | White artwork with the source alpha channel |
| `black` | Black artwork with the source alpha channel |
| `grayscale` | Neutral shades with the source alpha channel |
| `inverted` | Every RGB color negated; transparency stays the same |
| any map name | A named recolor from the brand file, such as `reverse` or `one-color` |

White and black versions need transparent source artwork; the tool refuses an opaque
source for those so it never produces a solid rectangle. A map variant is the real
answer for a reverse version: it recolors chosen colors and clears others, with a
tolerance and an optional feather per entry, and leaves everything else alone. A logo
whose enclosed background color stays opaque after edge-mode background removal becomes
a usable dark-shirt version by mapping its outline to white and that enclosed color to
transparent.

## Background removal

```sh
python make_logo_sizes.py logo.png --remove-background "#ffffff" --variants all
python make_logo_sizes.py logo.png --remove-background auto
python make_logo_sizes.py logo.png --remove-background "#faf6ee" --tolerance 4 --feather 200
```

| Option | Effect |
| --- | --- |
| `--remove-background COLOR` | Make that flat color transparent; `edge` mode keeps enclosed areas |
| `--remove-background auto` | Measure the border color and its noise, print the values used, then remove it |
| `--tolerance N` | Pixels within N of the color in any channel are fully removed |
| `--feather N` | Alpha ramps over the next N levels and the background color is subtracted from edge pixels |
| `--background-mode all` | Remove every matching pixel, including enclosed details |
| `--trim` | Crop to the artwork bounding box before fitting, so a framed master does not come out small |

A hard cut leaves a one or two pixel ring of blended background color around
anti-aliased art, which shows as a light halo on a dark surface. Feathering fixes it: set
the feather close to the contrast between the art and its background, which is what
`auto` does. Background removal only runs when asked, and the tool never guesses
silently.

## Config reference

A brand file is the template-plus-config way to run the tool: the program is the
template and each brand gets one YAML file. Copy
[`examples/brand.example.yaml`](examples/brand.example.yaml) to
`local-assets/brands/<brand>.yaml`, then:

```sh
python make_logo_sizes.py kit --brand local-assets/brands/my-brand.yaml
python make_logo_sizes.py dtf --brand local-assets/brands/my-brand.yaml
```

| Key | Purpose |
| --- | --- |
| `brand`, `slug` | Display name and output folder name |
| `sources.primary`, `symbol`, `horizontal` | The full logo; a mark for 64 px and under and small DTF placements; banner art |
| `colors` | Named colors used by maps, backgrounds and garments |
| `background` | `color` (a color or `auto`), `mode`, `tolerance`, `feather` |
| `trim` | `enabled` and `threshold` |
| `padding`, `formats`, `variants` | As on the command line; variants may include map names |
| `maps` | Named lists of `{from, to, tolerance, feather}`; `to: transparent` clears |
| `sizes` | `groups`, `presets` and `custom` sizes; omit the block for the standard set |
| `icon_background`, `banner_background` | Opaque fills for maskable icons and for banner sizes |
| `web` | `name`, `short_name`, `theme_color`, `background_color` for the web drop-in files |
| `dtf` | `audience`, `placements`, `variants`, `garments`, `symbol_for`, `overrides` |
| `uvdtf` | Sticker sizes in inches, same 300 DPI rules, no garment mockups |

Paths are relative to the brand file. Every key is validated before any artwork is read,
and unknown keys are errors. With `--brand`, the size, variant and color flags are
refused so there is one source of truth. The [command reference](docs/COMMAND-REFERENCE.md) lists every key with its
defaults.

## One master does it all: when it does and when it doesn't

| Situation | Verdict |
| --- | --- |
| A clean transparent PNG of at least 2048 px for digital use | Yes. One master covers every kit size |
| A vector SVG master | Usually. Supported SVGs render for the target size and produce a vector PDF; render limits can still cause a DPI warning |
| A flat-background PNG with anti-aliased edges | Yes, with `--remove-background auto` or a brand `background` block |
| A dark-shirt version of a logo with an enclosed light fill | Yes, with a `reverse` map; the tool cannot invent one from alpha alone |
| A chest-size version of a logo with a tagline or fine detail | Usually not. The thin-stroke check will say so; supply a `symbol` master |
| A full-back transfer from a raster master under about 3300 px on its long side | No. The DPI verdict fails and names the pixel size you need |
| Navy art on a navy shirt | No file can fix that; the contrast check recommends another variant |

The tool reports every one of these plainly in the run summary and in `kit.json`,
`dtf.json` and the order sheet, so you never have to open an image to find out.

## Horizontal, stacked and symbol artwork

Provide a separate source design for each layout. The tool sizes them; it does not
rearrange lettering, invent a symbol or trace raster artwork into vector paths. A brand
file's `symbol` source is used for sizes of 64 px and under and for the DTF placements
listed in `symbol_for`; its `horizontal` source is used for canvases at least twice as
wide as they are tall. Without a brand file, use custom canvases:

```sh
python make_logo_sizes.py brand-horizontal.png --size header=1200x300
python make_logo_sizes.py brand-symbol.png --group web --variants all
python make_logo_sizes.py --padding 0.12 --no-upscale --formats png webp
```

Custom sizes replace the standard list unless you also select a `--group` or
`--preset`, in which case they are added. `--no-upscale` keeps raster artwork at or
below its source pixel dimensions inside the requested canvas; raster enlargement
otherwise produces a note.

## SVG originals

Install optional SVG support:

```sh
python -m pip install -e ".[svg]"
```

CairoSVG also needs the Cairo system library. On macOS, install it with
`brew install cairo`; on Debian/Ubuntu use `sudo apt-get install libcairo2`. For Windows
setup, see the [CairoSVG installation instructions](https://cairosvg.org/documentation/).
Raster inputs work without CairoSVG or Cairo.

Provide a plain, self-contained SVG with a `viewBox` or numeric pixel width and height.
Path-based artwork is preferable to text that depends on installed fonts. External
resources, embedded images, scripts, entities, imports and `url()` references are
refused; a `<style>` block with plain fill, stroke and font rules is accepted. The
original SVG is copied unchanged to `masters/source.svg` and to `web/favicon.svg`, and a
vector `print/<slug>.pdf` is written. The tool does not create a vector master from a
PNG or JPEG.

## What is in a kit

| Part | Contents |
| --- | --- |
| `<variant>/` | Every selected size as PNG, and WebP if requested |
| `<variant>/app-icons/` | Six-size `favicon.ico`, 192 and 512 regular and maskable icons, Apple touch icon, manifest icon fragment |
| `web/` | Drop-in files for a site root: icons, complete `site.webmanifest`, `head.html`, `favicon.svg` and the Open Graph image when made |
| `print/<slug>.pdf` | Vector PDF, SVG sources only |
| `preview.png`, `preview.html` | White, dark and checkerboard backgrounds, profile circles, tab mocks, 16, 32 and 48 px samples |
| `preview-banners.png` | Each banner size with its safe area outlined |
| `masters/` | The untouched primary (`source.*`), symbol and horizontal originals |
| `GUIDE.txt` | Which files to use and the important limitations |
| `kit.json` | Options, sources with checksums, and every file's size, checksum, variant, preset, purpose and source role |
| `<slug>.zip` | The complete kit, as a sibling file |

Every run ends with a readable summary: each file and its size in KB, a total, every
warning (including per-preset size caps) and every note. Skip parts with `--no-icons`,
`--no-preview` or `--no-zip`.

## Export sizes

Use `--list` for the complete list with sources. The original fifteen sizes are the
standard set and are written by a run with no size flags; the rectangular sizes are
optional and selected explicitly. All of them come from
[`northmark/data/platform-presets.yaml`](northmark/data/platform-presets.yaml) with a
source and the date it was read.

| Group | Sizes in pixels | Default |
| --- | --- | --- |
| `youtube` | Watermark 150, profile 800 | Yes |
| `web` | 16, 32, 180, 192, 512 | Yes |
| `social` | LinkedIn 400, X 400, Facebook 500, Instagram 320 | Yes |
| `docs` | Document 600, email 200, slide 1000 | Yes |
| `master` | 2048 raster derivative | Yes |
| `banners` | YouTube banner 2560x1440 with a 1546x423 safe area and 6 MB cap, X header 1500x500, LinkedIn cover 1128x191 and 4200x700 (conflicting specs, both provided) | No |
| `share` | Open Graph image 1200x630 | No |

```sh
python make_logo_sizes.py --group banners --banner-background "#0f2340"
python make_logo_sizes.py --preset og-image-1200
```

Banner sizes keep the artwork inside the platform's safe area and take an optional
opaque `--banner-background`. These are convenient starting sizes, not current platform
acceptance guarantees.

## Safe reruns and other folders

```sh
python make_logo_sizes.py --dry-run
python make_logo_sizes.py --overwrite
python make_logo_sizes.py -i /path/to/originals -o /path/to/exports
```

`--overwrite` backs up the previous output before publishing the new one, for kits, DTF
folders and gang sheets alike. A kit rebuild keeps the design's existing `dtf/` folder.
Errors before publication leave the previous result intact. DTF resolution refusals
can still publish the placements that passed; check the final counts as described in
[Developer notes](#developer-notes). Duplicate
output names are caught before any batch writes. Kit and DTF dry runs check paths, names and
options without decoding artwork. Gang dry runs resolve existing transfer PNGs and
may read their dimensions while planning the sheet. A failed source produces a nonzero exit status; other
valid sources still finish.

An output lock prevents two processes from publishing into the same folder at once. The
lock records its process id and host. If that process has exited on the same machine,
the next run reclaims the stale lock itself and says so; the reclaim is a rename, so two
runs that find the same stale lock cannot both proceed. A lock from a live process or
another machine is respected.

## Development and installation

```sh
python -m pip install -e ".[svg,print]"
python -m unittest discover -s tests -v
python tools/check_public_files.py
```

Tests create temporary generic images and exercise real exports, pixels, transparency,
matting, color maps, brand files, DTF sizing and verdicts, gang-sheet packing, backups,
locks, icons, ZIPs and SVG refusal rules. CI runs the suite on Ubuntu, macOS and Windows
for Python 3.10, 3.12 and 3.14, with SVG checks skipped where Cairo is unavailable, then
runs the public-file check. Dependabot keeps the SHA-pinned actions current. Pushing a
`v*` tag builds the wheel and sdist, refuses any private file in the build, and
publishes a GitHub release.

To regenerate the README image after changing the preview:

```sh
python examples/make_demo.py
python make_logo_sizes.py local-assets/input/demo-mark.png --variants all --overwrite
cp local-assets/exports/demo-mark/preview.png docs/images/demo-preview.png
```

## Developer notes

These notes describe the current implementation and the failure cases encountered
in the walkthrough. The [developer manual](docs/DEVELOPER-MANUAL.md) covers the full architecture.

| Area | Behavior and maintenance note |
| --- | --- |
| Output names | `northmark/presets.py:slugify` normalizes the source filename stem. `ReelRoots.png` becomes `reelroots`; the longer filename becomes `reelroots-cinematic-family-memories`. Brand files can supply their own slug. |
| Shell quoting | The shell expands an unquoted `*` before Python sees the path. Backslashes inside double quotes before `_` or `.` remain literal filename characters. Document exact quoted paths and reserve globs for single matches. |
| DTF completion | `northmark/cli.py:run_dtf` publishes the generated folder before reporting each placement. A refused placement has no transfer PNG; the command returns exit status 1 when any placement is refused, even if `DONE` appeared. |
| DTF replacement | DTF publication replaces the entire design's `dtf/` directory. Include all placements that should remain. A kit rebuild preserves an existing `dtf/` directory on disk. |
| Resolution | Source DPI is evaluated before resampling. `--allow-low-dpi` permits export without repairing missing detail. Gang-sheet rendering cannot recover that detail. |
| Gang dependencies | `northmark/gang.py:_resolve_item` resolves design, audience, placement and variant to an existing transfer PNG. The default audience is `adult`; a refused placement makes the gang job fail. |
| Preflight | Kit and DTF `--dry-run` do not decode or validate artwork. Gang `--dry-run` resolves existing transfers and plans packing, so it can fail on a missing PNG. |
| ZIP scope | `northmark/kit.py:generate_kit` creates the kit ZIP before `publish_kit` carries over existing DTF files. Later DTF and gang runs do not refresh that ZIP. Use the delivery bundle command for all outputs. |
| Rebuild order | After changing a source, rebuild its kit and all required DTF placements, then the gang sheet, then the delivery folder and ZIP. Outputs are snapshots, not live references. |
| Vendor data | Placement sizes, ranges and recommendations come from dated YAML in `northmark/data`. Review inconsistent average sizes and ranges rather than silently treating a warning as approval. |

Useful development commands, run from the project root with `.venv` active:

```sh
python -m pip install -e ".[svg,print]"
python -m unittest discover -s tests -v
python tools/check_public_files.py
git diff --check
```

These commands are separate from exporting artwork. Keep source artwork, order files,
exports and delivery archives under the ignored `local-assets` directory.

## Manuals

| Document | For |
| --- | --- |
| [User manual](docs/USER-MANUAL.md) | Plain-language Ghostty guide: exact commands from artwork to delivery ZIP |
| [Command reference](docs/COMMAND-REFERENCE.md) | All command options, brand files, orders and output formats |
| [Developer manual](docs/DEVELOPER-MANUAL.md) | Module map, data files, publishing and locking, tests, releases, security notes |

## License

[MIT](LICENSE) for the software. No personal or client artwork is included. The
software license grants no rights to any source artwork you process.

## Stack

| Layer | Tools |
| --- | --- |
| Runtime | Python 3.10 or newer |
| Image processing | Pillow |
| Configuration | PyYAML, safe loader only |
| Optional SVG rendering and vector PDF | CairoSVG and Cairo (`[svg]`) |
| Optional press card and gang-sheet PDF | reportlab (`[print]`) |
| Checks | Python unittest, GitHub Actions on three operating systems, the public-file check |

<!-- TNDS-FOOTER:BEGIN -->
## Contact

Jacob Johnston | True North Data Strategies LLC, SDVOSB | Colorado Springs, Colorado

jacob@truenorthstrategyops.com | [truenorthstrategyops.com](https://truenorthstrategyops.com) | [pipelinepunks.com](https://pipelinepunks.com)

_Maintained by the TNDS README steward. Last reviewed 2026-11-15._
<!-- TNDS-FOOTER:END -->
