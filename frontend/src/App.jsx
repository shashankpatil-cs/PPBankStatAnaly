import React from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import Login from "./components/Login.jsx";
import Dashboard from "./components/Dashboard.jsx";
import UploadPDF from "./components/UploadPDF.jsx";
import TransactionTable from "./components/TransactionTable.jsx";
import AIAssistant from "./components/AIAssistant.jsx";

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
        <h1>💜 PhonePe Analyzer</h1>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/upload">Upload Statement</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/assistant">AI Assistant</NavLink>
        </nav>
        <div style={{ marginTop: 40 }}>
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
        <Route
          path="/assistant"
          element={
            <ProtectedRoute>
              <Shell><AIAssistant /></Shell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
