FROM ubuntu:24.10 AS base

RUN apt update && apt install -y wget

# install miniconda
ENV CONDA_DIR=/root/miniconda3
ENV PATH=$CONDA_DIR/bin:${PATH}
# look up version and sha in this directory https://repo.anaconda.com/miniconda/
ENV CONDA_VERSION=py312_24.5.0-0
ENV CONDA_SHA_HASH="4b3b3b1b99215e85fd73fb2c2d7ebf318ac942a457072de62d885056556eb83e"
ENV CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh"
RUN wget --quiet $CONDA_URL -O conda_installer.sh \
    && echo "$CONDA_SHA_HASH conda_installer.sh" > verify.txt \
    && sha256sum -c verify.txt \
    && bash conda_installer.sh -b \
    && rm -f conda_installer.sh

# install conda environment
COPY environment.yaml environment.yaml
RUN conda init \
    && conda init bash \
    && conda env create -n paper_token_maker -f environment.yaml \
    && conda clean --all

# Settings to make this conda environment the default environment
# the second export is a hack to correctly set the LD_LIBRARY_PATH for this env
# by default inside the container
SHELL ["conda", "run", "-n", "paper_token_maker", "/bin/bash", "-c"]
RUN echo "conda activate paper_token_maker" >> $HOME/.bashrc
#&& echo "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib" >> $HOME/.bashrc