from collections import namedtuple
import io
from typing import IO, Any, Dict, List, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from paper_token_maker.token import Token
from reportlab.lib.utils import ImageReader
from tqdm import tqdm

Point = namedtuple('Point', ['x', 'y'])

class Page():
    def __init__(
        self,
        dpi=400,
        pagesize=letter,
        page_margin=0.25,
        max_pages=None,
    ):
        self.dpi = dpi
        self.pagesize = pagesize
        self.page_margin = page_margin * inch
        self.max_pages = max_pages

    @property
    def page_width(self) -> float:
        return self.pagesize[0]

    @property
    def page_height(self) -> float:
        return self.pagesize[1]

    @property
    def renderable_width(self) -> float:
        return self.page_width - 2 * self.page_margin

    @property
    def renderable_height(self) -> float:
        return self.page_height - 2 * self.page_margin

    @property
    def right_margin(self) -> float:
        return self.page_width - self.page_margin

    @property
    def bottom_margin(self) -> float:
        return self.page_height - self.page_margin

    def validate_token(self, token: Token):
        fits_horizontally = (token.image_width <= self.renderable_width)
        fits_vertically = (token.image_height <= self.renderable_height)
        if not fits_horizontally or not fits_vertically:
            raise ValueError(f'Token {token} does not fit on a page of size {self.renderable_width / inch} inches by {self.renderable_height / inch} inches (size excludes page margins).')

    def token_image_size_ordinal(self, token) -> Any:
        """
        Hash to group images by size. Any two image in the same 0.01 inch
        bucket are considered to be in the same size group
        """
        width = int(token.image_width / (0.01 * inch))
        height = int(token.image_height / (0.01 * inch))
        return (height, width)

    def arrange(self, tokens: List[Token]) -> List[List[Tuple[Point, Token]]]:
        """
        Two factors to consider optimizing over:
        1. we want to reduce the amount of wasted space as much as possible.
        2. we want to reduce the amount of cutting (labor) as much as possible.
        
        However, since the user is deciding which things and how many to print
        it's hard to imagine optimizing #1 better than sticking with an easy-to-
        understand algorithm and letting the user do their thing.

        So we just do the simplest algorithm and do wrapping horizontal lines of
        tokens.
        """
        token_groups: Dict[Any, List[Token]] = {}
        for token in tokens:
            ordinal = self.token_image_size_ordinal(token)
            token_group = token_groups.get(ordinal, [])
            token_group.append(token)
            token_groups[ordinal] = token_group

        # from largest to smallest token
        page_token_placements = []
        token_placements = []
        x = self.page_margin
        y = self.page_margin
        max_height_in_row = 0
        for ordinal in sorted(token_groups.keys()):
            token_group = token_groups[ordinal]
            for token in token_group:
                for _ in range(token.copies):
                    self.validate_token(token)
                    if x + token.image_width > self.right_margin:
                        y += max_height_in_row
                        x = self.page_margin
                    if y + token.image_height > self.bottom_margin:
                        page_token_placements.append(token_placements)
                        if len(page_token_placements) == self.max_pages:
                            print('Cannot render all of these tokens due to page limit. Doing my best.')
                            return page_token_placements
                        else:
                            token_placements = []
                            x = self.page_margin
                            y = self.page_margin
                            max_height_in_row = 0
                    placement = Point(x, y)
                    token_placements.append((placement, token))
                    x += token.image_width
                    max_height_in_row = max(max_height_in_row, token.image_height)

        if len(token_placements) > 0:
            page_token_placements.append(token_placements)
        return page_token_placements

    def render(self, tokens: List[Token], output_stream_or_filename: str | IO[bytes]):
        c = canvas.Canvas(output_stream_or_filename, pagesize=self.pagesize)
        arrangement = self.arrange(tokens)
        count = 0
        num_tokens = sum((len(page_arrangement) for page_arrangement in arrangement))
        with tqdm(total=num_tokens, desc='Tokens rendered') as pbar:
            for page_arrangement in arrangement:
                for (point, token) in page_arrangement:
                    token_image = token.to_image(dpi=self.dpi, token_index=count)
                    img_byte_io = io.BytesIO()
                    token_image.save(img_byte_io, format='PNG')
                    img_byte_io.seek(0)
                    token_image_reader = ImageReader(img_byte_io)
                    c.drawImage(token_image_reader, point.x, point.y, width=token.image_width, height=token.image_height)
                    count += 1
                    pbar.update(1)
                c.showPage() # this draws the current page and goes to the next page
        c.save()
