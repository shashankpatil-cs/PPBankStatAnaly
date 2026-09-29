import React, { useState, useEffect, useContext } from "react";
import { uploadStatement, getAiStatus } from "../api.js";
import { ActiveStatementContext } from "../context.js";

export default function UploadPDF() {
  const { setActiveStatementId, triggerRefresh } = useContext(ActiveStatementContext);
  const [file, setFile] = useState(null);
  const [statementName, setStatementName] = useState("");
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

  const isNameEmpty = !statementName.trim();
  const isLocked = !file || isNameEmpty;
  const canExtract = !isLocked && !uploading;

  const handleFileChange = (selectedFile) => {
    if (selectedFile) {
      if (selectedFile.name.toLowerCase().endsWith(".pdf")) {
        setFile(selectedFile);
        setStatementName(""); // PDF must be named before Extract Statement button is unlocked
        setError("");
        setResult(null);
      } else {
        setError("Please upload a valid PDF statement file.");
      }
    }
  };

  const handleUpload = async () => {
    if (!file || isNameEmpty) return;
    setError("");
    setResult(null);
    setUploading(true);
    try {
      const res = await uploadStatement(
        file,
        pdfPassword,
        useAi,
        (evt) => {
          if (evt.total) {
            setProgress(Math.round((evt.loaded * 100) / evt.total));
          }
        },
        statementName.trim()
      );
      setResult(res.data);
      setActiveStatementId(res.data.statement_id);
      triggerRefresh();
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
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleReset = () => {
    setFile(null);
    setStatementName("");
    setPdfPassword("");
    setResult(null);
    setError("");
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
        <div style={{ fontSize: 38, marginBottom: 8 }}>📄</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
          {file ? file.name : "Drag & drop your PhonePe statement PDF here"}
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4, marginBottom: 14 }}>
          {file ? `${(file.size / 1024).toFixed(1)} KB selected` : "or click browse to select a file from your computer"}
        </div>

        <input
          id="pdf-file-input"
          type="file"
          accept="application/pdf"
          onClick={(e) => { e.target.value = null; }}
          onChange={(e) => handleFileChange(e.target.files?.[0])}
          style={{ display: "none" }}
        />
        <label
          htmlFor="pdf-file-input"
          className="btn secondary"
          style={{ cursor: "pointer", display: "inline-block", padding: "8px 18px", fontSize: 13 }}
        >
          {file ? "Change PDF" : "Browse PDF"}
        </label>

        {/* Statement Configuration Card - displayed once PDF is uploaded/selected */}
        {file && (
          <div
            style={{
              marginTop: 24,
              padding: "20px 24px",
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid var(--border)",
              borderRadius: "14px",
              textAlign: "left",
              maxWidth: 460,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            {/* Statement Name Input (Required before unlocking extraction) */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <label
                  htmlFor="statement-name-input"
                  style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", display: "flex", alignItems: "center", gap: 6 }}
                >
                  Statement Name <span style={{ color: "var(--red)" }}>*</span>
                </label>
                <button
                  type="button"
                  onClick={() => setStatementName(file.name.replace(/\.pdf$/i, ""))}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--purple)",
                    fontSize: 12,
                    padding: 0,
                    textDecoration: "underline",
                    cursor: "pointer",
                    boxShadow: "none",
                  }}
                  title="Use original file name without .pdf extension"
                >
                  Use file name
                </button>
              </div>

              <input
                id="statement-name-input"
                type="text"
                placeholder="e.g., PhonePe March 2024 or Personal Account"
                value={statementName}
                onChange={(e) => setStatementName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canExtract) {
                    handleUpload();
                  }
                }}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  fontSize: 14,
                  borderRadius: "8px",
                  border: isNameEmpty ? "1px solid rgba(239, 68, 68, 0.5)" : "1px solid rgba(16, 185, 129, 0.5)",
                }}
                autoFocus
              />

              <div style={{ marginTop: 6, fontSize: 12 }}>
                {isNameEmpty ? (
                  <span style={{ color: "#f87171", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    🔒 Please name this PDF statement to unlock extraction.
                  </span>
                ) : (
                  <span style={{ color: "var(--green)", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    ✓ Named: Ready to extract!
                  </span>
                )}
              </div>
            </div>

            {/* Statement Password (Optional) */}
            <div>
              <label
                htmlFor="pdf-password-input"
                style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-muted)", marginBottom: 6 }}
              >
                Statement Password <span style={{ fontSize: 11, fontWeight: "normal" }}>(Optional)</span>
              </label>
              <input
                id="pdf-password-input"
                type="password"
                placeholder="Password (if PDF is password-protected)"
                value={pdfPassword}
                onChange={(e) => setPdfPassword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canExtract) {
                    handleUpload();
                  }
                }}
                style={{ width: "100%", padding: "9px 14px", fontSize: 13, borderRadius: "8px" }}
              />
            </div>
          </div>
        )}

        {/* Extract Statement Action */}
        <div style={{ marginTop: 22 }}>
          <button
            id="extract-statement-button"
            onClick={handleUpload}
            disabled={!canExtract}
            title={
              !file
                ? "Please upload a PDF first"
                : isNameEmpty
                ? "Please name the PDF statement to unlock extraction"
                : "Extract statement transactions"
            }
            style={{
              padding: "12px 28px",
              fontSize: 14,
              fontWeight: 600,
              minWidth: 200,
              boxShadow: canExtract ? "0 4px 15px rgba(139, 92, 246, 0.35)" : "none",
            }}
          >
            {uploading ? (
              `Processing... ${progress > 0 ? progress + "%" : ""}`
            ) : !file ? (
              "Extract Statement"
            ) : isNameEmpty ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                🔒 Name PDF to Unlock
              </span>
            ) : (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                ⚡ Extract Statement
              </span>
            )}
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

          <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <a className="btn" href="/transactions" style={{ textDecoration: "none", display: "inline-block" }}>
              View Transactions →
            </a>
            <a className="btn secondary" href="/" style={{ textDecoration: "none", display: "inline-block" }}>
              Go to Dashboard
            </a>
            <button className="btn secondary" onClick={handleReset} style={{ display: "inline-block" }}>
              + Upload Another Statement
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
