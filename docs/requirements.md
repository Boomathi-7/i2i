# Requirements Document

## Objective

Build an AI-assisted image comparison system that accepts two images or image PDFs, detects visual differences, localizes changed regions, generates visual evidence, computes statistics, and produces a clear summary for civil engineers.

## Users

- Site engineers comparing progress photos.
- Civil engineers reviewing before/after field evidence.
- QA/QC teams comparing drawings, marked-up plans, or inspection imagery.
- Project managers who need a readable report without manually inspecting every pixel.

## Functional Requirements

| ID | Requirement | Implementation |
| --- | --- | --- |
| FR-1 | Upload two JPG, JPEG, PNG, or PDF files | React upload panels and FastAPI multipart endpoint |
| FR-2 | Validate files | Backend extension, empty-file, and size validation |
| FR-3 | Preprocess images | PDF rendering, EXIF correction, resizing, grayscale normalization |
| FR-4 | Align slightly shifted images | ORB feature matching with affine transform when possible |
| FR-5 | Detect differences | OpenCV absolute difference, Otsu thresholding, morphology, contour filtering |
| FR-6 | Detect changed regions | Bounding boxes generated from filtered contours |
| FR-7 | Visualize differences | Side-by-side image, heatmap, binary mask, and overlay with region labels |
| FR-8 | Compute statistics | Region count, changed percentage, changed pixels, total pixels, confidence |
| FR-9 | Generate summary | Civil-engineering-oriented summary with location, severity, confidence, and action guidance |
| FR-10 | Generate report | Downloadable PDF report with evidence, stats, and region register |

## Non-Functional Requirements

- Backend must use FastAPI.
- UI must not use Streamlit; React is used.
- Report must be readable for non-software users.
- Outputs must be stable URLs for frontend rendering and PDF download.
- The codebase should be simple enough for academic demonstration and future extension.

## Accepted Inputs

- Reference image or PDF
- Comparison image or PDF

## Outputs

- Reference preview
- Aligned comparison preview
- Side-by-side comparison
- Difference heatmap
- Highlighted changed regions
- Binary difference mask
- Difference statistics
- AI-generated summary paragraph
- PDF inspection report

## Current Limitations

- PDF support renders the first page only.
- The summary is rule-based and grounded in detected regions; it can be upgraded with a vision-language model later.
- Object names such as "vehicle" or "column" are not inferred yet; the system reports location and severity reliably without pretending to classify unknown objects.
- Large viewpoint changes may require manual review or more advanced registration.
