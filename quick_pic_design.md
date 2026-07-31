# 素写速食（quick_pic）设计

## Goal

Add a small built-in tool for turning a phone photo of a simple drawing into a clean PNG.

The normal flow is:

1. The phone uploads a photo to Dropbox.
2. The tool lists the five most recently modified supported images from the configured private input directory.
3. The user selects an image and sees the original preview.
4. The tool removes the paper background, crops empty space, and shows a processed preview.
5. The user selects the configured output root or any directory beneath it and saves the PNG.

ImageMagick is the image-processing engine. Python owns configuration, file discovery, validation, HTTP handling, and safe process execution.

## Scope

The first version is optimized for dark line drawings photographed on white or light paper.

It supports:

* JPEG and PNG input
* Automatic EXIF orientation
* Adjustable background threshold
* Transparent or solid-white output background
* Automatic cropping with a small transparent/white margin
* PNG output
* A configured output root plus all of its subdirectories

The first version does not include:

* Manual crop handles
* Perspective correction
* General-purpose photo editing
* AI object segmentation
* Reliable preservation of pale or complex colors
* Deleting or modifying the source image

HEIC may be enabled later after confirming that the installed ImageMagick build can decode it.

## User Interface

The tool has one dedicated page rather than using the generic command-tool form.

Controls:

1. **Source image**: dropdown containing the five newest images, newest first
2. **Original preview**: updates when the source changes
3. **Background**: `Transparent` or `White`
4. **Cleanup strength**: a threshold slider with a sensible configured default
5. **Output directory**: dropdown populated only from configuration
6. **Processed preview**
7. **Save PNG** button

The filename and modified time should appear beside each source option because phone filenames are often not descriptive. The newest image is selected automatically.

Changing the source, background mode, or cleanup strength refreshes the processed preview. Preview requests should be debounced so moving the slider does not start many ImageMagick processes.

After saving, the page shows:

* Saved filename
* Configured output label
* A link to open the generated PNG

## Configuration

Configuration lives at:

```text
~/.config/home_command_center/apps/quick_pic.yaml
```

Proposed format:

```yaml
type: command_tool

quick_pic:
  input_dir: "/path/to/private/camera-uploads"
  recent_count: 5

  output_root: "/path/to/private/image-library"
  output_root_label: Images
  default_background: transparent
  default_threshold: 82
  crop_padding: 24

  extensions:
    - .jpg
    - .jpeg
    - .png
```

Validation rules:

* `input_dir` must be an existing readable directory.
* `recent_count` must be between 1 and 20.
* `output_root` must be an existing writable directory.
* `output_root_label` must be a non-empty display label.
* `default_background` must be `transparent` or `white`.
* `default_threshold` must be between 1 and 99.
* `crop_padding` must be between 0 and 500 pixels.
* Extensions are normalized to lowercase and must begin with a dot.

The dashboard registry already ignores YAML files whose `type` is `command_tool`, so this settings file will not appear as a separate external-app card.

Both real machine-specific directory paths exist only in this private config and must not be committed to the repository.

## Candidate Discovery

The server scans only the directory configured by `input_dir` and does not scan its subdirectories. It:

1. Keeps regular files with configured extensions.
2. Sorts by modification time descending.
3. Returns the latest five entries (`recent_count: 5`).

Each response contains an opaque candidate ID, filename, modification time, dimensions when available, and preview URL. Raw filesystem paths are never sent to the browser.

When a candidate is used, the server rebuilds the current candidate list and accepts only an ID in that list. It also resolves the file again and verifies that it remains directly inside `input_dir`. This prevents a client from requesting arbitrary server files.

Dropbox may still be writing the newest file. A candidate should be ignored when its size or modification time changes during a short stability check, or ImageMagick cannot identify it as an image.

## Image Processing

ImageMagick must be invoked directly with an argument array. No shell is used, and no part of the request is interpolated into a command string.

Conceptual transparent-background pipeline:

```text
magick <source>
  -auto-orient
  -colorspace Gray
  -contrast-stretch 1%x1%
  -threshold <value>%
  -transparent white
  -trim
  +repage
  -bordercolor none
  -border <padding>
  png:-
```

For white output, the same cleanup is used but the final image is flattened onto white and saved without transparency.

The exact ImageMagick arguments should be verified against representative phone photos. In particular:

* A higher threshold keeps more light marks but may retain shadows.
* A lower threshold removes more background but may erase pencil marks.
* `-trim` must run before adding the final margin.
* A completely blank result should return a clear error instead of a 1x1 PNG.

Preview output is written to ImageMagick stdout and returned as `image/png`; it does not need a permanent preview file. Save performs the same pipeline again with the submitted settings.

Both preview and save have a short process timeout and an output-size limit.

## Output Naming and Writes

The output dropdown contains `output_root` itself followed by every directory beneath it, including nested directories. The root uses `output_root_label`; descendants use their paths relative to the root. Entries are sorted naturally by relative path.

The server returns an opaque ID for each directory. It never returns an absolute filesystem path. The client submits only this output directory ID.

Before writing, the server rebuilds the directory list, resolves the selected directory and `output_root`, and verifies that the selected directory is the root or a descendant of it. Symlinks that resolve outside the root are rejected.

Suggested filename:

```text
<source-stem>_cleaned_<YYYYMMDD-HHMMSS>.png
```

Unsafe filename characters are replaced. The server writes to a temporary file in the selected output directory, verifies that ImageMagick succeeded, then atomically renames it to the final filename. Existing files are never overwritten; a numeric suffix is added on collision.

The source image is always read-only.

Generated-file links use a dedicated `quick_pic` result route. The route accepts only a current output directory ID and a filename, resolves the path, and verifies containment under `output_root` before serving it.

## Server Integration

Register the tool with the following identity:

```text
id: quick_pic
name: 素写速食
name_en: quick_pic
```

Give it a dedicated renderer and endpoints:

```text
GET  /tools/quick_pic
GET  /api/tools/quick_pic/candidates
GET  /api/tools/quick_pic/source/<candidate-id>
POST /api/tools/quick_pic/preview
POST /api/tools/quick_pic/save
GET  /api/tools/quick_pic/results/<output-dir-id>/<filename>
```

`preview` and `save` accept only:

```json
{
  "candidate_id": "...",
  "background": "transparent",
  "threshold": 82,
  "output_dir_id": "..."
}
```

`output_dir_id` is required only for saving.

Recommended repo additions:

```text
cli_tools/quick_pic.py
static/quick_pic.js
static/quick_pic.css
tests/test_quick_pic.py
```

`cli_tools/quick_pic.py` contains config loading, candidate discovery, page rendering, request validation, ImageMagick invocation, and output-path validation. Route dispatch remains in `server.py`.

## Error Handling

The page should distinguish these cases:

* Configuration missing or invalid
* Input directory unavailable
* No recent images found
* Source image disappeared during processing
* Unsupported or corrupt image
* ImageMagick missing
* ImageMagick timeout or processing failure
* Output directory unavailable or not writable
* Blank result after cleanup

ImageMagick stderr may be logged server-side, but the browser should receive a short user-facing message without filesystem paths.

## Tests

Automated tests should cover:

* Configuration defaults and validation
* Candidate filtering, ordering, and limit
* Candidate rejection after it leaves the recent list
* Input and output path containment, including symlinks
* Output directory ID validation
* Recursive output-directory discovery, including the root itself
* Filename sanitization and collision handling
* ImageMagick command construction without a shell
* Transparent and white PNG generation using small fixtures
* Blank-image failure
* Timeout and non-zero ImageMagick exit handling
* Result-route access limited to the configured output root

## Acceptance Criteria

The feature is complete when:

1. The dashboard opens a dedicated 素写速食 page.
2. The page shows up to the configured number of newest Dropbox images.
3. A user can preview cleanup without modifying the source.
4. Transparent and white background modes both work.
5. Cropping removes empty margins and adds the configured padding.
6. The PNG can be saved only into the configured output root or one of its subdirectories.
7. The browser never supplies or receives raw filesystem paths.
8. No shell is used to run ImageMagick.
9. Invalid configuration and processing failures produce useful errors.
