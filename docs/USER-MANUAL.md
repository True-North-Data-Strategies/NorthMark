# NorthMark user manual: copy and paste in Ghostty

Reviewed 2026-11-15 for NorthMark 4.0.0 on macOS.

This guide takes you from one image to a folder and ZIP containing your digital logo
kit, shirt transfers and a sheet of transfers ready for review. You do not need to
write code. Copy one command box at a time into Ghostty, press Return and wait for
the prompt to come back before moving on.

The commands use Jacob's existing project at `/Users/jj-personal/Pictures/NorthMark`
and the image `local-assets/input/ReelRoots.png`. That is the current short filename.
If you are using a different computer or design, see [Use another image](#use-another-image).
The artwork itself is private and does not come with the repository.

## Find your place

| What you want to do | Go here |
| --- | --- |
| Start a new Ghostty session | [1. Open the project](#1-open-the-project) |
| Set up a fresh installation | [First-time setup](#first-time-setup) |
| Make website and social-media logo files | [2. Make the digital kit](#2-make-the-digital-kit) |
| Make a small shirt transfer | [3. Make the left-chest transfer](#3-make-the-left-chest-transfer) |
| Add a large front-of-shirt transfer | [4. Add the full-front transfer](#4-add-the-full-front-transfer) |
| Handle a low-resolution warning | [5. If the full-front transfer is refused](#5-if-the-full-front-transfer-is-refused) |
| Put several transfers on one sheet | [6. Set the quantities](#6-set-the-quantities) |
| Generate the sheet | [7. Build the gang sheet](#7-build-the-gang-sheet) |
| Put everything in one folder and ZIP | [8. Bundle everything](#8-bundle-everything) |
| Know which files to send | [9. Choose the files to share](#9-choose-the-files-to-share) |
| Run the job again another day | [Rerun or change an order](#rerun-or-change-an-order) |
| Fix an error | [Troubleshooting](#troubleshooting) |
| Look up advanced options | [Command reference](COMMAND-REFERENCE.md) |

## Before you paste

Copy only the text inside a command box. Do not copy the terminal prompt, `❯`, the
word `bash`, or the three backticks around a code box. If Ghostty asks whether to
paste multiple lines, review the box and allow the paste.

Keep quotation marks exactly as shown. Do not insert backslashes before spaces,
underscores, periods or asterisks. If you see a waiting prompt such as `dquote>` or
`heredoc>` and nothing happens, press **Control+C**, then paste the whole box again.
The job-file box in step 6 must include its final `YAML` line.

A **kit** is your logo in different digital sizes. A **DTF transfer** is a print file
for a design that will be pressed onto clothing. A **gang sheet** arranges several
transfers on one large sheet. A **mockup** is a picture showing roughly how the design
looks on a shirt color. **DPI** describes how much image detail is available at the
chosen print size; more pixels are needed for a bigger print.

## 1. Open the project

Open Ghostty and paste:

```bash
cd "/Users/jj-personal/Pictures/NorthMark"
source .venv/bin/activate
```

You should see `(.venv)` in your prompt if your prompt displays it. This turns on the
Python setup for this project. Repeat these two commands whenever you open a new
Ghostty tab or window. If activation fails, use [First-time setup](#first-time-setup).

Check that the image is where the following commands expect it:

```bash
ls -l "local-assets/input/ReelRoots.png"
```

If you see the filename and file information, continue. If you see `No such file or
directory`, open the input folder and check the spelling:

```bash
open "local-assets/input"
```

### First-time setup

Skip this if the project already works. From the existing project folder, this creates
the Python setup and installs the tools, including PDF support. It needs Python 3.10
or newer and internet access for installation. If `python3` is missing, install Python
before continuing. There is no need to repeat this for every image.

```bash
cd "/Users/jj-personal/Pictures/NorthMark"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[print]"
mkdir -p local-assets/input local-assets/orders local-assets/dist
```

Copy your PNG into `local-assets/input` using Finder. Keep your original somewhere
safe. Naming this working copy `ReelRoots.png` makes the commands below match exactly.
Renaming a JPG to `.png` does not convert it; keep the real extension for other formats.

## 2. Make the digital kit

This creates the logo sizes, website icons, previews and a digital-kit ZIP. It keeps
the colors and background as they are. The `--overwrite` part makes this command safe
to repeat: an older kit is moved into a dated backup before the new one replaces it.

```bash
python make_logo_sizes.py "local-assets/input/ReelRoots.png" --overwrite
```

When it finishes successfully, open the preview:

```bash
open "local-assets/exports/reelroots/preview.html"
```

Your browser opens a page showing the generated versions. Your folder and ZIP are in:

```bash
open "local-assets/exports"
```

If you only need website or social-media files, the digital kit is enough. You can
share `reelroots.zip` and stop here. Continue for shirt transfers and a gang sheet.

### Optional: remove the background from the digital kit

Use this instead if you want the kit's background removed. It estimates the background
color from the image edges. Check the preview afterward to make sure logo details
were not removed with it.

```bash
python make_logo_sizes.py "local-assets/input/ReelRoots.png" --remove-background auto --overwrite
open "local-assets/exports/reelroots/preview.html"
```

### Optional: add white, black and other color versions

This replaces the kit with all standard color versions. White and black versions
need transparent artwork, so this command includes background removal.

```bash
python make_logo_sizes.py "local-assets/input/ReelRoots.png" --remove-background auto --variants all --overwrite
open "local-assets/exports/reelroots/preview.html"
```

These options change the digital kit only. The shirt-transfer commands below choose
their own colors and background handling.

## 3. Make the left-chest transfer

This makes a small shirt transfer with the background removed. If your source is
already transparent, automatic removal leaves an already clear border alone.

```bash
python make_logo_sizes.py dtf "local-assets/input/ReelRoots.png" --placement left-chest --remove-background auto --overwrite
```

To keep the original background instead, leave out `--remove-background auto`.
Open the pictures showing the result on different shirt colors:

```bash
open "local-assets/exports/reelroots/dtf/mockups"
```

Check the edges, text and small details. The pictures show approximate colors and
placement, not a finished printed shirt. Read any warnings in Ghostty.

The current placement setting fits the design inside 3.5 x 2 inches. Because the
image keeps its proportions, the actual size may be smaller. The source placement
guide also lists a height range starting at 2.5 inches, so a size warning can appear
with the default setting. Use the actual dimensions in the order sheet and confirm
the size you want; the warning does not mean the program stretched the artwork.

## 4. Add the full-front transfer

This makes both the small chest transfer and the large front transfer together:

```bash
python make_logo_sizes.py dtf "local-assets/input/ReelRoots.png" --placement left-chest --placement full-front --remove-background auto --overwrite
```

Include every placement you want to keep. Each DTF rebuild replaces the whole `dtf`
folder and backs up the old folder. It does not add one new placement to the old set.

Read the final line. For this command, you want **2 transfer files written and 0
refused**. If a transfer says `NOT WRITTEN`, go to step 5 before building the sheet.
The word `DONE` alone does not mean every requested file was created.

Open the order sheet and mockups:

```bash
open "local-assets/exports/reelroots/dtf/order-sheet.csv"
open "local-assets/exports/reelroots/dtf/mockups"
open "local-assets/exports/reelroots/dtf/adult"
```

The order sheet opens in your default spreadsheet app. Look for `width_in`,
`height_in`, `source_dpi`, `warnings` and `file`. A blank `file` means that transfer
was refused. In the `adult` folder, each placement has an `original` folder containing
its transfer PNG. Use those PNGs for printing, not the small mockup pictures.

A warning about low contrast means the logo may be hard to see on that shirt color.
If `original` is the only version, it may still be listed as the recommendation;
that does not make poor contrast acceptable.

## 5. If the full-front transfer is refused

Skip this section if both transfers were written. The ReelRoots run we reviewed had
107 source DPI at 11.00 x 9.97 inches. NorthMark refuses files below 150 source DPI
unless you explicitly allow them. For 300 DPI at that size, you need at least
3300 x 2991 pixels of actual artwork after the background is trimmed.

For printing, get a larger original or a genuine vector original. Making the same
small PNG bigger does not bring back missing detail. After replacing the working
source with a better image, repeat steps 2 through 4.

If you only want to finish a **layout proof with the current image**, paste this:

```bash
python make_logo_sizes.py dtf "local-assets/input/ReelRoots.png" --placement left-chest --placement full-front --remove-background auto --allow-low-dpi --overwrite
```

This permits the low-resolution file. It does not improve it. The transfer, gang
sheet and delivery ZIP will still contain the enlarged low-detail artwork. Keep that
limitation with the proof when sharing it, and replace the source before treating it
as a final print file.

## 6. Set the quantities

A short job file tells NorthMark which transfers to arrange on the sheet. This example
uses one left-chest and one full-front transfer. Change each `qty: 1` to the number
you want before pasting, or use it as written for one of each.

Paste the entire box. The spaces at the start of the lines matter. This writes over
an existing `reelroots-gang.yaml` job file, so keep a copy first if it has custom settings.

```bash
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

This uses a 22-inch-wide sheet and lets the program choose from lengths of 2, 5 or
10 feet. There is a quarter-inch gap between transfers and half an inch around the
outside. Confirm those dimensions with your printer. The quantities here control the
gang sheet; they do not update the separate DTF `order-sheet.csv`.

If you only made a left-chest transfer, remove the entire four-line `full-front`
entry before pasting. Every transfer listed in the job file must already exist.

## 7. Build the gang sheet

```bash
python make_logo_sizes.py gang "local-assets/orders/reelroots-gang.yaml" --overwrite
```

When it succeeds, open the results:

```bash
open "local-assets/exports/gang-sheets/reelroots-gang/preview.png"
open "local-assets/exports/gang-sheets/reelroots-gang"
```

Check that the preview contains the right designs and number of copies. The sheet
may split into more than one file if the copies do not fit on the chosen lengths.

| File | What it is for |
| --- | --- |
| `preview.png` | A small picture for checking the arrangement. Do not upload it as the print file. |
| `sheet-22x...png` | The full-size sheet for printing; its name includes the sheet dimensions. |
| `sheet-22x...pdf` | The same layout as a PDF when PDF support is installed. It still contains raster artwork. |
| `cut-list.csv` | A spreadsheet listing each copy, size and position. |
| `layout.json` | Layout details for software. You do not need to edit this. |

If you see `no DTF output found`, a listed transfer is missing. Go back to the DTF
summary and handle its refusal; running the gang command repeatedly will not create
that missing transfer. If PDF support is missing, repeat the install command from
first-time setup, or add `--no-pdf` to the gang command to make PNG output only.

## 8. Bundle everything

Use this after the kit, transfers and gang sheet are complete. The automatic
`reelroots.zip` is only the digital kit. It does not collect later print exports.

The box below creates a new delivery folder, copies the current outputs into it,
creates a matching ZIP and checks that the ZIP can be read. It stops if a required
file or copy is missing. Copy the whole box, including both parentheses.

```bash
(
  set -e
  test -f "local-assets/exports/reelroots/kit.json"
  test -f "local-assets/exports/reelroots/dtf/dtf.json"
  test -f "local-assets/exports/gang-sheets/reelroots-gang/layout.json"
  test -f "local-assets/orders/reelroots-gang.yaml"
  mkdir -p "local-assets/dist"
  bundle_dir=$(mktemp -d "local-assets/dist/reelroots-delivery-XXXXXX")
  ditto "local-assets/exports/reelroots" "$bundle_dir/reelroots"
  ditto "local-assets/exports/gang-sheets/reelroots-gang" "$bundle_dir/gang-sheet"
  cp "local-assets/orders/reelroots-gang.yaml" "$bundle_dir/reelroots-gang.yaml"
  ditto -c -k --sequesterRsrc --keepParent "$bundle_dir" "${bundle_dir}.zip"
  unzip -tq "${bundle_dir}.zip"
  open "local-assets/dist"
)
```

Finder opens `local-assets/dist`. The new delivery folder and its ZIP have the same
name with a short unique ending. The check should report no errors in the ZIP.

The folder contains the digital kit, its original source master, the current DTF
files and mockups, the gang sheet and the job file. It does not include unrelated
brands or old backups. Review the contents before sharing. Packaging does not check
print quality or make an old gang sheet current; review the outputs first.

If nothing opens and the command stops, complete the missing earlier step. If your
digital kit is still in the old `reelroots-cinematic-family-memories` folder, run
step 2 with `ReelRoots.png` so the kit and transfers use the same folder.

## 9. Choose the files to share

| Recipient or purpose | Files to use |
| --- | --- |
| Someone who needs all the project outputs | The new delivery ZIP from `local-assets/dist`. It includes source artwork. |
| Someone who only needs digital logo files | The kit ZIP in `local-assets/exports`, or the specific files inside the kit. |
| A printer making individual transfers | The PNG inside each placement's `original` folder, with the exact dimensions from `order-sheet.csv`. |
| A printer making a gang sheet | The full-size `sheet-...png` or PDF, in the format the printer accepts. |
| Someone reviewing the layout | The mockups and gang-sheet preview, clearly described as previews. |

As checked on 2026-11-15, Ninja's upload page lists PNG and PDF among accepted
formats and recommends at least 300 DPI for raster artwork. Check the current
[gang-sheet upload requirements](https://ninjatransfers.com/products/premium-dtf-gang-sheets)
and confirm the dimensions shown after upload. The [online builder](https://ninjatransfers.com/products/build-your-own-gang-sheet)
is another option for arranging individual transfer images.

Before ordering, confirm the artwork, dimensions, quantities, background, shirt-color
contrast and resolution. Use the printer's current pressing instructions. Creating
these files does not place an order or send anything to a printer.

## Rerun or change an order

Open the project and activate it again as shown in step 1. Then use the relevant step:

| What changed | What to run again |
| --- | --- |
| Source image or background | Digital kit, all required DTF placements, gang sheet, delivery bundle. |
| Print placements or print artwork | All required DTF placements, gang sheet, delivery bundle. |
| Number of copies | Edit the job file, rebuild the gang sheet, make a new delivery bundle. |
| Only the delivery package is missing | Run step 8 after checking the existing outputs. |

`--overwrite` keeps previous generated outputs under `local-assets/exports/.backups`.
The job-file creation box overwrites that YAML file directly; it does not make a backup.
Each delivery bundle gets its own new folder. Existing delivery ZIPs never update
automatically when you rebuild the images.

When you are done, you may close Ghostty or turn off the project's Python setup:

```bash
deactivate
```

## Use another image

For another job, put the image in `local-assets/input` and use its exact filename.
Replace `ReelRoots.png` in the commands and replace `reelroots` in output paths and
both `design` entries in the gang job. Give the gang job and delivery folder their
own names too. Never rename a new brand to `ReelRoots.png` just to reuse the commands,
because that would replace the ReelRoots outputs when `--overwrite` is used.

| Source filename | Output folder name |
| --- | --- |
| `ReelRoots.png` | `reelroots` |
| `ReelRoots_ Cinematic Family Memories.png` | `reelroots-cinematic-family-memories` |
| `My Logo.png` | `my-logo` |

For a filename with spaces, keep the full path inside quotes:

```bash
python make_logo_sizes.py "local-assets/input/ReelRoots_ Cinematic Family Memories.png" --overwrite
```

If the source is directly in `local-assets`, omit `input/` from its path. The output
path after `DONE:` is the one to open. An unquoted `ReelRoots*.png` shortcut only works
when exactly one matching image exists, so this guide uses exact filenames instead.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `source: no such file or directory: .venv/bin/activate` | Run the first-time setup from the project folder. |
| `python: command not found` | Activate the project as in step 1; use first-time setup if `.venv` is missing. |
| `can't open file ... make_logo_sizes.py` | Run the `cd` command from step 1. You are in the wrong folder. |
| `Source is missing or unsupported` | Check the exact name, extension and folder. Do not put a backslash before `_` inside quotes. |
| `dquote>` or `heredoc>` waiting prompt | Press Control+C and paste the whole command box, including the closing quote or final `YAML`. |
| `open` says the folder does not exist | Check whether the export succeeded and use its printed destination. `reelroots` and the longer filename produce different folders. |
| `Output already exists` | Add `--overwrite` to back up the old generated output and rebuild it. |
| `NOT WRITTEN` | That transfer was not made. Follow step 5 before building a sheet that needs it. |
| `no DTF output found` | Generate the missing placement, fix its resolution, or remove its entry from the gang job. |
| A background or halo remains | Review the automatic cutout. It may need different background settings or a cleaner original; see the command reference. |
| White or black versions are refused | Those versions need transparency. Remove the background first or use the original colors. |
| Low contrast despite a recommendation to use `original` | The program can only choose among versions you generated. Review the mockup and use suitable artwork or a different shirt color. |
| Very thin details are flagged | Simplify the design or make it larger if the source has enough detail. Ask the printer whether those details will hold. |
| Bundle box stops without opening Finder | Check that steps 2, 4 and 7 completed and the job file exists. The bundle checks intentionally stop before copying an incomplete set. |
| `Another export holds .logo-kit.lock` | Let the other export finish. Do not delete a lock while an export is still running. |

For detailed sizes, background settings, SVG originals, brand files and other options,
use the [command reference](COMMAND-REFERENCE.md). For maintaining NorthMark itself,
use the [developer manual](DEVELOPER-MANUAL.md).
