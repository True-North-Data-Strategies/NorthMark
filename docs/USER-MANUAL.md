# Create Logos All Sizes: User Manual

This manual covers every command, flag, file format and output of version 4. The
README is the short tour; this is the reference. All examples use the wrapper
`python make_logo_sizes.py`; the installed `logo-sizes` command and
`python -m logo_sizes` accept exactly the same arguments.

## Contents

1. [Install](#install)
2. [Folders and privacy](#folders-and-privacy)
3. [The kit command](#the-kit-command)
4. [Brand configuration files](#brand-configuration-files)
5. [The dtf command](#the-dtf-command)
6. [Order files](#order-files)
7. [The gang command](#the-gang-command)
8. [Gang job files](#gang-job-files)
9. [Reading the run summary](#reading-the-run-summary)
10. [Vendor and platform data files](#vendor-and-platform-data-files)
11. [Troubleshooting](#troubleshooting)

## Install

| Step | Command |
| --- | --- |
| Create and activate a virtual environment | `python3 -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`) |
| Install the tool | `python -m pip install -r requirements.txt` or `python -m pip install -e .` |
| Add SVG support | `python -m pip install -e ".[svg]"` plus the Cairo library (`brew install cairo` or `sudo apt-get install libcairo2`) |
| Add PDF output (press card, gang-sheet PDF) | `python -m pip install -e ".[print]"` |
| Everything | `python -m pip install -e ".[svg,print]"` |

Python 3.10 or newer is required. Pillow and PyYAML are the only required
dependencies.

## Folders and privacy

Everything of yours lives under `local-assets/`, which git ignores:

| Folder or file | Holds |
| --- | --- |
| `local-assets/input/` | Original artwork. A run with no source argument processes every supported image here |
| `local-assets/brands/<brand>.yaml` | One configuration per brand |
| `local-assets/orders/` | Order files for quantities and gang-sheet job files |
| `local-assets/exports/<slug>/` | The kit for one design, plus its `dtf/` folder |
| `local-assets/exports/gang-sheets/<job>/` | Packed sheets |
| `local-assets/exports/.backups/` | Previous outputs kept by `--overwrite` |
| `local-assets/private-terms.txt` | One term per line; tracked YAML and CSV must not mention them |
| `local-assets/archive/` | Anything old you want to keep |

Supported source types: PNG, JPG, JPEG, WebP, BMP, TIF, TIFF, GIF (first frame) and
SVG (with the `[svg]` extra). Sources are never modified. Run
`python tools/check_public_files.py` before pushing to confirm nothing private is
tracked.

## The kit command

```sh
python make_logo_sizes.py [kit] [SOURCE] [options]
python make_logo_sizes.py kit --brand local-assets/brands/my-brand.yaml [options]
```

Without `SOURCE`, every image in the input folder is processed; each gets its own
output folder named from its file name. With `--brand`, the brand file supplies the
sources, sizes, variants and colors, and the output folder is the brand's slug.

| Flag | Meaning | Default |
| --- | --- | --- |
| `-i`, `--input-dir PATH` | Folder to scan when no source is given | `local-assets/input` |
| `-o`, `--output-dir PATH` | Where kits are published | `local-assets/exports` |
| `--brand FILE` | Brand configuration; refuses the size, variant and color flags below | none |
| `--group NAME` | Only presets in that group (`youtube`, `web`, `social`, `docs`, `master`, `banners`, `share`) | standard set |
| `--preset NAME` | One preset by name; see `--list` | standard set |
| `--size NAME=WxH` | Custom canvas; repeat for more. Replaces the standard set unless a group or preset is also chosen | none |
| `--variants ...` | `original`, `white`, `black`, `grayscale`, `inverted`, or `all` | `original` |
| `--formats ...` | `png` and/or `webp` (lossless) | `png` |
| `--padding F` | Fraction of each canvas side left clear, 0 to below 0.5 | `0.08` |
| `--no-upscale` | Never enlarge raster art beyond its source pixels | enlarge, with a note |
| `--remove-background COLOR` | A color such as `#ffffff`, or `auto` to measure the border | off |
| `--background-mode edge|all` | `edge` removes only regions touching the border | `edge` |
| `--tolerance N` | Full removal within N levels of the color | `0` |
| `--feather N` | Soft ramp over the next N levels, with color decontamination | `0` (hard cut) |
| `--trim` | Crop to the artwork before fitting | off |
| `--trim-threshold N` | Alpha level that counts as artwork when trimming | `8` |
| `--icon-background COLOR` | Opaque fill behind maskable and touch icons | dark for `white`, white otherwise |
| `--banner-background COLOR` | Opaque fill for banner and share sizes | transparent |
| `--no-icons`, `--no-preview`, `--no-zip` | Skip those parts | all on |
| `--overwrite` | Replace an existing kit after backing it up | refuse |
| `--dry-run` | Print the plan without reading artwork | off |
| `--list` | Show every preset with its group, standard or optional, and purpose | |

### What a kit contains

| Path | Contents |
| --- | --- |
| `<variant>/<preset>.png` | One file per size and variant; `.webp` too when requested |
| `<variant>/app-icons/` | `favicon.ico` (16 to 256), `icon-192.png`, `icon-512.png`, maskable versions, `apple-touch-icon.png`, `manifest.webmanifest` icon fragment |
| `web/` | `favicon.ico`, icons, `apple-touch-icon.png`, complete `site.webmanifest`, `head.html`, `favicon.svg` for SVG sources, `og-image-1200.png` when that preset was made. Written when icons are on and `original` is among the variants |
| `print/<slug>.pdf` | Vector PDF, SVG sources only |
| `preview.png`, `preview.html` | Variants on white, dark and checkerboard, circular profile crops, light and dark tab mocks, 16, 32 and 48 px samples |
| `preview-banners.png` | Each banner preset downscaled with its safe area outlined |
| `masters/source.*` | The untouched primary; `masters/symbol.*` and `masters/horizontal.*` when supplied |
| `GUIDE.txt` | Which file to use where |
| `kit.json` | Options, sources with SHA-256, and for every file: path, bytes, SHA-256, width, height, variant, preset, purpose, source role, safe area |
| `<slug>.zip` | The whole kit, next to the folder |

### Size caps

Presets may carry a `max_kb` cap. A file over its cap is still written; the summary
and `kit.json` carry a warning. The YouTube banner carries a 6 MB cap from its source.

## Brand configuration files

Copy `examples/brand.example.yaml` to `local-assets/brands/<brand>.yaml`. Paths are
relative to the brand file. Unknown keys are errors, and every value is checked before
any artwork is read.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `brand` | text | required | Display name |
| `slug` | text | slug of `brand` | Output folder name; lowercase letters, digits, hyphens |
| `sources.primary` | path | required | The full logo |
| `sources.symbol` | path | none | Used for sizes of 64 px and under and for `dtf.symbol_for` placements |
| `sources.horizontal` | path | none | Used for canvases at least twice as wide as tall |
| `colors.<name>` | color | none | Named colors for maps, backgrounds and web settings |
| `background.color` | color or `auto` | none | Omit the block to keep the source alpha |
| `background.mode` | `edge` or `all` | `edge` | |
| `background.tolerance` | 0 to 255 | `0` | With `auto`, 0 means use the measured value |
| `background.feather` | 0 to 255 | `0` | With `auto`, 0 means use the measured value |
| `trim` | `true`, or `{enabled, threshold}` | off | Threshold 0 to 255, default 8 |
| `padding` | 0 to below 0.5 | `0.08` | |
| `variants` | list | `[original]` | Standard names or map names |
| `maps.<name>` | list of entries | none | Each entry: `from` (color), `to` (color or `transparent`), `tolerance`, `feather` |
| `sizes.groups` | list | | Standard groups plus `banners` and `share` |
| `sizes.presets` | list | | Individual preset names |
| `sizes.custom` | list | | `name=WIDTHxHEIGHT` strings |
| `formats` | list | `[png]` | `png`, `webp` |
| `icon_background` | color | by variant | Opaque |
| `banner_background` | color | transparent | Opaque |
| `web.name`, `web.short_name`, `web.theme_color`, `web.background_color` | text | slug | Fill `site.webmanifest` and `head.html` |
| `dtf.audience` | `adult`, `youth`, `womens` | `adult` | |
| `dtf.placements` | list | `left-chest, full-front, full-back` | Names from the placements file |
| `dtf.variants` | list | brand `variants` | |
| `dtf.garments` | list | all in the data file | Names from the placements file |
| `dtf.symbol_for` | list | none | Placements that use the symbol source |
| `dtf.overrides.<placement>` | `{width_in, height_in}` | vendor average | The box the art is fitted into |
| `uvdtf.sizes` | list of `{name, width_in, height_in}` | none | Sticker sizes |
| `uvdtf.variants` | list | brand `variants` | |

When no `sizes` block is present the standard fifteen presets are used.

### How map variants work

Each entry measures every pixel's distance from its `from` color (the largest
difference in any RGB channel). Within `tolerance` the pixel is fully affected; over the
next `feather` levels the effect fades to nothing. `to: transparent` multiplies the
alpha down; a color blends toward it. All entries match against the source colors, so
order does not matter and one entry never sees another's result.

## The dtf command

```sh
python make_logo_sizes.py dtf SOURCE --placement NAME [--placement NAME ...] [options]
python make_logo_sizes.py dtf --brand FILE [--order FILE] [options]
python make_logo_sizes.py dtf --list-placements
```

| Flag | Meaning | Default |
| --- | --- | --- |
| `--brand FILE` | Brand file with sources, maps and a `dtf` section | none |
| `--placement NAME` | Placement to produce; repeat for more. Overrides the brand list | brand list or `left-chest`, `full-front`, `full-back` |
| `--audience NAME` | `adult`, `youth` or `womens`. Overrides the brand setting | brand or `adult` |
| `--variants ...` | Standard variants or map names | brand `dtf.variants`, else `original` |
| `--garments ...` | Garment colors from the placements file | brand list, else all |
| `--placements-file FILE` | Use another vendor data file | packaged file |
| `--order FILE` | Order file whose quantities fill the `qty` column | none |
| `--allow-low-dpi` | Write files that fail the 150 DPI floor; the true DPI is still reported | refuse them |
| `--no-harden` | Keep soft alpha | threshold it |
| `--choke N` | Erode the hardened alpha by N pixels, 0 to 10 | `0` |
| `--remove-background`, `--background-mode`, `--tolerance`, `--feather` | As for kits; single-source runs only | off |
| `-o`, `--overwrite`, `--dry-run` | As for kits | |

The output lands in `<output>/<design>/dtf/` and is published as one unit: an
existing `dtf/` folder needs `--overwrite`, which backs it up first. The art is always
trimmed to its bounding box per variant, so the stated size is the visible art.

### The resolution verdict

| Source DPI at the printed size | Verdict | What happens |
| --- | --- | --- |
| 300 or more | OK | File written |
| 150 to 299 | WARN | File written; warning names the pixels needed for 300 |
| Below 150 | FAIL | No file unless `--allow-low-dpi`; the order-sheet row stays with the warning |

A vector SVG source renders at the needed size, so it always passes. A raster that is
enlarged gets a note with its true source DPI. The DPI tag in the PNG is always 300; the
pixel count is what matters, and the verdict is about pixels.

### Order sheet columns

`design, placement, audience, variant, garment_colors, width_in, height_in, width_px,
height_px, source_dpi, warnings, file, qty`. The `garment_colors` column lists the
garments for which this variant is the recommended one. An empty template is in
`examples/templates/order-sheet.csv`.

### Press card

One page per design listing each placement with its exact size, the vendor's position
guidance, the recommended variant per garment color and the vendor's press settings with
the date they were read. PDF with the `[print]` extra, otherwise PNG.

## Order files

```yaml
order: 2026-10-18-tees
items:
  - {design: my-brand, placement: full-back, variant: original, qty: 2}
  - {design: my-brand, placement: left-chest, variant: reverse, audience: youth, qty: 4}
```

`design` is the brand slug or source file stem. `variant` defaults to `original`;
`audience` defaults to the run's audience. Quantities for the same key add up. See
`examples/order.example.yaml`.

## The gang command

```sh
python make_logo_sizes.py gang JOB [--no-rotate] [--no-pdf] [--placements-file FILE] [-o DIR] [--overwrite] [--dry-run]
```

The output lands in `<output>/gang-sheets/<job>/`. Items that name a design and
placement are looked up under `<output>/<design>/dtf/<audience>/<placement>/<variant>/`,
so run `dtf` first. `--dry-run` packs and prints every position without writing.

| Output | Contents |
| --- | --- |
| `sheet-<W>x<L>.png` (`-1`, `-2` suffixes when split) | 300 DPI sheet with a 300 DPI tag, transparent background |
| `sheet-<W>x<L>.pdf` | Same layout; each image embedded once; needs `[print]` |
| `layout.json` | Sheets with lengths, used length, utilization and every item position in inches; warnings; cost compare when prices are given |
| `cut-list.csv` | `sheet, item, design, file, copy, width_in, height_in, x_in, y_in, rotated` |
| `preview.png` | Sheets side by side with labeled boxes |

Packing is first-fit shelf packing. Pieces are sorted largest first, three rotation
policies are tried and the shortest result is kept, so the same job always gives the
same layout. The shortest configured length that holds the layout is chosen; when even
the longest will not, the layout is split across sheets.

## Gang job files

YAML:

```yaml
job: 2026-10-18-gang
sheet: {width_in: 22, lengths_ft: [2, 5, 10, 15, 20], gap_in: 0.25, margin_in: 0.25, rotate: true}
items:
  - {design: my-brand, placement: full-back, variant: original, qty: 2}
  - {file: ../input/sticker.png, width_in: 4, height_in: 6, qty: 1}
prices:
  currency: USD
  gang_sheet_by_length_ft: {2: 0.00, 5: 0.00}
  by_size: {full-back: 0.00}
```

CSV with the header `design,placement,variant,file,width_in,height_in,qty` (template in
`examples/templates/gang-job.csv`). Sheet settings and lengths default to the vendor data
file. `lengths_in` may replace `lengths_ft`. An item with `file` and no size takes its
size from the PNG's pixels and DPI tag. Prices are optional and never built in; when
present, the summary compares cost per transfer for gang sheets against by-size orders
using the vendor's bulk tiers.

## Reading the run summary

Every run prints, per design: `DONE` with the output path, each file with its size in
KB and a total, every `WARNING`, and every `NOTE`. DTF runs add one line per transfer
with the exact inches, pixels, source DPI and verdict, then the recommended variant per
garment. Gang runs add one line per sheet with its length and utilization. The final
`Finished:` line gives counts, and the exit status is nonzero when anything failed or
was refused, so scripts can check it.

## Vendor and platform data files

| File | Holds |
| --- | --- |
| `logo_sizes/data/ninja-placements.yaml` | Placement ranges, averages and positions for adult, youth and women's; garment swatches; press settings; bulk tiers; gang-sheet width, lengths, gap and margin; file limits; industry guidance; the dates read |
| `logo_sizes/data/platform-presets.yaml` | Every export size with group, purpose, safe area, cap, and source |

Where two vendor statements conflict, both are recorded and the safer one is used. Pass
`--placements-file` to use an updated copy without changing the package.

## Troubleshooting

| Message | Cause and fix |
| --- | --- |
| `Output already exists` | Add `--overwrite` to back up and replace, or choose another `-o` folder |
| `Another export holds .logo-kit.lock` | A run is active, or a lock from another machine or a live process remains. Stale locks from exited processes on this host clear themselves |
| `The white variant needs a transparent source` | Use `--remove-background` or a brand `background` block first |
| `Background removal removed all artwork` | The color or tolerance matches the art; lower the tolerance or pick the right color |
| `NOT WRITTEN: ... DPI is below 150` | The master has too few pixels for that size; the message names the pixels needed. Supply a larger or vector master, or pass `--allow-low-dpi` knowingly |
| `Low contrast against the navy garment` | Use the recommended variant for that garment color |
| `About x% of the art is thinner than 0.5 mm` | Fine detail may not print at this size; use a `symbol` master or a version without the tagline |
| `Unsupported SVG element` or `SVG external resources` | Export a plain SVG with inline attributes; style blocks may only hold plain rules |
| `Tracked configuration mentions a private term` | A tracked YAML or CSV contains a term from `local-assets/private-terms.txt`; move the data to `local-assets/` |
| `PDF sheets skipped` | Install the print extra: `pip install ".[print]"` |
