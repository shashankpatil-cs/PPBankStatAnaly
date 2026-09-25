import React, { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getSummary, getTopRecipients, getTrend } from "../api.js";

const BAR_COLORS = [
  "#5f259f", "#7c3aed", "#8b5cf6", "#a78bfa",
  "#0e9f6e", "#10b981", "#3b82f6", "#6366f1",
  "#f59e0b", "#ec4899", "#64748b", "#94a3b8",
  "#14b8a6", "#f97316", "#06b6d4", "#84cc16",
  "#d946ef", "#6b7280", "#0284c7", "#4f46e5"
];

function fmtInr(n) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [trendData, setTrendData] = useState([]);
  const [granularity, setGranularity] = useState("monthly");

  // Top Counterparties Controls
  const [topType, setTopType] = useState("DEBIT"); // "DEBIT" = who received most money from user; "CREDIT" = who sent most
  const [topLimit, setTopLimit] = useState(10);    // default Top 10
  const [topData, setTopData] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadBase = async () => {
    setLoading(true);
    setError("");
    try {
      const [s, t] = await Promise.all([
        getSummary(),
        getTrend({ granularity }),
      ]);
      setSummary(s.data);
      setTrendData(t.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  const loadTop = async () => {
    try {
      const res = await getTopRecipients({ n: topLimit, txn_type: topType });
      setTopData(res.data || []);
    } catch (err) {
      console.error("Failed to load top counterparties", err);
    }
  };

  useEffect(() => {
    loadBase();
  }, [granularity]);

  useEffect(() => {
    loadTop();
  }, [topLimit, topType]);

  if (loading) return <p className="muted">Loading dashboard...</p>;
  if (error) return <p className="error-text">{error}</p>;

  const hasData = summary && summary.transaction_count > 0;
  const totalFlow = topType === "DEBIT" ? summary?.total_spent || 1 : summary?.total_received || 1;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2>Dashboard</h2>
        {summary?.date_range && (
          <span className="muted" style={{ fontSize: 13 }}>
            Statement: {summary.date_range.formatted_from || summary.date_range.from} to {summary.date_range.formatted_to || summary.date_range.to}
          </span>
        )}
      </div>

      {!hasData && (
        <div className="card" style={{ marginBottom: 24 }}>
          No transactions yet. <a href="/upload">Upload a PhonePe statement</a> to get started.
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="summary-grid">
        <div className="card summary-card">
          <div className="label">Total Spent (Debits)</div>
          <div className="value spent">{fmtInr(summary?.total_spent)}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {summary?.debit_count ?? 0} debit transactions
          </div>
        </div>
        <div className="card summary-card">
          <div className="label">Total Received (Credits)</div>
          <div className="value received">{fmtInr(summary?.total_received)}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {summary?.credit_count ?? 0} credit transactions
          </div>
        </div>
        <div className="card summary-card">
          <div className="label">Net Cash Flow</div>
          <div className="value net" style={{ color: (summary?.net_cash_flow || 0) >= 0 ? "var(--green)" : "var(--purple)" }}>
            {fmtInr(summary?.net_cash_flow)}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            {(summary?.net_cash_flow || 0) >= 0 ? "Net Positive" : "Net Outflow"}
          </div>
        </div>
        <div className="card summary-card">
          <div className="label">All Transactions</div>
          <div className="value">{summary?.transaction_count ?? 0}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            100% parsed & stored
          </div>
        </div>
      </div>

      {/* Spending & Received Trend + Financial Snapshot */}
      <div className="grid-2">
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Spending & Received Trend</h3>
            <div className="segmented-control">
              <button
                type="button"
                className={`segmented-btn ${granularity === "monthly" ? "active" : ""}`}
                onClick={() => setGranularity("monthly")}
              >
                Monthly
              </button>
              <button
                type="button"
                className={`segmented-btn ${granularity === "daily" ? "active" : ""}`}
                onClick={() => setGranularity("daily")}
              >
                Daily
              </button>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => fmtInr(v)} />
              <Legend />
              <Line type="monotone" dataKey="spent" stroke="#e02424" name="Spent (Debit)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="received" stroke="#0e9f6e" name="Received (Credit)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Financial Snapshot</h3>
            <span style={{ fontSize: 11, color: "var(--purple)", background: "var(--purple-light)", padding: "3px 8px", borderRadius: 6, fontWeight: 600 }}>
              Spending Averages
            </span>
          </div>

          <div>
            {/* Average spent in a day */}
            <div className="insight-metric-box daily">
              <div className="label">
                <span>Average Spent / Day</span>
                <span style={{ color: "var(--red)", fontSize: 11 }}>Daily</span>
              </div>
              <div className="val" style={{ color: "var(--red)" }}>
                {fmtInr(summary?.avg_spent_per_day)}
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-muted)", marginLeft: 4 }}>/ day</span>
              </div>
              <div className="subtext">
                Actual Spent ({fmtInr(summary?.actual_spent)}) ÷ 30 days/mo
              </div>
            </div>

            {/* Average in a month */}
            <div className="insight-metric-box monthly" style={{ marginBottom: 0 }}>
              <div className="label">
                <span>Average Spent / Month</span>
                <span style={{ color: "var(--purple)", fontSize: 11 }}>Monthly</span>
              </div>
              <div className="val" style={{ color: "var(--purple)" }}>
                {fmtInr(summary?.avg_spent_per_month)}
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-muted)", marginLeft: 4 }}>/ mo</span>
              </div>
              <div className="subtext">
                Actual Spent ({fmtInr(summary?.actual_spent)}) ÷ {summary?.months_count ?? 1} mo
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Featured Section: Top 10 / Selectable Who Received Most Money */}
      <div className="card" style={{ marginTop: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
          <div>
            <h3 style={{ margin: 0 }}>
              {topType === "DEBIT"
                ? `Top ${topLimit} Who Received Most Money`
                : `Top ${topLimit} Who Sent Most Money`}
            </h3>
            <p className="muted" style={{ margin: "4px 0 0 0" }}>
              {topType === "DEBIT"
                ? "Ranked list of people and merchants you paid the most to"
                : "Ranked list of people and sources you received the most from"}
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {/* Mode Switcher: Money Sent vs Received */}
            <div className="segmented-control">
              <button
                type="button"
                className={`segmented-btn ${topType === "DEBIT" ? "active" : ""}`}
                onClick={() => setTopType("DEBIT")}
              >
                💸 Money Sent
              </button>
              <button
                type="button"
                className={`segmented-btn ${topType === "CREDIT" ? "active" : ""}`}
                onClick={() => setTopType("CREDIT")}
              >
                💰 Money Received
              </button>
            </div>

            {/* Count Selector */}
            <select
              value={topLimit}
              onChange={(e) => setTopLimit(Number(e.target.value))}
              style={{ padding: "6px 10px", fontSize: 13, borderRadius: 8 }}
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={20}>Top 20</option>
            </select>
          </div>
        </div>

        {topData.length === 0 ? (
          <p className="muted">No transactions found for this view.</p>
        ) : (
          <div className="leaderboard-layout">
            {/* Horizontal Bar Chart */}
            <div>
              <ResponsiveContainer width="100%" height={Math.max(300, topData.length * 36)}>
                <BarChart
                  data={topData}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis
                    dataKey="counterparty"
                    type="category"
                    width={130}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(v, _, item) => [
                      `${fmtInr(v)} (${item.payload.transaction_count} txns)`,
                      topType === "DEBIT" ? "Total Sent" : "Total Received",
                    ]}
                  />
                  <Bar
                    dataKey="total_amount"
                    radius={[0, 6, 6, 0]}
                  >
                    {topData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Ranked Leaderboard List */}
            <div style={{ background: "#fafafa", borderRadius: 12, padding: "12px 16px", border: "1px solid #f1f5f9" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, paddingBottom: 8, borderBottom: "1px solid #e2e8f0" }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Rank & Recipient
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Amount & Share
                </span>
              </div>
              <table className="leaderboard-table">
                <tbody>
                  {topData.map((r, i) => {
                    const sharePct = ((r.total_amount / totalFlow) * 100).toFixed(1);
                    const rankClass = i === 0 ? "rank-1" : i === 1 ? "rank-2" : i === 2 ? "rank-3" : "rank-other";
                    return (
                      <tr key={r.counterparty}>
                        <td style={{ width: 34 }}>
                          <span className={`rank-badge ${rankClass}`}>{i + 1}</span>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, color: "var(--text)" }}>{r.counterparty}</div>
                          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            {r.transaction_count} transaction{r.transaction_count > 1 ? "s" : ""}
                          </div>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <div style={{ fontWeight: 700, color: topType === "DEBIT" ? "var(--red)" : "var(--green)" }}>
                            {fmtInr(r.total_amount)}
                          </div>
                          <div style={{ fontSize: 11, color: "var(--purple)", fontWeight: 500 }}>
                            {sharePct}% of total
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
