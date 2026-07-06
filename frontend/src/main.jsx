import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";
import logoImage from "./logo.png";
import { 
  AlertTriangle, 
  CheckCircle2, 
  Download, 
  FileImage, 
  Loader2, 
  UploadCloud, 
  ZoomIn, 
  Building,
  Info,
  ChevronDown,
  ChevronUp
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

// Simple non-technical descriptions for change classifications
function getSimpleExplanation(region) {
  const [x, y, w, h] = region.bbox;
  const aspect = w / max(1, h);
  const area = region.area;

  if ((w > 100 && h < 20) || (h > 100 && w < 20)) {
    return {
      type: "Possible Wall",
      desc: "A wall-like line or partition outline appears different."
    };
  }
  if (aspect >= 0.35 && aspect <= 0.65 && h >= 40 && h <= 100) {
    return {
      type: "Possible Door",
      desc: "A door-like structure seems modified or shifted."
    };
  }
  if (aspect >= 0.75 && aspect <= 1.35 && w >= 25 && w <= 75 && h >= 25 && h <= 75) {
    return {
      type: "Possible Window",
      desc: "A window-like structure appears different between the two revisions."
    };
  }
  if (aspect < 0.22 && h > 60 && w < 18) {
    return {
      type: "Possible Column",
      desc: "A support column or vertical post element seems modified."
    };
  }
  if (y < 380 && aspect > 2.0 && h < 25) {
    return {
      type: "Possible Roof",
      desc: "A roof line profile or top parapet outline appears different."
    };
  }
  if (aspect >= 1.2 && aspect <= 2.8 && h >= 20 && h <= 60 && w >= 40) {
    return {
      type: "Possible Stair",
      desc: "A stair outline or step-like segment seems modified."
    };
  }
  if (area > 1200) {
    return {
      type: "Possible Structural Element",
      desc: "A structural element in this location has changed."
    };
  }
  return {
    type: "Line Detail",
    desc: "A visible modification was detected in this area."
  };
}

function max(a, b) {
  return a > b ? a : b;
}

function getSimpleLocation(region) {
  const [x, y, w, h] = region.bbox;
  if (y < 380) return "Roof Area";
  if (y >= 380 && y < 580) return "Upper Building";
  return "Lower Building";
}

function getImportanceLabel(area) {
  if (area > 1000) return "High";
  if (area > 350) return "Medium";
  return "Low";
}

function getConfidenceLabel(conf) {
  if (conf >= 0.7) return "High";
  if (conf >= 0.4) return "Medium";
  return "Low";
}

function App() {
  const [reference, setReference] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const canAnalyze = reference && comparison && !loading;

  async function analyze() {
    if (!canAnalyze) return;
    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("reference", reference);
    formData.append("comparison", comparison);

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Analysis failed.");
      }
      setResult(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
            <img 
              src={logoImage} 
              alt="Logo" 
              style={{ width: "56px", height: "56px", objectFit: "cover", borderRadius: "14px", border: "2px solid #ebf0ec", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }} 
            />
            <div>
              <h1>i2i - comparisons</h1>
              <p className="eyebrow" style={{ marginTop: "12px" }}>AI-Based image difference detection , visualization, and automated change summarization </p>
            </div>
          </div>
          {result && (
            <div className="download-group">
              <a className="icon-action" href={absoluteUrl(result.outputs.report_pdf)} onClick={(e) => { e.preventDefault(); handleDownload(absoluteUrl(result.outputs.report_pdf), 'comparison_report.pdf'); }} title="Download PDF Report">
                <Download size={18} />
                PDF Report
              </a>
              <a className="icon-action" href={absoluteUrl(result.outputs.report_html)} onClick={(e) => { e.preventDefault(); handleDownload(absoluteUrl(result.outputs.report_html), 'comparison_report.html'); }} title="Download HTML Report">
                <Download size={18} />
                HTML Report
              </a>
            </div>
          )}
        </header>

        <section className="upload-grid">
          <Uploader label="Original" file={reference} onChange={setReference} />
          <Uploader label="Updated" file={comparison} onChange={setComparison} />
        </section>

        <div className="run-row">
          <button className="primary-button" onClick={analyze} disabled={!canAnalyze}>
            {loading ? <Loader2 className="spin" size={18} /> : <UploadCloud size={18} />}
            Generate comparison report
          </button>
          {error && (
            <p className="status error">
              <AlertTriangle size={16} />
              {error}
            </p>
          )}
          {result && (
            <p className="status success">
              <CheckCircle2 size={16} />
              Report generated successfully
            </p>
          )}
        </div>

        {loading ? <LoadingState /> : result ? <ReportView result={result} /> : <EmptyState />}
      </section>
    </main>
  );
}

function Uploader({ label, file, onChange }) {
  const accept = ".jpg,.jpeg,.png,.pdf";
  return (
    <label className="upload-panel">
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] || null)}
      />
      <FileImage size={26} />
      <span>{label}</span>
      <strong>{file ? file.name : "Select drawing file (PDF or Image)"}</strong>
    </label>
  );
}

function ReportView({ result }) {
  const [activeTab, setActiveTab] = useState("summary");
  const [zoomImage, setZoomImage] = useState(null);
  const [showTech, setShowTech] = useState(false);

  // Derive counts & locations
  const totalChanges = result.regions.length;
  
  const mappedRegions = useMemo(() => {
    return result.regions.map(r => ({
      ...r,
      simpleLoc: getSimpleLocation(r),
      importance: getImportanceLabel(r.area),
      simpleConf: getConfidenceLabel(r.confidence),
      explanation: getSimpleExplanation(r)
    }));
  }, [result.regions]);

  const upperCount = useMemo(() => {
    return result.regions.filter(r => r.bbox[1] < 500).length;
  }, [result.regions]);
  const lowerCount = totalChanges - upperCount;
  const concentratedText = upperCount >= lowerCount ? "upper building elevation" : "lower building elevation";

  return (
    <section className="results">
      {/* Visual Navigation Tabs (coincides with Pages 1 to Last) */}
      <div className="tab-navigation report-stepper-tabs">
        <button 
          className={activeTab === "summary" ? "tab-button active" : "tab-button"}
          onClick={() => setActiveTab("summary")}
        >
          1. Summary
        </button>
        <button 
          className={activeTab === "overview" ? "tab-button active" : "tab-button"}
          onClick={() => setActiveTab("overview")}
        >
          2. Visual Overview
        </button>
        <button 
          className={activeTab === "register" ? "tab-button active" : "tab-button"}
          onClick={() => setActiveTab("register")}
        >
          3. Change Table
        </button>
        <button 
          className={activeTab === "cards" ? "tab-button active" : "tab-button"}
          onClick={() => setActiveTab("cards")}
        >
          4. Individual Changes
        </button>
        <button 
          className={activeTab === "conclusion" ? "tab-button active" : "tab-button"}
          onClick={() => setActiveTab("conclusion")}
        >
          5. Conclusion
        </button>
      </div>

      {/* Tab Panels */}
      <div className="tab-content report-sheets-content">
        {/* PAGE 1: Revision Comparison Summary */}
        {activeTab === "summary" && (
          <div className="report-page-card">
            <h2>Revision Comparison Summary</h2>
            <p className="summary-banner-text">
              The system compared the two engineering drawings and identified <strong>{totalChanges} possible modifications</strong>.
            </p>
            
            <div className="executive-grid">
              <div className="exec-item">
                <span>Overall Similarity:</span>
                <strong>{result.statistics.similarity.toFixed(0)}%</strong>
              </div>
              <div className="exec-item">
                <span>Total Changes:</span>
                <strong>{totalChanges}</strong>
              </div>
              <div className="exec-item">
                <span>Processing Status:</span>
                <strong style={{ color: "#15803d" }}>Completed Successfully</strong>
              </div>
            </div>

            <div className="visual-grid double-column-visuals" style={{ marginTop: "24px" }}>
              <Visual title="Original Drawing (Revision A)" src={result.outputs.reference_image} onZoom={setZoomImage} />
              <Visual title="Updated Drawing (Revision B)" src={result.outputs.aligned_image} onZoom={setZoomImage} />
            </div>
          </div>
        )}

        {/* PAGE 2: Visual Overview */}
        {activeTab === "overview" && (
          <div className="report-page-card">
            <h2>Visual Overview of Changes</h2>
            <p className="description-text">
              Below is the updated drawing showing the location of all detected changes highlighted inside yellow review boxes.
            </p>
            <div className="visual-grid single-column-visual" style={{ marginTop: "16px" }}>
              <Visual title="Drawing Highlighting All Changes" src={result.outputs.annotated_image} onZoom={setZoomImage} wide />
            </div>
          </div>
        )}

        {/* PAGE 3: Change Summary Table */}
        {activeTab === "register" && (
          <div className="report-page-card">
            <h2>Summary of Detected Changes</h2>
            <p className="description-text">
              A plain-language directory of all changed regions on the drawing sheet.
            </p>
            {mappedRegions.length ? (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Change</th>
                      <th>Location</th>
                      <th>Importance</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mappedRegions.map((r) => (
                      <tr key={r.id}>
                        <td><strong>Change {r.id}</strong></td>
                        <td>{r.simpleLoc}</td>
                        <td>
                          <span className={`severity-tag ${r.importance.toLowerCase() === "high" ? "major" : r.importance.toLowerCase() === "medium" ? "moderate" : "minor"}`}>
                            {r.importance}
                          </span>
                        </td>
                        <td>
                          <span className={`severity-tag ${r.simpleConf === "High" ? "minor" : r.simpleConf === "Medium" ? "moderate" : "major"}`}>
                            {r.simpleConf} Confidence
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">No changes detected between revisions.</p>
            )}
          </div>
        )}

        {/* PAGE 4+: Individual Change Cards */}
        {activeTab === "cards" && (
          <div className="report-page-card list-view-card">
            <h2>Individual Change Analysis</h2>
            <p className="description-text">
              Detailed before/after view crops and explanations for each detected modification.
            </p>
            <div className="change-cards-layout">
              {mappedRegions.map((r) => (
                <div className="change-card shadow-accent" key={r.id}>
                  {/* Card Title Header */}
                  <div className="card-header-bar flex-header">
                    <div className="id-group">
                      <span className="id-badge font-accent">Change {r.id}</span>
                      <span className="type-badge-large">{r.explanation.type}</span>
                    </div>
                    <div className="badge-group">
                      <span className={`severity-tag ${r.importance.toLowerCase() === "high" ? "major" : r.importance.toLowerCase() === "medium" ? "moderate" : "minor"}`}>
                        {r.importance} Importance
                      </span>
                      <span className="conf-tag">
                        {r.simpleConf} Confidence
                      </span>
                    </div>
                  </div>

                  {/* Simple Plain Description */}
                  <p className="explanation-bubble text-bubble">
                    {r.explanation.desc}
                  </p>

                  {/* Crop Assets */}
                  <div className="crops-grid report-crops shadow-box">
                    <figure className="crop-item" onClick={() => setZoomImage(r.images.before)}>
                      <img src={absoluteUrl(r.images.before)} alt="Before Crop" />
                      <figcaption>Before (Rev A)</figcaption>
                    </figure>
                    <figure className="crop-item" onClick={() => setZoomImage(r.images.after)}>
                      <img src={absoluteUrl(r.images.after)} alt="After Crop" />
                      <figcaption>After (Rev B)</figcaption>
                    </figure>
                    <figure className="crop-item" onClick={() => setZoomImage(r.images.mask)}>
                      <img src={absoluteUrl(r.images.mask)} alt="Difference Mask" />
                      <figcaption>Highlighted Difference</figcaption>
                    </figure>
                  </div>
                  
                  <div className="card-metrics" style={{ padding: "10px 14px", marginTop: "10px", fontSize: "0.85rem", background: "#f8fafc", borderRadius: "6px" }}>
                    <p style={{ margin: 0 }}><strong>General Location:</strong> {r.simpleLoc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PAGE LAST: Executive Summary */}
        {activeTab === "conclusion" && (
          <div className="report-page-card">
            <h2>Executive Review Conclusion</h2>
            <div className="conclusion-block">
              <p className="summary-paragraph">
                The comparison identified {totalChanges} possible differences between the two revisions.
                Most of the changes are concentrated in the {concentratedText}.
                Several changes appear to affect window and wall-like structures.
                A manual engineering review is recommended before final approval.
              </p>
            </div>
            
            <div className="drawing-signature-block">
              <div className="sign-line">
                <span className="label">Prepared By:</span>
                <span className="value">Automated Revision Review System</span>
              </div>
              <div className="sign-line">
                <span className="label">Review Status:</span>
                <span className="value status-pending">Awaiting Manual Verification</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Advanced Technical Details Collapsible Accordion (Hidden by default) */}
      <section className="technical-details-section">
        <button 
          className="tech-details-toggle"
          onClick={() => setShowTech(!showTech)}
        >
          <div className="toggle-label">
            <Info size={18} />
            <span>Advanced Technical Details</span>
          </div>
          {showTech ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {showTech && (
          <div className="tech-details-panel">
            <div className="details-metrics">
              <p><strong>Similarity Score:</strong> {result.statistics.similarity.toFixed(4)} (SSIM metric proxy)</p>
              <p><strong>Total Processing Duration:</strong> {result.statistics.processing_time} seconds</p>
              <p><strong>Alignment Method:</strong> Affine Partial ransac estimation (Drawing ROI masked inliers)</p>
            </div>

            <h3 style={{ marginTop: "16px", marginBottom: "8px", fontSize: "0.9rem", textTransform: "uppercase" }}>Raw Coordinates & Bounding Boxes</h3>
            <table className="tech-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Pixel Coordinates [x, y, w, h]</th>
                  <th>Centroid (cx, cy)</th>
                  <th>Raw Area</th>
                  <th>Confidence Metric</th>
                </tr>
              </thead>
              <tbody>
                {result.regions.map(r => (
                  <tr key={r.id}>
                    <td>R{r.id}</td>
                    <td>[{r.bbox.join(", ")}]</td>
                    <td>({r.center[0]}, {r.center[1]})</td>
                    <td>{r.area} px</td>
                    <td>{r.confidence.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Lightbox zoom modal */}
      {zoomImage && (
        <div className="lightbox-overlay" onClick={() => setZoomImage(null)}>
          <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
            <img src={absoluteUrl(zoomImage)} alt="Zoomed Review" />
            <button className="lightbox-close" onClick={() => setZoomImage(null)}>×</button>
          </div>
        </div>
      )}
    </section>
  );
}

function Visual({ title, src, wide = false, onZoom }) {
  return (
    <figure className={wide ? "visual wide" : "visual"}>
      <div className="visual-wrapper">
        <img src={absoluteUrl(src)} alt={title} />
        <button className="zoom-btn" onClick={() => onZoom(src)}>
          <ZoomIn size={16} />
          Zoom Review
        </button>
      </div>
      <figcaption>{title}</figcaption>
    </figure>
  );
}

function EmptyState() {
  return (
    <section className="empty-state center-content">
      <div className="lottie-container">
        <DotLottieReact
          src="/animation.json"
          loop
          autoplay
        />
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <section className="empty-state center-content">
      <div className="lottie-container">
        <DotLottieReact
          src="/loading.json"
          loop
          autoplay
        />
      </div>
    </section>
  );
}

function absoluteUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

async function handleDownload(url, filename) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Network response was not ok");
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  } catch (e) {
    console.error("Failed to download file:", e);
    window.open(url, "_blank");
  }
}

createRoot(document.getElementById("root")).render(<App />);
