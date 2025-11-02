"""
token_renderer.py
==================

This script implements a small renderer for paper‑doll style tokens based on
SVG templates.  It consumes a YAML configuration describing one or more
tokens, their associated placeholder substitutions and page layout
information, and produces a PDF with the resulting tokens arranged on
pages.

The renderer makes heavy use of Inkscape via its command line interface
to extract geometrical information (such as bounding boxes) and to
rasterise the SVG templates at an arbitrary resolution.  Pillow is
used for image manipulation (resizing and compositing), and reportlab
produces the final PDF output.

The configuration schema is specified with Pydantic models.  See
`PageOfTokensConfig` at the bottom of this file for the entry point.

Usage::

    python token_renderer.py --config config.yaml --output out.pdf

The YAML file must adhere to the schema described in the models below.
"""

from __future__ import annotations

import argparse
import enum
import subprocess
import tempfile
from dataclasses import dataclass
from math import floor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from PIL import Image
from pydantic import BaseModel, FilePath, validator
from pydantic.color import Color
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

###############################################################################
# Configuration models
###############################################################################

class PageSize(str, enum.Enum):
    letter = "letter"
    double_letter = "double_letter"

    @property
    def size(self) -> Tuple[float, float]:
        """Return the page dimensions in points."""
        if self == PageSize.letter:
            return (8.5 * inch, 11 * inch)
        elif self == PageSize.letter:
            return (11 * inch, 17 * inch)
        else:
            raise NotImplementedError()



class PageOrientation(str, enum.Enum):
    portrait = "portrait"
    landscape = "landscape"


class PlaceholderAlignment(str, enum.Enum):
    center = "center"


class PlaceholderResizeMethod(str, enum.Enum):
    disable = "disable"  # don't resize asset
    fill_height = "fill_height"  # scale asset to height of placeholder
    fill_width = "fill_width"  # scale asset to width of placeholder


class TentStyle(str, enum.Enum):
    """
    Tokens may be paper tents.  Three styles:

    - disable  - no tent; token is assumed to be complete.
    - mirror   - mirror the token across its top edge.
    - rotated  - rotate the token by π and place rotated at top edge.
    """

    disable = "disable"
    mirror = "mirror"
    rotated = "rotated"


class PageConfig(BaseModel):
    dpi: int
    pagesize: PageSize
    orientation: PageOrientation
    page_margin_inches: float
    max_pages: int

    @validator("dpi")
    def _dpi_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("DPI must be a positive integer")
        return v

    @property
    def page_dimensions(self) -> Tuple[float, float]:
        """Return the page width and height in points respecting orientation."""
        width, height = self.pagesize.size
        if self.orientation == PageOrientation.landscape:
            return height, width
        return width, height


class TokenPlaceholderConfig(BaseModel):
    """
    Specifies how to replace a token placeholder path.  The `placeholder_name`
    refers to the Inkscape label found in the SVG template.  Each
    placeholder is replaced by an external image according to the
    provided resizing and alignment rules.
    """

    placeholder_name: str  # something like "placeholder_image"
    replacement_image: FilePath
    placement: PlaceholderAlignment = PlaceholderAlignment.center
    resize_method: PlaceholderResizeMethod = PlaceholderResizeMethod.fill_height
    keep_aspect_ratio: bool = True

    # Offsets in inches applied to the final pasted asset.  Positive values
    # shift the image right (for horizontal) and down (for vertical).  Use
    # this to fine‑tune positioning beyond the bounding box centre.
    offset_x_inch: float = 0.0
    offset_y_inch: float = 0.0


class TokenConfig(BaseModel):
    """
    A token configuration describes how to instantiate a specific token
    from a given SVG template.  Multiple tokens can share a template
    but differ in their placeholder substitutions or tent style.
    """

    template_svg: FilePath
    background_color: Color  # fill in background in case of transparency
    tent_style: TentStyle = TentStyle.disable
    placeholders: List[TokenPlaceholderConfig]


class PageOfTokensConfig(BaseModel):
    page_config: PageConfig
    token_configs: Dict[str, TokenConfig]

    class Config:
        arbitrary_types_allowed = True


###############################################################################
# Utility functions
###############################################################################

def read_yaml_file(path: Path) -> Dict:
    """Load a YAML file and return its contents as a Python object."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def query_svg_object_bbox(svg_path: Path, object_id: str) -> Tuple[float, float, float, float]:
    """
    Query Inkscape for the bounding box (x, y, width, height) of a given
    object ID within an SVG file.  Inkscape returns coordinates in
    pixel units at 96 dpi.  This function wraps the necessary
    subprocess calls and collects the results.

    Parameters
    ----------
    svg_path : Path
        The path to the SVG template file.
    object_id : str
        The 'id' attribute of the SVG element whose bounding box is
        requested.

    Returns
    -------
    (x, y, width, height) : tuple of floats
        The bounding box of the object in pixels at 96 dpi.  The
        coordinate origin is the top‑left of the page.
    """
    # Inkscape's query options (-X, -Y, -W, -H) output numbers on stdout.
    # Each call returns a single value.
    def _query(flag: str) -> float:
        try:
            result = subprocess.run(
                [
                    "inkscape",
                    "--query-id",
                    object_id,
                    flag,
                    str(svg_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "Inkscape is required but could not be found on your system."
            ) from e
        # Inkscape may print warnings to stderr; we ignore them.  The last
        # non‑empty line on stdout should contain the numeric answer.
        stdout = result.stdout.strip()
        # It's possible that multiple lines are printed (warnings on stdout).
        # We'll parse all floats and take the last one.
        values = [float(x) for x in stdout.split() if _is_number(x)]
        if not values:
            raise RuntimeError(
                f"Failed to query {flag} for id {object_id} in {svg_path}. Output: {stdout!r}"
            )
        return values[-1]

    x = _query("-X")
    y = _query("-Y")
    w = _query("-W")
    h = _query("-H")
    return (x, y, w, h)


def _is_number(s: str) -> bool:
    """Return True if the string can be parsed as a float."""
    try:
        float(s)
        return True
    except ValueError:
        return False


def map_placeholders_to_ids(svg_path: Path) -> Dict[str, str]:
    """
    Parse an SVG file and build a mapping from Inkscape 'label'
    attributes to element 'id's.  This is used to look up the object
    ID corresponding to a placeholder name.

    Parameters
    ----------
    svg_path : Path
        The path to the SVG template.

    Returns
    -------
    Dict[str, str]
        A mapping from placeholder names (labels) to element IDs.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"inkscape": "http://www.inkscape.org/namespaces/inkscape"}
    mapping: Dict[str, str] = {}
    for elem in root.iter():
        label = elem.get(f"{{{ns['inkscape']}}}label")
        elem_id = elem.get("id")
        if label and elem_id:
            mapping[label] = elem_id
    return mapping


###############################################################################
# Token rendering logic
###############################################################################

@dataclass
class RenderedToken:
    """
    Container to hold a rendered token image along with its physical
    dimensions in points.  Reportlab draws images based on point units
    (1 point = 1/72 inch).
    """

    image: Image.Image
    width_pts: float
    height_pts: float


def render_single_token(token_cfg: TokenConfig, page_dpi: int) -> RenderedToken:
    """
    Render a single token according to its configuration.  This function
    rasterises the SVG template at the requested DPI, compositing
    placeholder images onto it and handling tent styles.  The resulting
    PIL image and its physical dimensions (in points) are returned.

    Parameters
    ----------
    token_cfg : TokenConfig
        Configuration for the token to be rendered.
    page_dpi : int
        The resolution in dots per inch at which to rasterise the SVG.

    Returns
    -------
    RenderedToken
        The rendered token image together with its width and height in
        points (1/72 inch).
    """
    # 1. Rasterise the template SVG at the desired DPI using Inkscape.
    #    Prior to rasterisation we remove the placeholder geometry so that the
    #    output does not include the placeholder shapes.  We build a
    #    temporary SVG on the fly with those elements removed.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_svg = Path(tmpdir) / "cleaned_template.svg"
        tmp_png = Path(tmpdir) / "template.png"
        # Build a cleaned copy of the SVG without placeholder geometry.
        def _write_clean_svg() -> None:
            import xml.etree.ElementTree as ET
            ns = {"inkscape": "http://www.inkscape.org/namespaces/inkscape"}
            tree = ET.parse(token_cfg.template_svg)
            root = tree.getroot()
            # Build a parent map to enable removing children.
            parent_map: Dict[ET.Element, ET.Element] = {c: p for p in tree.iter() for c in p}
            to_remove = []
            for elem in parent_map.keys():
                label = elem.get(f"{{{ns['inkscape']}}}label")
                if label and label.startswith("placeholder_"):
                    to_remove.append(elem)
            for elem in to_remove:
                parent = parent_map.get(elem)
                if parent is not None:
                    parent.remove(elem)
            tree.write(tmp_svg, encoding="utf-8", xml_declaration=True)

        _write_clean_svg()
        # Build inkscape command.  We set the export DPI explicitly; the
        # exported bitmap will have a transparent background (unless
        # filters produce artifacts).  The user can specify a
        # background colour separately which we overlay later.
        cmd = [
            "inkscape",
            str(tmp_svg),
            "--export-type=png",
            f"--export-filename={tmp_png}",
            "-d",
            str(page_dpi),
            "--export-area-page",  # use page boundaries
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Inkscape failed to export {token_cfg.template_svg}: {e.stderr}"
            )

        # Load the rasterised template.
        base_image = Image.open(tmp_png).convert("RGBA")

    # 2. Construct a mapping from placeholder labels to element IDs.
    label_to_id = map_placeholders_to_ids(Path(token_cfg.template_svg))

    # 3. Determine bounding boxes for each placeholder.  Inkscape returns
    # coordinates in pixels at 96 dpi; we rescale to the rasterised DPI.
    scale = page_dpi / 96.0
    bbox_cache: Dict[str, Tuple[float, float, float, float]] = {}
    for ph in token_cfg.placeholders:
        if ph.placeholder_name in bbox_cache:
            continue
        elem_id = label_to_id.get(ph.placeholder_name)
        if not elem_id:
            continue
        x, y, w, h = query_svg_object_bbox(Path(token_cfg.template_svg), elem_id)
        bbox_cache[ph.placeholder_name] = (x * scale, y * scale, w * scale, h * scale)

    # 4. Create a background layer filled with the requested background colour.
    bg = Image.new("RGBA", base_image.size, token_cfg.background_color.as_rgb())
    # Composite the template over the background (preserving transparency).
    composed = Image.alpha_composite(bg, base_image)

    # 5. Composite each placeholder image.
    for ph in token_cfg.placeholders:
        bbox = bbox_cache.get(ph.placeholder_name)
        if not bbox:
            # Placeholder missing from template; skip.
            continue
        box_x, box_y, box_w, box_h = bbox
        # Load the replacement asset.
        asset_img = Image.open(ph.replacement_image).convert("RGBA")
        # Determine new size based on resize method.
        asset_w, asset_h = asset_img.size
        new_w = asset_w
        new_h = asset_h
        if ph.resize_method == PlaceholderResizeMethod.fill_height:
            if ph.keep_aspect_ratio:
                # Scale to match height; preserve aspect ratio.
                if asset_h != 0:
                    scale_factor = box_h / float(asset_h)
                    new_w = asset_w * scale_factor
                    new_h = box_h
            else:
                # Only force the height; width stays unchanged.
                new_h = box_h
        elif ph.resize_method == PlaceholderResizeMethod.fill_width:
            if ph.keep_aspect_ratio:
                if asset_w != 0:
                    scale_factor = box_w / float(asset_w)
                    new_h = asset_h * scale_factor
                    new_w = box_w
            else:
                new_w = box_w
        elif ph.resize_method == PlaceholderResizeMethod.disable:
            # Do not scale at all.
            pass
        # Resize if needed.
        if (new_w, new_h) != (asset_w, asset_h):
            asset_img = asset_img.resize((int(round(new_w)), int(round(new_h))), Image.LANCZOS)
            asset_w, asset_h = asset_img.size
        # Compute position based on alignment.  Currently only center.
        if ph.placement == PlaceholderAlignment.center:
            paste_x = box_x + (box_w - asset_w) / 2.0
            paste_y = box_y + (box_h - asset_h) / 2.0
        else:
            # Future alignments could be implemented here; default to top-left.
            paste_x = box_x
            paste_y = box_y
        # Apply user-specified offsets (in inches).  Convert to pixels at
        # the current DPI.  Positive offsets move right and down in the
        # raster coordinate system (y increases downward).
        offset_px_x = ph.offset_x_inch * page_dpi
        offset_px_y = ph.offset_y_inch * page_dpi
        paste_x += offset_px_x
        paste_y += offset_px_y
        # Paste the asset onto the composite image.
        # PIL expects integer coordinates; convert accordingly.
        composed.paste(asset_img, (int(round(paste_x)), int(round(paste_y))), asset_img)

    # 6. Handle tent styles.  Mirror or rotate the token vertically.
    final_img = composed
    if token_cfg.tent_style == TentStyle.mirror:
        w, h = composed.size
        # Create an image twice the height.  Paste the original at bottom
        # and its vertically flipped copy at the top.
        mirrored = composed.transpose(Image.FLIP_TOP_BOTTOM)
        new_img = Image.new("RGBA", (w, h * 2), token_cfg.background_color.as_rgb())
        new_img.paste(mirrored, (0, 0), mirrored)
        new_img.paste(composed, (0, h), composed)
        final_img = new_img
    elif token_cfg.tent_style == TentStyle.rotated:
        w, h = composed.size
        rotated = composed.rotate(180, expand=True)
        # rotated may have different dimensions; ensure width matches by
        # padding if necessary.
        rw, rh = rotated.size
        # Create a canvas of width max(w, rw) and height h + rh.
        new_w = max(w, rw)
        new_h = h + rh
        new_img = Image.new("RGBA", (new_w, new_h), token_cfg.background_color.as_rgb())
        # Paste rotated at the top centred.
        rot_x = (new_w - rw) // 2
        new_img.paste(rotated, (rot_x, 0), rotated)
        # Paste original at bottom centred.
        orig_x = (new_w - w) // 2
        new_img.paste(composed, (orig_x, rh), composed)
        final_img = new_img

    # 7. Compute physical dimensions in points.
    # Each pixel corresponds to (1 / dpi) inches.  1 inch = 72 points.
    px_w, px_h = final_img.size
    width_pts = px_w / page_dpi * 72.0
    height_pts = px_h / page_dpi * 72.0
    return RenderedToken(final_img, width_pts, height_pts)


###############################################################################
# Page layout and PDF generation
###############################################################################

def render_tokens_to_pdf(config: PageOfTokensConfig, output_pdf: Path) -> None:
    """
    Render all tokens specified in the configuration and write them into a
    paginated PDF.  Tokens are placed sequentially across rows and
    columns on each page using the provided page size, orientation, and
    margin settings.  No more than `max_pages` pages will be produced.

    Parameters
    ----------
    config : PageOfTokensConfig
        The full configuration including page layout and token definitions.
    output_pdf : Path
        The path where the resulting PDF will be written.
    """
    page_cfg = config.page_config
    # Pre-render all tokens.  We need to know their physical sizes to
    # determine how many will fit per page.  Maintain the original order.
    rendered_tokens: List[RenderedToken] = []
    for name, tok_cfg in config.token_configs.items():
        rendered = render_single_token(tok_cfg, page_cfg.dpi)
        rendered_tokens.append(rendered)

    if not rendered_tokens:
        # Nothing to render; create an empty PDF.
        c = canvas.Canvas(str(output_pdf), pagesize=page_cfg.page_dimensions)
        c.save()
        return

    # Assume all tokens have the same dimensions; if not, we still
    # compute placement based on the largest width and height across tokens.
    max_token_width = max(t.width_pts for t in rendered_tokens)
    max_token_height = max(t.height_pts for t in rendered_tokens)

    page_width, page_height = page_cfg.page_dimensions
    margin_pt = page_cfg.page_margin_inches * 72.0
    available_width = page_width - 2 * margin_pt
    available_height = page_height - 2 * margin_pt
    if max_token_width <= 0 or max_token_height <= 0:
        raise ValueError("Invalid token dimensions; cannot lay out tokens.")
    tokens_per_row = max(1, int(floor(available_width / max_token_width)))
    tokens_per_col = max(1, int(floor(available_height / max_token_height)))
    tokens_per_page = tokens_per_row * tokens_per_col

    if tokens_per_page == 0:
        raise ValueError(
            "Tokens are too large to fit on the page with the specified margins."
        )

    total_tokens = len(rendered_tokens)
    total_pages_needed = int((total_tokens + tokens_per_page - 1) / tokens_per_page)
    pages_to_create = min(total_pages_needed, page_cfg.max_pages)

    # Begin writing the PDF.
    c = canvas.Canvas(str(output_pdf), pagesize=(page_width, page_height))
    token_idx = 0
    for page_num in range(pages_to_create):
        for row in range(tokens_per_col):
            for col in range(tokens_per_row):
                if token_idx >= total_tokens:
                    break
                token = rendered_tokens[token_idx]
                # Compute draw position.  PDF coordinate origin is bottom-left.
                x_pos = margin_pt + col * max_token_width
                # Place rows starting from top margin downward.
                y_pos = page_height - margin_pt - (row + 1) * max_token_height
                # Convert PIL image to a format accepted by reportlab.  We can
                # use ImageReader on a BytesIO or the image directly.
                from reportlab.lib.utils import ImageReader

                img_reader = ImageReader(token.image)
                c.drawImage(
                    img_reader,
                    x_pos,
                    y_pos,
                    width=token.width_pts,
                    height=token.height_pts,
                    mask="auto",
                )
                token_idx += 1
            if token_idx >= total_tokens:
                break
        if page_num < pages_to_create - 1:
            c.showPage()
    c.save()


###############################################################################
# Command line interface
###############################################################################

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render paper doll tokens from SVG templates and arrange them on a PDF."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the YAML configuration file (see models in script).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination PDF file to write the rendered tokens.",
    )
    args = parser.parse_args()

    # Read YAML and parse into config model.
    data = read_yaml_file(args.config)
    try:
        config = PageOfTokensConfig.parse_obj(data)
    except Exception as e:
        raise SystemExit(f"Error parsing configuration: {e}")

    # Render tokens and write PDF.
    render_tokens_to_pdf(config, args.output)


if __name__ == "__main__":
    main()