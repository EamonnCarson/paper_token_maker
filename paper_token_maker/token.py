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
            bottom_margin: float = 0.5,
            border_thickness: float = 0.1,
            border_colors: Tuple[int, int, int] | List[Tuple[int, int, int]] = (255, 255, 255),
            background_colors: Tuple[int, int, int] | List[Tuple[int, int, int]] = (0, 0, 0),
            background_image_paths: Optional[str | List[str]] = None,
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
        bottom_margin:      float height of the margin at the base of the token
                            (you need some paper to stick / paste onto a stand).
        border_thickness:   float thickness in inches of the border around token
        border_colors:      int RGB Tuple color of border. Default is white.
                            if multiple colors supplied, cycle through them.
        background_colors:  int RGB Tuple color of background. Default black
                            if multiple colors supplied, cycle through them.
        background_image_paths:
                            str or list[str] image paths to render behind token.
                            if multiple images supplied, cycle through them.
                            overrides background color.
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
        self._bottom_margin = bottom_margin * inch
        self._border_thickness = border_thickness * inch
        self._mirror_back = mirror_back
        self._copies = copies
        self._border_colors = border_colors
        self._background_colors = background_colors
        self._background_image_paths = background_image_paths

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
        return self._height * 2 + self._border_thickness * 4 + self._bottom_margin * 2

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

    def _background_color(self, token_index) -> Tuple[int, int, int]:
        try:
            color = self._background_colors[token_index % len(self._background_colors)]
            len(color)  # checks that it's not an int
        except:
            color = self._background_colors
        # output needs to be a tuple
        return (color[0], color[1], color[2])

    def _background_image(self, token_index: int, image_size: Tuple[int, int]) -> Image:
        if self._background_image_paths is not None:
            if isinstance(self._background_image_paths, str):
                background_image_path = self._background_image_paths
            else:
                index = token_index % len(self._background_image_paths)
                background_image_path = self._background_image_paths[index]
            background_image = Image.open(background_image_path)
            background_image = background_image.resize(image_size)
        else:
            try:
                color = self._background_colors[token_index % len(self._background_colors)]
                len(color)  # checks that it's not an int
            except:
                color = self._background_colors
            # only tuples accepted
            color = (color[0], color[1], color[2])
            background_image = Image.new('RGBA', image_size, color)
        return background_image

    def apply_background(self, image: Image, background: Image):
        background.paste(image, (0, 0), mask=image)
        return background

    def set_corner_pixels_black(self, image: Image, cross_radius_px=10) -> None:
        # Set corner pixels to black
        right = image.width - 1
        bottom = image.height - 1
        pixels = image.load()
        black = (0, 0, 0)
        for i in range(cross_radius_px):
            pixels[0, 0+i] = black  # Top-left corner
            pixels[right-i, 0] = black  # Top-right corner
            pixels[0+i, bottom] = black  # Bottom-left corner
            pixels[right, bottom-i] = black  # Bottom-right corner
            pixels[0+i, 0] = black  # Top-left corner
            pixels[right, 0+i] = black  # Top-right corner
            pixels[0, bottom-i] = black  # Bottom-left corner
            pixels[right-i, bottom] = black  # Bottom-right corner

    def to_image(self, dpi: int, token_index=0) -> Image:
        dpi_per_inch = dpi / inch  # convert reportlab inch to pixels

        # load front and back images, resize them, orient them.
        front_img = Image.open(self._front_image_path).convert("RGBA")
        back_image_path = self._back_image_path or self._front_image_path
        back_img = Image.open(back_image_path).convert("RGBA")
        pixel_width = int(self._width * dpi_per_inch)
        pixel_height = int(self._height * dpi_per_inch)
        token_pixel_dims = (pixel_width, pixel_height)
        front_img = front_img.resize(token_pixel_dims)
        back_img = back_img.resize(token_pixel_dims)

        # apply background color or image
        pixel_border = int(self._border_thickness * dpi_per_inch)
        border_color = self._border_color(token_index)
        background_image = self._background_image(token_index, token_pixel_dims)
        front_img = self.apply_background(front_img, background_image)
        background_image = self._background_image(token_index, token_pixel_dims)
        back_img = self.apply_background(back_img, background_image)

        # flip/mirror the back image as needed
        back_img = ImageOps.flip(back_img)
        if self._mirror_back:
            back_img = ImageOps.mirror(back_img)

        # stack the front and back images within the frame, apply border
        combined_img = Image.new(
            'RGBA',
            (int(self.image_width * dpi_per_inch), int(self.image_height * dpi_per_inch)),
            color=border_color,
            )
        # front img is on bottom so that fold-crease is on top.
        pixel_bottom_margin = int(self._bottom_margin * dpi_per_inch)
        y_back = pixel_border + pixel_bottom_margin
        y_front = y_back + pixel_border + back_img.height + pixel_border
        combined_img.paste(back_img, (pixel_border, y_back), mask=back_img)
        combined_img.paste(front_img, (pixel_border, y_front), mask=front_img)
        self.set_corner_pixels_black(combined_img)
        return combined_img
