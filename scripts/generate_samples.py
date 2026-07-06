from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    base = Image.new("RGB", (1000, 650), "#f8fafc")
    draw = ImageDraw.Draw(base)
    _draw_site_plan(draw)
    base.save(SAMPLES / "reference_site_plan.png")

    changed = base.copy()
    draw_changed = ImageDraw.Draw(changed)
    draw_changed.rectangle((700, 410, 875, 535), outline="#dc2626", width=8)
    draw_changed.rectangle((720, 430, 850, 510), fill="#fee2e2", outline="#991b1b", width=3)
    draw_changed.text((732, 457), "New\nslab", fill="#991b1b")
    draw_changed.line((190, 125, 390, 125), fill="#f8fafc", width=12)
    draw_changed.line((190, 125, 390, 125), fill="#f97316", width=5)
    draw_changed.ellipse((485, 280, 555, 350), fill="#fef08a", outline="#ca8a04", width=4)
    changed.save(SAMPLES / "comparison_site_plan.png")


def _draw_site_plan(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((40, 40, 960, 610), outline="#0f172a", width=4)
    draw.text((58, 56), "Sample construction inspection plan", fill="#0f172a")
    draw.rectangle((145, 120, 420, 305), outline="#2563eb", width=5)
    draw.text((220, 195), "Block A", fill="#1e3a8a")
    draw.rectangle((560, 110, 850, 300), outline="#16a34a", width=5)
    draw.text((650, 190), "Block B", fill="#166534")
    draw.rectangle((150, 405, 430, 540), outline="#64748b", width=5)
    draw.text((245, 465), "Yard", fill="#334155")
    draw.line((100, 355, 900, 355), fill="#475569", width=10)
    draw.text((430, 370), "Access road", fill="#334155")
    for x in range(150, 850, 100):
        draw.line((x, 90, x, 575), fill="#e2e8f0", width=1)
    for y in range(105, 575, 85):
        draw.line((100, y, 900, y), fill="#e2e8f0", width=1)


if __name__ == "__main__":
    main()
