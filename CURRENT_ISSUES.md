# MediaTruth - Current Project Issues & Technical Debt

This document outlines the current state of bugs, configuration issues, and technical debt facing the MediaTruth platform as of the latest debugging session. 

---

## 1. Virtual Environment Fragmentation
**Problem:** There are currently two separate Python virtual environments in the `backend/` directory: `venv` and `.venv`. 
- Earlier today, we successfully configured and installed everything into `.venv`. 
- However, your current PowerShell terminal is using `venv` (activated via `.\venv\Scripts\Activate.ps1`), which has a completely different, slightly older, and broken set of packages.
**Action Item:** Standardize on a single environment. We should delete the broken `venv` folder to prevent future confusion and strictly use `.venv` for all backend operations.

## 2. Supabase & HTTPX Dependency Hell (The 500 Crash)
**Problem:** When a file is uploaded, the image pipelines process it successfully, but the final step—saving the results to Supabase—crashes the server with a `500 Internal Server Error`.
- **The Traceback:** `TypeError: Client.__init__() got an unexpected keyword argument 'proxy'`
- **The Cause:** The `gotrue==2.9.1` package (a sub-dependency of Supabase used for authentication) attempts to use a `proxy=` argument under the hood when establishing the HTTP connection. However, the `proxy` keyword was only added in `httpx 0.27.0`.
- Because our `requirements.txt` specifically pins `httpx==0.25.2` (to satisfy `supabase==2.4.0`), `gotrue` crashes instantly upon instantiation.
**Action Item:** Resolve the "dependency triangle". The best path forward is to upgrade the entire Supabase ecosystem to the latest 2.x releases (which fully support the newer `httpx` versions) rather than holding `httpx` back. In the meantime, I attempted to downgrade `gotrue` to a version without the proxy keyword, but that failed (see Problem 4).

## 3. OpenCV Incompatibility with Satellite/Geospatial TIFFs
**Problem:** Uploading `land-cover-menz-gera.tiff` triggers a background backend warning: `[ERROR:0]... failed TIFFReadRGBATile`.
- OpenCV (`cv2`) handles standard RGB/RGBA JPEGs and PNGs perfectly. However, satellite/land-cover TIFFs often use multi-spectral bands (e.g., 4 to 8 channels instead of 3), custom geographic encodings (GeoTIFFs), or non-standard internal tiling schemas.
- Our AI Inference pipelines currently rely on OpenCV to open images. When they hit this TIFF format, they fail to extract the image array. The code gracefully catches this failure and returns a "partial" result (which is good), but the models aren't actually analyzing the image.
**Action Item:** If geospatial TIFF support is a priority feature for MediaTruth, the inference pipeline (`services/model_loader.py` or individual detectors) should fall back to `tifffile` or introduce a geospatial reading library like `rasterio` when the file extension is `.tiff` or `.tif`. 

## 4. Immediate Blocker: Broken Server State (`ModuleNotFoundError`)
**Problem:** The `uvicorn` backend is completely stopped right now with: `ModuleNotFoundError: No module named 'supabase'`.
- Why? While trying to patch the `gotrue` issue, I instructed pip to downgrade `gotrue` to `2.8.2`. Unfortunately, that specific version tag does not exist in PyPI for Windows, causing the `pip install` script to abort halfway through. As a result, `supabase` was uninstalled but not re-installed.
**Action Item:** Fix `requirements.txt` (by reverting `gotrue==2.8.2` and removing hardcoded supabase sub-package versions) and manually run `pip install -r requirements.txt` inside the correct `.venv` environment to restore the basic ability to boot the server.
