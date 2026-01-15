from __future__ import annotations

import enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, FilePath, field_serializer, field_validator
from pydantic_extra_types.color import Color
from reportlab.lib.units import inch


class PageSize(str, enum.Enum):
    letter = "letter"
    double_letter = "double_letter"

    @property
    def size(self) -> Tuple[float, float]:
        """Return the page dimensions in points."""
        if self == PageSize.letter:
            return (8.5 * inch, 11 * inch)
        elif self == PageSize.double_letter:
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

    @field_validator("dpi")
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

    @field_serializer("pagesize")
    def serialize_pagesize(self, v: PageSize, _info):
        return v.value

    @field_serializer("orientation")
    def serialize_orientation(self, v: PageOrientation, _info):
        return v.value


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

    @field_serializer("placement")
    def serialize_placement(self, v: PlaceholderAlignment, _info):
        return v.value

    @field_serializer("resize_method")
    def serialize_resize_method(self, v: PlaceholderResizeMethod, _info):
        return v.value


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
