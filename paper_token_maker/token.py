from typing import Dict, List, Optional, Tuple
from PIL import Image
from PIL import ImageOps
from reportlab.lib.units import inch

class Token():
    def __init__(
            self,
            front_image_path: str,
            height: float,
            width: float,
            back_image_path: Optional[str] = None,
            border_thickness: float = 0.1,
            border_colors: Tuple[int, int, int] | List[Tuple[int, int, int]] = (254, 254, 254),
            mirror_back: bool = False,
            copies: int = 1,
            metadata: Dict[any, any] = None,
    ):
        """
        front_image_path:   str path to image to render on front of token
        back_image_path:    str path to image to render on back of token.
                            if omitted, defaults to front_image_path.
        height:             float height in inches of each printed token image.
        width:              float width in inches of each printed token image.
        border_thickness:   float thickness in inches of the border around token
        border_colors:      int RGB Tuple color of border. Default off-white
                            if multiple colors supplied, cycle through them.
        mirror_back:        bool if True, mirror back so that text would read
                            properly. May cause misalignment with front if the
                            picture is not horizontally symmetrical.
        copies:             int number of times token should be printed.
        metadata:           unused. only so that you can easily store metadata
                            in the yaml.
        """
        self._front_image_path = front_image_path
        self._back_image_path = back_image_path
        self._height = height * inch
        self._width = width * inch
        self._border_thickness = border_thickness * inch
        self._mirror_back = mirror_back
        self._copies = copies
        self._border_colors = border_colors

    def __str__(self):
        return (f"Token(front_image_path='{self._front_image_path}', "
                f"height={self._height / inch} inches, width={self._width / inch} inches, "
                f"border_thickness={self._border_thickness / inch} inches, ")

    def __repr__(self):
        return (f"Token(front_image_path={repr(self._front_image_path)}, "
                f"height={self._height}, width={self._width}, "
                f"back_image_path={repr(self._back_image_path)}, "
                f"border_thickness={self._border_thickness}, "
                f"mirror_back={self._mirror_back}, copies={self._copies})")

    @property
    def image_width(self) -> float:
        """ returns in reportlab units """
        return self._width + self._border_thickness * 2

    @property
    def image_height(self) -> float:
        """ returns in reportlab units """
        return self._height * 2 + self._border_thickness * 4

    @property
    def copies(self) -> int:
        return self._copies

    def _border_color(self, token_index) -> Tuple[int, int, int]:
        try:
            color = self._border_colors[token_index % len(self._border_colors)]
            len(color)  # checks that it's not an int
        except:
            color = self._border_colors
        # output needs to be a tuple
        return (color[0], color[1], color[2])

    def to_image(self, dpi: int, token_index=0) -> Image:
        dpi_per_inch = dpi / inch  # convert reportlab inch to pixels
        front_img = Image.open(self._front_image_path)
        back_image_path = self._back_image_path or self._front_image_path
        back_img = Image.open(back_image_path)
        pixel_width = int(self._width * dpi_per_inch)
        pixel_height = int(self._height * dpi_per_inch)
        front_img = front_img.resize((pixel_width, pixel_height))
        back_img = back_img.resize((pixel_width, pixel_height))
        back_img = ImageOps.flip(back_img)

        if self._mirror_back:
            back_img = ImageOps.mirror(back_img)

        pixel_border = int(self._border_thickness * dpi_per_inch)
        color = self._border_color(token_index)
        combined_img = Image.new(
            'RGB',
            (int(self.image_width * dpi_per_inch), int(self.image_height * dpi_per_inch)),
            color=color,
            )
        # front img is on bottom so that fold-crease is on top.
        combined_img.paste(back_img, (pixel_border, pixel_border))
        combined_img.paste(front_img, (pixel_border, 3 * pixel_border + back_img.height))
        return combined_img
