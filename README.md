# document-amr-datascripts

This contains initial scripts for handling sets of AMRs with multi-sentence data.

Currently that primarily means converting data from the MSAMR anontation into document graphs [as described in the Multi-sentence AMR paper](https://aclanthology.org/C18-1313/), so that they can be scored by SMATCH. 

The current main code takes a folder of MS-AMR xml files and a folder of AMR files, and produces a big document graph for each MS-AMR document:

```python msamrgraph.py --amrunsplit <AMR 3.0 data, pointing to the "unsplit" data> --msamr <location of a folder of MS-AMR files> --output <output folder>```


I'll hopefully make it more usable for other tasks, and expand beyond the MS-AMR assumptions, but can't promise any hours to this project, so please feel free to fork or submit a PR!  


