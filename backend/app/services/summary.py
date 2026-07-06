from app.services.difference import Region


def build_engineering_summary(regions: list[Region], changed_percentage: float, alignment_status: str, confidence: str) -> str:
    if not regions:
        return (
            "The comparison did not identify significant visual changes after alignment and noise filtering. "
            "For civil inspection use, the images can be treated as visually consistent, with only minor pixel-level variation."
        )

    major_locations = ", ".join(region.location for region in regions[:4])
    severity = _overall_severity(changed_percentage, regions)
    region_word = "region" if len(regions) == 1 else "regions"
    return (
        f"The inspection identified {len(regions)} changed {region_word}, affecting approximately "
        f"{changed_percentage:.2f}% of the submitted view. The most relevant changes are concentrated around "
        f"the {major_locations} portion of the image. Overall change severity is {severity}, which suggests "
        f"{_civil_action(severity)} Confidence: {confidence}. Alignment note: {alignment_status}"
    )


def _overall_severity(changed_percentage: float, regions: list[Region]) -> str:
    if changed_percentage >= 12 or any(region.severity == "major" for region in regions):
        return "major"
    if changed_percentage >= 3 or any(region.severity == "moderate" for region in regions):
        return "moderate"
    return "minor"


def _civil_action(severity: str) -> str:
    if severity == "major":
        return "the area should be reviewed against site records, drawings, or progress photos before approval."
    if severity == "moderate":
        return "an engineer should verify whether the variation is expected construction progress or an exception."
    return "the change is likely localized, but it should still be checked if it falls in a structural or safety-critical zone."
