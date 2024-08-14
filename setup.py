import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="paper_token_maker",
    version="1.0.0",
    author="Eamonn Carson",
    description="Makes double sided paper tokens",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/EamonnCarson/paper_token_maker",
    packages=setuptools.find_packages(
        include=['paper_token_maker']
    ),
    python_requires='>=3.10',
    install_requires=[
        'pillow',
        'reportlab',
        'pyyaml',
        'tqdm',
    ],
    entry_points = {
        'console_scripts': [
            'paper_token_maker=paper_token_maker.main:main',
        ],
    }
)