# Reproducing results of the MonkeyDrive paper

Code and data accompanying *MonkeyDrive: An open-source microdrive for nonhuman primate neurophysiology*

This repository reproduces the validation analyses in Figure 3 and the three example drift maps in Figure 4. The control software and firmware live in [MonkeyDrive](https://github.com/jazlab/MonkeyDrive). You can learn more at our [project website](https://jazlab.github.io/MonkeyDrive/).

## Get the code and data

Clone the repository or download its source ZIP. Figure 3 data is included in the source. The six Figure 4 NumPy arrays are distributed separately in the [versioned data release](https://github.com/jazlab/monkeydrive_paper/releases/tag/data-v1); Git LFS is not required. Use Python 3.11 or later for the download command.

```bash
git clone https://github.com/jazlab/monkeydrive_paper.git
cd monkeydrive_paper
python download_data.py
python verify_data.py
```

`download_data.py` downloads `figure4-data.zip`, verifies the archive and each extracted file against SHA-256 checksums, and installs the arrays in `figures/fig4/data/`. It skips downloading when all six files already match. Allow about 3 GB of free disk space for the download, extraction, and outputs. You can skip the download to run only Figure 3.

While the repository is private, the downloader uses an authenticated [GitHub CLI](https://cli.github.com/) session (`gh auth login`) if anonymous download is unavailable. Once the repository is public, no GitHub account or CLI is needed to download the data. Alternatively, download `figure4-data.zip` from the release in your browser and run `python download_data.py --archive /path/to/figure4-data.zip`.

`verify_data.py` checks every input and reports missing or damaged files. For Figure 3 alone, use `python verify_data.py --figure 3`.

The root [data manifest](data_manifest.json) records the release asset and its checksum, all input files and checksums, and region, session, and probe identifiers for Figure 4.

## Install and reproduce

Use Python 3.11 or later (tested with Python 3.12). From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce.py
```

On Windows Command Prompt, activate with `.venv\Scripts\activate` instead. On systems where Python is named `python3`, use that command to create the environment. The reproduction command runs without a display, verifies the input data first, and saves new files to `results/`, leaving the supplied reference plots intact.

| Paper panel | Inputs | Analysis | New outputs |
| --- | --- | --- | --- |
| Figure 3A | Three moving trials and one stationary recording per drive | Lateral laser-spot RMS displacement, detrending, statistics, representative XY trajectories | `results/fig3a/` |
| Figure 3B | Ten 10-mm displacement measurements per drive | Signed error, accuracy and precision, Welch ANOVA, Games–Howell and Brown–Forsythe comparisons | `results/fig3b/` |
| Figure 4 | Paired detected peaks and peak locations for thalamus, LIP, and dentate nucleus | Uncorrected peak depth versus recording time | `results/fig4/` |

To run a subset or choose a destination:

```bash
python reproduce.py --figure 3
python reproduce.py --figure 4 --output-dir my_results
```

See [Figure 3](figures/fig3/README.md) and [Figure 4](figures/fig4/README.md) for figure-specific methods, data details, and output descriptions. All analysis dependencies are pinned in the root `requirements.txt`.

### Interactive notebooks

With the same virtual environment active, start from the repository root:

```bash
python -m pip install -r requirements-notebook.txt
python -m jupyterlab
```

Open a notebook in JupyterLab, then run its cells in order:

| Figure | Notebook | Notebook outputs |
| --- | --- | --- |
| Figure 3 | [`figures/fig3/validation.ipynb`](figures/fig3/validation.ipynb) | `figures/fig3/results/fig3a/` and `figures/fig3/results/fig3b/` |
| Figure 4 | [`figures/fig4/drift_map.ipynb`](figures/fig4/drift_map.ipynb) | `figures/fig4/results/` |

Use each notebook's containing folder as its working directory (the JupyterLab default when opening a notebook). Both notebooks use the existing analysis code. Figure 3 provides editable plotting settings, inline plots, and result tables for exploration. `requirements-notebook.txt` includes the shared analysis dependencies and adds JupyterLab for both notebooks.

## License

Repository code, documentation, and release data are distributed under the [MIT License](LICENSE). Dependencies retain their own licenses. Please cite *MonkeyDrive: An open-source microdrive for nonhuman primate neurophysiology* when using these materials.
