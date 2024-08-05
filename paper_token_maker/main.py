from typing import List
from paper_token_maker.page import Page
from paper_token_maker.token import Token
from argparse import ArgumentParser
import yaml

def get_parser(parser=None):
    parser = parser or ArgumentParser()
    parser.add_argument('--config_yaml', required=True, help='Config yaml that defines the tokens you want to print. See configs/example.yaml for example.')
    parser.add_argument('--output_file', required=True, help='file path to output pdf to.')
    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()
    with open(args.config_yaml) as f:
        cfg = yaml.safe_load(f)
    tokens: List[Token] = [Token(**token_cfg) for token_cfg in cfg['tokens']]
    page: Page = Page(**cfg['page'])
    page.render(tokens, args.output_file)

if __name__ == "__main__":
    main()
