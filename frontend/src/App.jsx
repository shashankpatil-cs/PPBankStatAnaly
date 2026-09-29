import React from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import Login from "./components/Login.jsx";
import Dashboard from "./components/Dashboard.jsx";
import UploadPDF from "./components/UploadPDF.jsx";
import TransactionTable from "./components/TransactionTable.jsx";
import { deleteAccount } from "./api.js";

function isAuthed() {
  return !!localStorage.getItem("access_token");
}

function ProtectedRoute({ children }) {
  if (!isAuthed()) return <Navigate to="/login" replace />;
  return children;
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
  return (
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
  );
}
