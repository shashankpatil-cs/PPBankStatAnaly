import React, { useState, useEffect } from "react";
import { uploadStatement, getAiStatus } from "../api.js";

export default function UploadPDF() {
  const [file, setFile] = useState(null);
  const [pdfPassword, setPdfPassword] = useState("");
  const [useAi, setUseAi] = useState(true);
  const [aiStatus, setAiStatus] = useState({ available: false, model: "" });
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    getAiStatus()
      .then((res) => {
        setAiStatus({
          available: res.data?.ai_available || false,
          model: res.data?.model || "",
        });
        if (res.data?.ai_available) {
          setUseAi(true);
        }
      })
      .catch(() => {
        setAiStatus({ available: false, model: "" });
      });
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setError("");
    setResult(null);
    setUploading(true);
    try {
      const res = await uploadStatement(file, pdfPassword, useAi, (evt) => {
        if (evt.total) {
          setProgress(Math.round((evt.loaded * 100) / evt.total));
        }
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload and parsing failed. Please check the PDF format.");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.toLowerCase().endsWith(".pdf")) {
        setFile(droppedFile);
        setError("");
      } else {
        setError("Please upload a valid PDF statement file.");
      }
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2>Upload Statement</h2>
      </div>

      <p className="muted" style={{ marginBottom: 20 }}>
        Export your transaction statement PDF from the PhonePe or banking app and upload it here.
        Transactions are automatically extracted, categorized, and added to your personal analytics.
      </p>


      {/* Upload Dropzone */}
      <div
        className={`upload-dropzone ${dragOver ? "drag-over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          background: dragOver ? "rgba(139, 92, 246, 0.15)" : undefined,
          borderColor: dragOver ? "var(--purple)" : undefined,
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 8 }}>📄</div>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>
          {file ? file.name : "Drag & drop your PhonePe statement PDF here"}
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4, marginBottom: 14 }}>
          {file ? `${(file.size / 1024).toFixed(1)} KB selected` : "or click browse to select a file from your computer"}
        </div>

        <input
          id="pdf-file-input"
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
          style={{ display: "none" }}
        />
        <label
          htmlFor="pdf-file-input"
          className="btn secondary"
          style={{ cursor: "pointer", display: "inline-block", padding: "8px 18px", fontSize: 13 }}
        >
          {file ? "Change File" : "Browse PDF"}
        </label>

        <div style={{ marginTop: 20 }}>
          <input
            type="password"
            placeholder="Statement password (if PDF is password-protected)"
            value={pdfPassword}
            onChange={(e) => setPdfPassword(e.target.value)}
            style={{ width: 340, maxWidth: "100%", padding: "9px 14px", fontSize: 13 }}
          />
        </div>

        <div style={{ marginTop: 18 }}>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            style={{
              padding: "10px 24px",
              fontSize: 14,
              fontWeight: 600,
              minWidth: 180,
              boxShadow: "0 2px 8px rgba(95,37,159,0.25)",
            }}
          >
            {uploading ? `Processing... ${progress > 0 ? progress + "%" : ""}` : "Extract Statement"}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-text" style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
          ⚠️ {error}
        </div>
      )}

      {result && (
        <div
          className="card"
          style={{
            marginTop: 24,
            borderLeft: "4px solid var(--green)",
            background: "rgba(16, 185, 129, 0.05)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: "0 0 6px 0", color: "#166534" }}>✓ Extraction Complete</h3>
              <p style={{ margin: "0 0 12px 0", fontSize: 14 }}>
                Successfully extracted <strong>{result.transactions_extracted}</strong> transactions from{" "}
                <strong>{result.filename}</strong>.
              </p>
            </div>
          </div>

          {result.transactions_failed_to_parse > 0 && (
            <p className="error-text" style={{ fontSize: 13, marginTop: 4 }}>
              Notice: {result.transactions_failed_to_parse} unparsable blocks in the PDF were safely skipped.
            </p>
          )}

          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <a className="btn" href="/transactions" style={{ textDecoration: "none", display: "inline-block" }}>
              View Transactions →
            </a>
            <a className="btn secondary" href="/" style={{ textDecoration: "none", display: "inline-block" }}>
              Go to Dashboard
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
