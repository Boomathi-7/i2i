import cv2
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

from app.models import AnalysisResponse


def classify_region_python(bbox: list[int], area: int) -> tuple[str, str]:
    x, y, w, h = bbox
    aspect = w / max(1, h)
    
    if (w > 100 and h < 20) or (h > 100 and w < 20):
        return "Possible Wall", "A possible wall line or partition outline appears different."
    if 0.35 <= aspect <= 0.65 and 40 <= h <= 100:
        return "Possible Door", "A door-like structure appears different between the revisions."
    if 0.75 <= aspect <= 1.35 and 25 <= w <= 75 and 25 <= h <= 75:
        return "Possible Window", "A window-like structure appears different between the revisions."
    if aspect < 0.22 and h > 60 and w < 18:
        return "Possible Column", "A possible column or structural support element seems modified."
    if y < 380 and aspect > 2.0 and h < 25:
        return "Possible Roof", "A roof line or top parapet outline appears different."
    if 1.2 <= aspect <= 2.8 and 20 <= h <= 60 and w >= 40:
        return "Possible Stair", "A stair or step-like structure seems modified."
    if area > 1200:
        return "Possible Structural Element", "A structural element in this location has changed."
    return "Line Detail", "A small line detail or annotation appears different in this area."


def build_pdf_report(response: AnalysisResponse, output_path: Path, image_paths: dict[str, Path]) -> None:
    styles = getSampleStyleSheet()
    
    # Text styles
    title_style = ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f766e"),
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        name="SectionHeader",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f3f3a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        name="Body",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334135"),
    )
    cell_style = ParagraphStyle(
        name="Cell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
    )
    cell_bold = ParagraphStyle(
        name="CellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    header_style = ParagraphStyle(
        name="HeaderCell",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    
    story = []
    
    # ----------------------------------------------------
    # PAGE 1: Revision Comparison Summary
    # ----------------------------------------------------
    story.append(Paragraph("Revision Comparison Summary", title_style))
    story.append(Spacer(1, 10))
    
    summary_text = (
        f"The comparison system examined the two engineering drawings and identified "
        f"{response.statistics.total_changes} possible modifications."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 15))
    
    # Overall metrics grid
    stats_data = [
        [
            Paragraph("Overall Similarity", cell_bold),
            Paragraph(f"{response.statistics.similarity:.0f}%", cell_style),
            Paragraph("Total Changes Found", cell_bold),
            Paragraph(str(response.statistics.total_changes), cell_style),
        ],
        [
            Paragraph("Processing Status", cell_bold),
            Paragraph("Completed Successfully", cell_style),
            Paragraph("Date of Report", cell_bold),
            Paragraph(str(Path(output_path).stat().st_mtime if output_path.exists() else "Today"), cell_style),
        ]
    ]
    stats_table = Table(stats_data, colWidths=[1.7 * inch, 1.7 * inch, 1.7 * inch, 2.07 * inch])
    stats_table.setStyle(_table_style(header=False))
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Reference and Comparison drawings side-by-side
    img_ref = _scaled_image(image_paths["image_a"], 3.3 * inch, 2.8 * inch)
    img_cmp = _scaled_image(image_paths["image_b"], 3.3 * inch, 2.8 * inch)
    drawings_table = Table([[img_ref, img_cmp]], colWidths=[3.5 * inch, 3.5 * inch])
    drawings_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(Paragraph("Compared Sheets (Revision A / Revision B)", h2_style))
    story.append(drawings_table)
    
    story.append(PageBreak())

    # ----------------------------------------------------
    # PAGE 2: Visual Overview
    # ----------------------------------------------------
    story.append(Paragraph("Visual Overview of Changes", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Below is the overview drawing highlighting all detected changes in yellow boxes.", body_style))
    story.append(Spacer(1, 15))
    
    # Highlighting drawing
    img_annotated = _scaled_image(image_paths["overlay"], 6.8 * inch, 4.5 * inch)
    story.append(img_annotated)
    
    story.append(PageBreak())

    # ----------------------------------------------------
    # PAGE 3: Change Summary
    # ----------------------------------------------------
    story.append(Paragraph("Change Summary Table", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("A quick-reference index of all modifications detected on the drawing sheet.", body_style))
    story.append(Spacer(1, 15))
    
    summary_table_data = [
        [
            Paragraph("Change", header_style),
            Paragraph("Location", header_style),
            Paragraph("Importance", header_style),
            Paragraph("Confidence", header_style)
        ]
    ]
    
    for r in response.regions:
        loc = "Upper Building" if r.bbox[1] < 500 else "Lower Building"
        imp = "High" if r.area > 1000 else "Medium" if r.area > 350 else "Low"
        conf = "High Confidence" if r.confidence >= 0.70 else "Medium Confidence" if r.confidence >= 0.40 else "Low Confidence"
        
        summary_table_data.append([
            Paragraph(f"Change {r.id}", cell_style),
            Paragraph(loc, cell_style),
            Paragraph(imp, cell_style),
            Paragraph(conf, cell_style)
        ])
        
    summary_table = Table(summary_table_data, colWidths=[1.3 * inch, 2.3 * inch, 1.5 * inch, 2.07 * inch])
    summary_table.setStyle(_table_style(header=True))
    story.append(summary_table)
    
    story.append(PageBreak())

    # ----------------------------------------------------
    # PAGE 4+: Individual Change Pages
    # ----------------------------------------------------
    crops_dir = output_path.parent / "crops"
    
    for r in response.regions:
        story.append(Paragraph(f"Change Detail: Change {r.id}", title_style))
        story.append(Spacer(1, 10))
        
        loc = "Upper Building" if r.bbox[1] < 500 else "Lower Building"
        imp = "High" if r.area > 1000 else "Medium" if r.area > 350 else "Low"
        conf = "High Confidence" if r.confidence >= 0.70 else "Medium Confidence" if r.confidence >= 0.40 else "Low Confidence"
        cls_type, cls_desc = classify_region_python(r.bbox, r.area)
        
        meta_data = [
            [
                Paragraph("Location", cell_bold), Paragraph(loc, cell_style),
                Paragraph("Type Classification", cell_bold), Paragraph(cls_type, cell_style),
            ],
            [
                Paragraph("Importance", cell_bold), Paragraph(imp, cell_style),
                Paragraph("Detection Confidence", cell_bold), Paragraph(conf, cell_style),
            ]
        ]
        meta_table = Table(meta_data, colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.07 * inch])
        meta_table.setStyle(_table_style(header=False))
        story.append(meta_table)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("Explanation of Change", h2_style))
        story.append(Paragraph(cls_desc, body_style))
        story.append(Spacer(1, 20))
        
        # Crops
        ref_path = crops_dir / f"R_{r.id}_ref.png"
        cmp_path = crops_dir / f"R_{r.id}_cmp.png"
        edge_path = crops_dir / f"R_{r.id}_edge.png"
        
        if ref_path.exists() and cmp_path.exists() and edge_path.exists():
            i_ref = Image(str(ref_path), width=2.1 * inch, height=1.6 * inch)
            i_cmp = Image(str(cmp_path), width=2.1 * inch, height=1.6 * inch)
            i_edge = Image(str(edge_path), width=2.1 * inch, height=1.6 * inch)
            
            crops_table = Table([[i_ref, i_cmp, i_edge]], colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch])
            crops_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(Paragraph("Visual Comparison Crops (Before / After / Highlighted Difference)", h2_style))
            story.append(crops_table)
            
        story.append(PageBreak())

    # ----------------------------------------------------
    # PAGE LAST: Executive Summary & Technical Details Appendix
    # ----------------------------------------------------
    story.append(Paragraph("Executive Summary", title_style))
    story.append(Spacer(1, 10))
    
    # Text notes count
    upper_count = sum(1 for r in response.regions if r.bbox[1] < 500)
    lower_count = len(response.regions) - upper_count
    conc_text = "upper building elevation" if upper_count >= lower_count else "lower building elevation"
    
    exec_summary = (
        f"The comparison identified {len(response.regions)} possible differences between the two drawing revisions. "
        f"Most of the changes are concentrated in the {conc_text}. "
        f"Several modifications appear to affect window, door, or wall-like structures. "
        f"A manual engineering review is recommended before final approval."
    )
    story.append(Paragraph(exec_summary, body_style))
    story.append(Spacer(1, 30))
    
    # Collapsible Technical Appendix
    story.append(Paragraph("Technical Details Appendix", h2_style))
    story.append(Paragraph("This section contains computer vision measurements and raw algorithm metadata.", cell_style))
    story.append(Spacer(1, 10))
    
    tech_data = [
        [
            Paragraph("Parameter", header_style),
            Paragraph("Measurement / Technical Information", header_style),
        ],
        [
            Paragraph("Similarity Score", cell_bold),
            Paragraph(f"{response.statistics.similarity:.4f} (SSIM metric proxy)", cell_style),
        ],
        [
            Paragraph("Processing Time", cell_bold),
            Paragraph(f"{response.statistics.processing_time:.2f} seconds", cell_style),
        ],
        [
            Paragraph("Alignment Method", cell_bold),
            Paragraph("Affine Similarity Feature alignment via AKAZE/ORB RANSAC", cell_style),
        ]
    ]
    
    # Add regions bounding boxes
    for r in response.regions:
        tech_data.append([
            Paragraph(f"Change {r.id} coordinates", cell_bold),
            Paragraph(f"Bounding Box: [x={r.bbox[0]}, y={r.bbox[1]}, w={r.bbox[2]}, h={r.bbox[3]}], Area={r.area} px, Centroid=({r.center[0]}, {r.center[1]}), Raw Confidence={r.confidence:.4f}", cell_style),
        ])
        
    tech_table = Table(tech_data, colWidths=[2.2 * inch, 4.87 * inch])
    tech_table.setStyle(_table_style(header=True))
    story.append(tech_table)

    doc.build(story)


def build_html_report(response: AnalysisResponse, output_path: Path, image_paths: dict[str, Path]) -> None:
    regions_html = ""
    for r in response.regions:
        cls_type, cls_desc = classify_region_python(r.bbox, r.area)
        loc = "Upper Building" if r.bbox[1] < 500 else "Lower Building"
        imp = "High" if r.area > 1000 else "Medium" if r.area > 350 else "Low"
        conf = "High Confidence" if r.confidence >= 0.70 else "Medium Confidence" if r.confidence >= 0.40 else "Low Confidence"
        
        regions_html += f"""
        <div style="border: 1px solid #ddd; border-radius: 6px; padding: 20px; margin-bottom: 25px; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h3 style="margin-top:0; color: #0f766e;">Change {r.id} - {cls_type}</h3>
            <p><strong>Location:</strong> {loc} | <strong>Importance:</strong> {imp} | <strong>Confidence:</strong> {conf}</p>
            <p style="background: #f9f9f9; padding: 10px; border-left: 4px solid #0f766e; font-size: 14px;">{cls_desc}</p>
            <div style="display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap;">
                <figure style="margin: 0; text-align: center;">
                    <img src="crops/R_{r.id}_ref.png" style="width: 200px; height: 150px; object-fit: contain; border: 1px solid #ccc; border-radius: 4px;"/>
                    <figcaption style="font-size: 11px; color: #555; margin-top: 5px;">Before (Rev A)</figcaption>
                </figure>
                <figure style="margin: 0; text-align: center;">
                    <img src="crops/R_{r.id}_cmp.png" style="width: 200px; height: 150px; object-fit: contain; border: 1px solid #ccc; border-radius: 4px;"/>
                    <figcaption style="font-size: 11px; color: #555; margin-top: 5px;">After (Rev B)</figcaption>
                </figure>
                <figure style="margin: 0; text-align: center;">
                    <img src="crops/R_{r.id}_edge.png" style="width: 200px; height: 150px; object-fit: contain; border: 1px solid #ccc; border-radius: 4px;"/>
                    <figcaption style="font-size: 11px; color: #555; margin-top: 5px;">Difference</figcaption>
                </figure>
            </div>
            
            <details style="margin-top: 15px; font-size: 12px; color: #666; cursor: pointer;">
                <summary>Technical Details</summary>
                <div style="padding: 10px; background: #fafafa; border-radius: 4px; margin-top: 5px;">
                    Bounding Box: [x={r.bbox[0]}, y={r.bbox[1]}, w={r.bbox[2]}, h={r.bbox[3]}] | Centroid: ({r.center[0]}, {r.center[1]}) | Area: {r.area} px | Raw Confidence: {r.confidence:.4f}
                </div>
            </details>
        </div>
        """
        
    # Stats counts
    upper_count = sum(1 for r in response.regions if r.bbox[1] < 500)
    lower_count = len(response.regions) - upper_count
    conc_text = "upper building elevation" if upper_count >= lower_count else "lower building elevation"
    
    import datetime
    report_date = datetime.date.today().strftime("%m/%d/%Y")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Engineering Drawing Comparison Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.5; color: #333; margin: 40px; background-color: #f5f7f6; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); }}
            h1 {{ color: #0f766e; border-bottom: 2px solid #0f766e; padding-bottom: 10px; margin-top: 0; }}
            h2 {{ color: #0f3f3a; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 40px; }}
            .hero-card {{ background: #eff6ff; border-left: 6px solid #1d4ed8; padding: 20px; border-radius: 4px; margin-bottom: 30px; }}
            .visual-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-top: 20px; }}
            .visual-item {{ border: 1px solid #ddd; border-radius: 6px; padding: 15px; text-align: center; background: #fafafa; }}
            .visual-item img {{ max-width: 100%; height: 260px; object-fit: contain; }}
            .stats-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            .stats-table th, .stats-table td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            .stats-table th {{ background-color: #0f766e; color: white; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Engineering Drawing Comparison Report</h1>
            <p style="color: #666; font-size: 14px;">Report generated on {report_date}</p>
            
            <div class="hero-card">
                <h3 style="margin-top:0; color: #1e40af;">Revision Summary</h3>
                <p>The system compared the two drawing sheets and detected <strong>{len(response.regions)} possible modifications</strong>.</p>
                <p>Overall drawing similarity score is <strong>{response.statistics.similarity:.0f}%</strong>.</p>
            </div>
            
            <h2>Visual Overview</h2>
            <div class="visual-grid">
                <figure class="visual-item">
                    <img src="changed_regions.png"/>
                    <figcaption><strong>Highlighted Differences</strong></figcaption>
                </figure>
                <figure class="visual-item">
                    <img src="heatmap.png"/>
                    <figcaption><strong>Difference Heatmap</strong></figcaption>
                </figure>
            </div>
            
            <h2>Change Summary Index</h2>
            <table class="stats-table">
                <thead>
                    <tr>
                        <th>Change</th><th>Location</th><th>Importance</th><th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td>Change {r.id}</td><td>{'Upper Building' if r.bbox[1] < 500 else 'Lower Building'}</td><td>{'High' if r.area > 1000 else 'Medium' if r.area > 350 else 'Low'}</td><td>{'High' if r.confidence >= 0.70 else 'Medium' if r.confidence >= 0.40 else 'Low'}</td></tr>" for r in response.regions)}
                </tbody>
            </table>
            
            <h2>Detailed Change Analysis</h2>
            {regions_html}
            
            <h2>Executive Conclusion</h2>
            <div style="background: #fafbfb; border: 1px solid #ddd; border-radius: 4px; padding: 20px; margin-top: 30px;">
                <p>The comparison identified {len(response.regions)} possible differences between the two revisions. 
                Most of the changes are concentrated in the {conc_text}. 
                Several changes appear to affect window and wall-like structures. 
                A manual engineering review is recommended before final approval.</p>
            </div>
            
            <h2 style="margin-top: 50px;">Technical Index Appendix</h2>
            <details style="cursor: pointer; background: #fdfdfd; padding: 15px; border: 1px solid #eee; border-radius: 4px;">
                <summary>Click to view system metrics & parameters</summary>
                <div style="margin-top: 15px;">
                    <p><strong>Similarity Metric (SSIM proxy):</strong> {response.statistics.similarity:.4f}</p>
                    <p><strong>Total Processing Duration:</strong> {response.statistics.processing_time:.2f} seconds</p>
                    <p><strong>Alignment Method:</strong> Affine Partial ransac estimation (inliers matched inside Drawing ROI views only)</p>
                </div>
            </details>
        </div>
    </body>
    </html>
    """
    
    with open(str(output_path), "w", encoding="utf-8") as f:
        f.write(html_content)


def _paragraph_rows(rows: list[list[str]], body_style: ParagraphStyle, header_style: ParagraphStyle | None = None) -> list[list[Paragraph]]:
    formatted = []
    for row_index, row in enumerate(rows):
        style = header_style if row_index == 0 and header_style else body_style
        formatted.append([Paragraph(str(cell), style) for cell in row])
    return formatted


def _scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    scale = min(max_width / image.drawWidth, max_height / image.drawHeight)
    image.drawWidth *= scale
    image.drawHeight *= scale
    image.hAlign = "CENTER"
    return image


def _table_style(header: bool = False) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    return TableStyle(commands)


