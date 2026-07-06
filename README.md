# AI-Based Image Difference Detection

FastAPI + React application for detecting and summarizing visual changes between two site photos, engineering drawings, or static image PDFs.

The output is designed for civil engineers: changed regions are boxed, affected area is estimated, image evidence is saved, and a PDF report explains the result in inspection-friendly language.

## Features

- Upload JPG, JPEG, PNG, or PDF files.
- Render the first page of uploaded PDFs for comparison.
- Resize inputs to a common canvas.
- Apply feature-based alignment when the views are slightly shifted.
- Detect changed regions with OpenCV difference masks and noise filtering.
- Generate side-by-side, heatmap, binary mask, and highlighted-region outputs.
- Compute changed region count, affected percentage, changed pixels, confidence, and coordinates.
- Produce a downloadable civil engineering change report PDF.

## Project Structure

```text
backend/
  app/
    main.py                 FastAPI routes
    services/
      difference.py         Alignment, masking, regions, visualization
      image_io.py           Image/PDF upload validation and decoding
      report.py             User-friendly PDF report generation
      summary.py            Civil engineering summary text
frontend/
  src/
    main.jsx                React application
    styles.css              Responsive inspection UI
docs/
  requirements.md
  architecture.md
scripts/
  generate_samples.py
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

Open `http://127.0.0.1:5173`.

## Generate Sample Inputs

```bash
python scripts/generate_samples.py
```

This creates two construction-style drawing images in `samples/` that can be uploaded to the UI.

## API

### `POST /api/analyze`

Multipart form fields:

- `reference`: reference JPG, JPEG, PNG, or PDF
- `comparison`: comparison JPG, JPEG, PNG, or PDF

Returns:

- URLs for original, aligned comparison, side-by-side, heatmap, overlay, mask, and report PDF
- changed-region statistics
- region coordinates
- natural-language engineering summary

## References

The project brief requires awareness of these resources:

- https://arxiv.org/abs/2201.00625
- https://arxiv.org/pdf/2505.01530
- https://github.com/javvi51/eDOCr
- https://github.com/Bakkopi/engineering-drawing-extractor
- https://github.com/topics/cad-drawings

This implementation uses practical computer-vision techniques for a working prototype and keeps the architecture open for later model-based object recognition or drawing-element extraction.
