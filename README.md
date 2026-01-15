# Paper Token Maker
- Printers often have alignment issues, making it hard to print on front and back of a sheet.
- This tool automatically mirrors your tokens so you can print fold-over tokens.
- yaml file specifying what tokens you want printed.

# How to Use
## 1. Create your configuration
A token sheet configuration is usually pretty long and repetitive.
Run a program to create a token sheet config for yourself.
for example, I made one for lancer that uses the (amazing) pishly token set.
I can't distribute his artwork obviously, but if you download his zip, unpack it into
the images folder and run

```bash
mkdir -p configs
manifest=res/lancer/data/npc_faction_manifest.csv  # data about each token
output_config=configs/pishly_npc_faction_tokens.yaml  # a specification of what to render
uv run paper_token_maker/make_lancer_config.py $manifest $output_config
```

And it will automatically output a configuration for you based off of the npc data I have placed here.

## 2. Create your token sheet
```bash
mkdir -p outputs
input_config=configs/pishly_npc_faction_tokens.yaml  # a specification of what to render
output=outputs/pishly_npc_faction_tokens.pdf
uv run paper_token_maker --config $input_config --output $output
```

