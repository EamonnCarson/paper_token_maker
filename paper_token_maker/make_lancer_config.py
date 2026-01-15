import argparse
import json
from typing import Dict, List
import pandas as pd
import yaml

import paper_token_maker.structs as S
from pydantic_extra_types.color import Color


# Map NPC role -> background color (Color just helps validate that it's RGBA)
color_mapping: Dict[str, Color] = {
    "striker": Color("dbb57fff"),
    "artillery": Color("e4b0baff"),
    "defender": Color("a3c57fff"), #Color("bebb80ff"),
    "controller": Color("bcb2deff"),
    "support": Color("84c6b0ff"),
    "cephalapunk": Color("91c0dfff"),
    "hellrunner": Color("ffcd1aff"),
    "morningstar": Color("bebb80ff"),
    "parallax": Color("84c6b0ff"),
    "raider": Color("7695a2ff"),
    "verdant": Color("9dc482ff"),
}


def create_token_config(
    image_path: str, size: str, role: str, color_scheme: str, number: int, image_fill_height: bool, image_y_offset: float
) -> S.TokenConfig:
    """
    Create a single TokenConfig for an NPC token.

    image_path: path to the NPC art, e.g. "res/lancer/images/pishly_npc_factions/Cephalapunk_Leech.png"
    size: numeric size from CSV, e.g. 0.5
    role: NPC combat role, e.g. "controller"
    number: which copy of the token (1, 2, etc.) -> used for roman numeral badge
    """

    # pick template svg by size
    template_svg = f"res/lancer/templates/template_npc_size{size}.svg"

    # resolve background color from role
    # fall back to controller lilac if role is missing/unknown
    bg_color = color_mapping.get(color_scheme.lower(), color_mapping["controller"])

    # roman numeral overlay path depends on number
    roman_path = f"res/lancer/images/roman_numerals/roman_numeral_{number}.png"
    chevrons_path = f"res/lancer/images/chevrons/white_chevrons_{number}.png"

    # role icon path depends on role
    role_icon_path = f"res/lancer/images/role_icons/{role.lower()}.png"

    # Build placeholders like in the example YAML. We return a plain dict payload,
    # then we'll let pydantic model_validate() coerce into S.TokenConfig.
    token_cfg_dict = {
        "template_svg": template_svg,
        "background_color": str(bg_color),  # ensure we store the rgba string
        "tent_style": "rotated",
        "placeholders": [
            {
                "placeholder_name": "placeholder_image",
                "replacement_image": image_path,
                "placement": "center",
                "resize_method": "fill_height" if image_fill_height else "fill_width",
                "keep_aspect_ratio": True,
                "offset_y_inch": image_y_offset,
            },
            {
                "placeholder_name": "placeholder_role_icon",
                "replacement_image": role_icon_path,
                "placement": "center",
                "resize_method": "fill_width",
                "keep_aspect_ratio": True,
            },
            {
                "placeholder_name": "placeholder_id",
                "replacement_image": roman_path,
                "placement": "center",
                "resize_method": "fill_height",
                "keep_aspect_ratio": True,
            },
            {
                "placeholder_name": "placeholder_chevrons",
                "replacement_image": chevrons_path,
                "placement": "center",
                "resize_method": "fill_width",
                "keep_aspect_ratio": True,
            },
        ],
    }

    # Validate into the real TokenConfig model so we catch schema issues early
    return S.TokenConfig.model_validate(token_cfg_dict)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('output_config')
    args = parser.parse_args()
    # 1. Load the source manifest of NPC tokens we want to generate
    file_path = args.manifest
    df = pd.read_csv(file_path, dtype=str)
    if 'image_fill_height' in df:
        df['image_fill_height'] = df.image_fill_height.fillna("false")
        if not df.image_fill_height.str.lower().isin(["true", "false"]).all():
            raise ValueError("image fill height must be true or false")
        df['image_fill_height'] = df.image_fill_height.str.lower() == "true"
    else:
        df['image_fill_height'] = False
    if 'image_y_offset' in df:
        df['image_y_offset'] = df['image_y_offset'].fillna("0.0")
        df['image_y_offset'] = df['image_y_offset'].apply(float)
    else:
        df['image_y_offset'] = 0.0
    df = df.fillna("")

    # Expected columns in npc_faction_manifest.csv:
    # - file_path (string to art)
    # - size (like 0.5, 1, etc.)
    # - role (like controller / striker / etc.)
    #
    # If your CSV is different, update the attribute access below.

    token_cfgs: List[S.TokenConfig] = []

    for row in df.itertuples(index=False):
        # row.file_path, row.size, row.role
        for number in [1, 2]:
            cfg = create_token_config(
                image_path=row.file_path,
                size=row.size,
                role=row.role,
                color_scheme=row.faction or row.role,
                number=number,
                image_fill_height=row.image_fill_height,
                image_y_offset=row.image_y_offset
            )
            token_cfgs.append(cfg)

    # 2. Build the full PageOfTokensConfig payload
    # We'll assemble a dict that matches PageOfTokensConfig, then validate it.
    page_cfg_dict = {
        "dpi": 450,
        "pagesize": "double_letter",
        "orientation": "landscape",
        "page_margin_inches": 0.5,
        "max_pages": 1,
    }

    # token_configs in the YAML example is a mapping of token_name -> token_config.
    # We can name them using their index or something stable like "<basename>_<n>"
    token_cfg_map: Dict[str, dict] = {}
    for i, tc in enumerate(token_cfgs):
        token_cfg_map[f"token_{i + 1}"] = tc.model_dump()

    page_of_tokens_cfg = S.PageOfTokensConfig.model_validate(
        {
            "page_config": page_cfg_dict,
            "token_configs": token_cfg_map,
        }
    )

    # 3. Write YAML to configs/pishly_npc_faction_tokens.yaml
    # We'll dump the validated model back to plain data first so we don't get
    # pydantic internals in the YAML.
    output_json = page_of_tokens_cfg.model_dump_json()
    output_dict = json.loads(output_json)

    with open(args.output_config, "w") as f:
        yaml.safe_dump(output_dict, f, sort_keys=False)


if __name__ == "__main__":
    main()
