# NorthMark: Developer Manual

How NorthMark's code is organized, what each module guarantees, how outputs are published
safely, how to test and release, and the security rules a public image tool has to
keep. Read the user manual first for what the commands do.

## Contents

1. [Module map](#module-map)
2. [Data files](#data-files)
3. [Image pipeline](#image-pipeline)
4. [Publishing and locking](#publishing-and-locking)
5. [Tests](#tests)
6. [Adding things](#adding-things)
7. [Releases and CI](#releases-and-ci)
8. [Security notes](#security-notes)
9. [Conventions](#conventions)

## Module map

| Module | Responsibility |
| --- | --- |
| `logo_sizes/cli.py` | Argument parsing for `kit`, `dtf` and `gang` (installed as `northmark` and `logo-sizes`); source planning; the output lock; all printing. Nothing else prints |
| `logo_sizes/config.py` | Brand YAML loading with `yaml.safe_load`, key-by-key validation, color resolution, preset selection |
| `logo_sizes/presets.py` | `Preset` dataclass and the preset list loaded from `data/platform-presets.yaml`; `parse_size`, `slugify` |
| `logo_sizes/imaging.py` | Loading with limits, the SVG sanitizer, matting (`remove_background`, `detect_background`), `color_map`, `trim_to_art`, `make_variant`, `fit_canvas`, `svg_to_pdf` |
| `logo_sizes/kit.py` | Kit generation into a work folder, icons, web drop-in, previews, `kit.json`, the ZIP, and `publish()` |
| `logo_sizes/dtf.py` | Placement data access, inch and pixel geometry, DPI verdicts, alpha hardening, thin-stroke estimate, garment contrast, mockups, order sheet, press card, `build_dtf()` |
| `logo_sizes/gang.py` | Job file loading, deterministic shelf packing, banded PNG writer, PDF sheets, layout and cut list, preview, cost compare, `build_gang()` |
| `logo_sizes/report.py` | The file table printed at the end of every run |
| `logo_sizes/files.py` | Streamed SHA-256 for output manifests |
| `tools/check_public_files.py` | The publishing guard run by CI and before every push |
| `examples/` | The demo-art generator, example brand, order and job files, and CSV templates |

Dependencies: Pillow and PyYAML are required. CairoSVG (`[svg]`) and reportlab
(`[print]`) are optional and imported lazily inside the functions that need them, so the
rest of the tool works without them and gives a clear message when they are missing.
NumPy was considered and not needed: Pillow's point tables, `ImageChops`, `ImageMath`
and rank filters cover matting, decontamination and the morphological checks.

## Data files

Every platform or vendor number lives in a YAML file under `logo_sizes/data/` with a
`source` and `checked` date, never in code. The files ship inside the wheel through
`[tool.setuptools.package-data]` and are read with `importlib.resources`.

| File | Consumers |
| --- | --- |
| `platform-presets.yaml` | `presets.py` at import time; `standard: false` entries are opt-in |
| `ninja-placements.yaml` | `dtf.py` and `gang.py`; `--placements-file` substitutes another copy at run time |

Rules: record conflicting vendor statements side by side and use the safer one; label
industry guidance as not from the vendor; leave unknown numbers out rather than guess.

## Image pipeline

1. `load_image` decodes with a decompression-bomb guard and the 32 MP kit limit,
   applies EXIF orientation, converts to RGBA and clears metadata. SVG goes through the
   sanitizer and CairoSVG at the largest size the run needs.
2. `matte` (in `cli.py`) applies `remove_background` when asked. With `auto`,
   `detect_background` measures the border's median color and 99th-percentile noise,
   sets the tolerance just above the noise and the feather near the 20th-percentile
   contrast between art and background, and records the values used.
3. `remove_background` computes the per-pixel distance to the color, turns it into a
   background amount with a linear ramp (`_ramp`), limits it to border-connected
   regions in `edge` mode (a flood fill through every partly-background pixel, so pure
   art pixels act as barriers and a one-pixel outline protects what it encloses), subtracts the background's contribution from partially kept pixels
   (`_decontaminate`, via `ImageMath`), and multiplies the alpha.
4. `trim_to_art` crops to the alpha bounding box above a threshold.
5. `make_variant` produces the standard variants or applies a named `color_map`.
6. Kits call `render_preset` per size (safe area and banner background aware) and
   `fit_canvas`, which never crops or stretches. DTF calls `fit_inches`, `pixels_for`,
   `effective_dpi`, then `harden_alpha` and `thin_strokes` on the rendered transfer.

`fit_canvas` relies on Pillow premultiplying alpha during RGBA resizes, so transparent
pixel colors do not bleed into edges.

## Publishing and locking

Every command builds into a temporary folder inside the output directory
(`tempfile.TemporaryDirectory(prefix=".logo-build-")`) and then calls `kit.publish()`,
which moves each built item to its destination with `rename`. Existing destinations
are moved to `.backups/<label>-<UTC stamp>-<id>/` first, including outputs that have no
replacement this run (a kit's old ZIP when `--no-zip` is used). If any move fails, the
moves already made are reversed and the backups restored, so the previous complete
output always survives. Symbolic links at any destination are refused.

`cli.output_lock` creates `.logo-kit.lock` exclusively and writes the process id, host
and start time. On `FileExistsError` it calls `reclaim_stale_lock`: if the host matches
and the process no longer exists (`process_alive`, which never signals or terminates),
the stale file is renamed to a unique name first, which is atomic, so only one of two
racing runs can reclaim it; the winner deletes the renamed file and retries creation
once. On exit the lock is removed only if it still carries this process id. On Windows
the liveness check uses `OpenProcess` with `PROCESS_QUERY_LIMITED_INFORMATION` and
`GetExitCodeProcess`, because `os.kill(pid, 0)` terminates on that platform and an
exited process stays openable while a handle to it is held.

## Tests

`python -m unittest discover -s tests -v` runs everything; CI runs the same command.
Tests use generated geometric art only, never brand files, and most go through the
command line in a subprocess against temporary folders.

| Test module | Covers |
| --- | --- |
| `tests/test_cli.py` | Kits end to end: fitting, variants, backgrounds, backups, locks, brand files, trim, banners, web files, SVG rules, previews |
| `tests/test_imaging.py` | Matting halos on a dark composite, feathered edge and all modes, detection, color maps, trim |
| `tests/test_config.py` | Brand file validation and color resolution |
| `tests/test_kit.py` | Size caps and per-file metadata |
| `tests/test_presets.py` | The presets data file and the standard set |
| `tests/test_dtf.py` | Placement data, inch geometry, DPI verdicts, hardening, thin strokes, garment contrast, the `dtf` command |
| `tests/test_gang.py` | Packing invariants (no overlaps, gap, margin, determinism, length choice, splitting, rotation), job files, cost compare, the `gang` command |
| `tests/test_public_files.py` | The publishing guard in disposable repositories, including private terms |

Write the test first and watch it fail for the right reason before implementing. The
SVG tests skip when CairoSVG or the Cairo library cannot be imported.

## Adding things

| Task | Where |
| --- | --- |
| A new export size | Add an entry to `data/platform-presets.yaml` with `source` and `checked`; set `standard: false` unless it must join the default run; add it to the README table |
| A new placement or audience | Add it under `audiences` in `data/ninja-placements.yaml` with `average`, `range` where published, `position`, and a `note` for conflicts |
| A new garment color | Add it under `garments` with a `color` and a note that the swatch is approximate |
| A new brand-file key | Add it to `TOP_LEVEL_KEYS` or the section key sets in `config.py`, validate it, carry it on `BrandConfig`, document it in the user manual and the example file |
| A new CSV | Add a matching empty template under `examples/templates/` and a header test |

## Releases and CI

`tests.yml` runs the suite and the public-file check on Ubuntu, macOS and Windows for
Python 3.10, 3.12 and 3.14. Actions are pinned by commit SHA with the version in a
comment; Dependabot proposes updates weekly for actions and pip ranges.

To release: bump `version` in `pyproject.toml` and `__version__` in
`logo_sizes/__init__.py`, commit, tag `vX.Y.Z` and push the tag. `release.yml` builds
the wheel and sdist, refuses any artwork or `local-assets` path inside them, uploads
them as a workflow artifact and creates the GitHub release with generated notes.

## Security notes

| Area | Rule |
| --- | --- |
| YAML | `yaml.safe_load` only; documents must be mappings; unknown keys are errors; names that become folders must be one safe lowercase component |
| SVG | defusedxml parsing with DTDs, entities and external references forbidden; an element allow list; no `on*` attributes, external `href`, `url()`, escapes, imports or comments in attributes or style blocks; 5 MB cap; CairoSVG with `unsafe=False` |
| Rasters | Decompression-bomb warnings are errors; a 32 MP kit limit and a 60 MP per-transfer limit |
| Paths | Outputs that are symbolic links are refused; a source inside its own output folder is refused; slugs come from `slugify` with Windows reserved names avoided |
| Metadata | Source EXIF and comments are not carried into outputs |
| Logging | Paths are printed relative to the output root in file tables; file contents and private terms are never echoed |
| Network | None at run time |
| Publishing | `tools/check_public_files.py` rejects tracked artwork, private folders, credential patterns and private terms in configuration files |

## Conventions

- Plain functions and small dataclasses; no global state beyond the preset list.
- Every vendor or platform number is data with a source and date.
- Every warning is a sentence that says what to do next.
- Never delete user output; move it to `.backups/`.
- Never mirror, never upscale silently, never set a DPI tag the pixels do not support.
