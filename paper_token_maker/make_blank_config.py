import argparse
import json
from typing import Dict, List
import pandas as pd
import yaml

import paper_token_maker.structs as S
from pydantic_extra_types.color import Color


def create_blank_token_config(size: str) -> S.TokenConfig:
    """Create a single TokenConfig for an NPC token."""

    # pick template svg by size
    template_svg = f"res/blank/templates/template_npc_size{size}.svg"
    bg_color = Color("ffffffff")

    # Build placeholders like in the example YAML. We return a plain dict payload,
    # then we'll let pydantic model_validate() coerce into S.TokenConfig.
    token_cfg_dict = {
        "template_svg": template_svg,
        "background_color": str(bg_color),  # ensure we store the rgba string
        "tent_style": "rotated",
        "placeholders": [],
    }

    # Validate into the real TokenConfig model so we catch schema issues early
    return S.TokenConfig.model_validate(token_cfg_dict)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_small', type=int, default=3)
    parser.add_argument('--num_medium', type=int, default=5)
    parser.add_argument('--num_large', type=int, default=3)
    parser.add_argument('--num_huge', type=int, default=2)
    parser.add_argument('--output_config', type=str, default="configs/blanks.yaml")
    args = parser.parse_args()

    token_size_counts = {
        "0.5": args.num_small,
        "1": args.num_medium,
        "2": args.num_large,
        "3": args.num_huge,
        }

    token_cfgs = []
    for size, number in token_size_counts.items():
        cfg = create_blank_token_config(size)
        for _ in range(number):
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

    # 3. Write YAML to specified output location
    # We'll dump the validated model back to plain data first so we don't get
    # pydantic internals in the YAML.
    output_json = page_of_tokens_cfg.model_dump_json()
    output_dict = json.loads(output_json)

    with open(args.output_config, "w") as f:
        yaml.safe_dump(output_dict, f, sort_keys=False)


if __name__ == "__main__":
    main()
