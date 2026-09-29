import React from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import Login from "./components/Login.jsx";
import Dashboard from "./components/Dashboard.jsx";
import UploadPDF from "./components/UploadPDF.jsx";
import TransactionTable from "./components/TransactionTable.jsx";
import { deleteAccount, listStatements, updateStatement } from "./api.js";
import { ActiveStatementContext } from "./context.js";

function isAuthed() {
  return !!localStorage.getItem("access_token");
}

function ProtectedRoute({ children }) {
  if (!isAuthed()) return <Navigate to="/login" replace />;
  return children;
}

function StatementSelector() {
  const { activeStatementId, setActiveStatementId, refreshCounter, triggerRefresh } = React.useContext(ActiveStatementContext);
  const [statements, setStatements] = React.useState([]);
  const [editingId, setEditingId] = React.useState(null);
  const [editName, setEditName] = React.useState("");

  const load = () => {
    listStatements().then((res) => {
      setStatements(res.data);
      if (res.data.length > 0 && activeStatementId === null) {
         setActiveStatementId(res.data[0]._id);
      }
    });
  };

  React.useEffect(() => {
    if (isAuthed()) load();
  }, [refreshCounter]);

  if (statements.length === 0) return null;

  return (
    <div style={{ marginTop: 24, marginBottom: 24 }}>
      <h3 style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "1px" }}>Active Statement</h3>
      <select 
        value={activeStatementId || ""} 
        onChange={(e) => setActiveStatementId(e.target.value)}
        style={{ width: "100%", marginBottom: 8, padding: "8px 12px", background: "var(--bg)", border: "1px solid var(--card-border)", color: "var(--text)", borderRadius: "6px" }}
      >
        <option value="">All Statements (Combined)</option>
        {statements.map(s => (
          <option key={s._id} value={s._id}>{s.filename}</option>
        ))}
      </select>
      
      {activeStatementId && (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {editingId === activeStatementId ? (
            <>
              <input 
                type="text" 
                value={editName}
                onChange={e => setEditName(e.target.value)}
                style={{ flex: 1, padding: "6px 8px", fontSize: 13, border: "1px solid var(--primary)", background: "var(--bg)", color: "var(--text)", borderRadius: "4px" }}
                autoFocus
              />
              <button className="btn-sm" style={{ padding: "6px 12px" }} onClick={async () => {
                try {
                  await updateStatement(activeStatementId, editName);
                  setEditingId(null);
                  triggerRefresh();
                } catch(e) {
                  alert("Failed to rename statement");
                }
              }}>Save</button>
            </>
          ) : (
            <button className="secondary btn-sm" onClick={() => {
              setEditingId(activeStatementId);
              const stmt = statements.find(s => s._id === activeStatementId);
              setEditName(stmt ? stmt.filename : "");
            }} style={{ width: "100%", padding: "6px 12px" }}>
              ✎ Rename
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Shell({ children }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "32px" }}>
          <img 
            src="https://upload.wikimedia.org/wikipedia/commons/7/71/PhonePe_Logo.svg" 
            alt="PhonePe Logo" 
            style={{ width: "28px", height: "28px", borderRadius: "50%", background: "#fff", padding: "2px" }} 
          />
          <h1 style={{ margin: 0, fontSize: "22px" }}>SpendWise</h1>
        </div>
        <nav>
          <NavLink to="/upload">Upload Statement</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/" end>Dashboard</NavLink>
        </nav>
        
        <StatementSelector />

        <div style={{ marginTop: 40, display: "flex", flexDirection: "column", gap: "12px" }}>
          <button
            className="secondary"
            style={{ background: "transparent", color: "white", border: "1px solid rgba(255,255,255,0.4)" }}
            onClick={() => {
              localStorage.removeItem("access_token");
              window.location.href = "/login";
            }}
          >
            Log out
          </button>
          <button
            className="secondary"
            style={{ background: "rgba(239, 68, 68, 0.1)", color: "#fca5a5", border: "1px solid rgba(239, 68, 68, 0.4)" }}
            onClick={async () => {
              if (window.confirm("Are you sure you want to completely delete your account? This will permanently erase all your uploaded PDFs and saved transactions. This cannot be undone.")) {
                try {
                  await deleteAccount();
                  localStorage.removeItem("access_token");
                  window.location.href = "/login";
                } catch (e) {
                  alert("Failed to delete account");
                }
              }
            }}
          >
            Delete Account
          </button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}

export default function App() {
  const [activeStatementId, setActiveStatementId] = React.useState(null);
  const [refreshCounter, setRefreshCounter] = React.useState(0);
  const triggerRefresh = () => setRefreshCounter(c => c + 1);

  return (
    <ActiveStatementContext.Provider value={{ activeStatementId, setActiveStatementId, refreshCounter, triggerRefresh }}>
      <BrowserRouter>
        <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Shell><Dashboard /></Shell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <Shell><UploadPDF /></Shell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/transactions"
          element={
            <ProtectedRoute>
              <Shell><TransactionTable /></Shell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
    </ActiveStatementContext.Provider>
  );
}
