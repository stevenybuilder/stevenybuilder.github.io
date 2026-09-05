# Steven Yang’s research blog

A static personal site with a report on instruction following in π0.5.

Edit the report in `content/pick-it-up.html`, shared pages in `scripts/build.mjs`, and presentation in `assets/site.css` and `assets/site.js`.

Build with `node scripts/build.mjs`. Preview with `python3 -m http.server 4173`.

The figures use recorded experiment data, not illustrative numbers. Downloadable data and source hashes live in `assets/data/`. Robot clips are cropped from the archived recording and encoded for the browser; no generated frames or reconstructed scene details are added. The browser plays the clips at half their encoded rate for inspection.

To regenerate assets from the research archive, install NumPy and Matplotlib and run `python scripts/prepare_assets.py /path/to/research-archive` (FFmpeg is required). The source archive is not needed to build or serve the site.

Experiment code: https://github.com/stevenybuilder/mechinterp-vla
