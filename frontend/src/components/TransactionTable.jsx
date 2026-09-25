import React, { useEffect, useState } from "react";
import { listTransactions, updateTransaction, listCategories, exportCsvUrl } from "../api.js";

function fmtInr(n) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(n || 0);
}

const DEFAULT_CATEGORIES = [
  "Person",
  "Friend",
  "Groceries",
  "Food",
  "Shopping",
  "Recharge & Bills",
  "Entertainment",
  "Health",
  "Travel",
  "Investment",
  "Family",
  "Uncategorized",
];

function getCategoryClass(cat) {
  if (!cat) return "cat-uncategorized";
  const lower = cat.toLowerCase();
  if (lower.includes("person")) return "cat-person";
  if (lower.includes("friend")) return "cat-friend";
  if (lower.includes("family")) return "cat-family";
  if (lower.includes("grocer")) return "cat-groceries";
  if (lower.includes("food") || lower.includes("dining")) return "cat-food";
  if (lower.includes("shop")) return "cat-shopping";
  if (lower.includes("recharge") || lower.includes("bill") || lower.includes("utilit")) return "cat-recharge-bills";
  if (lower.includes("entertain") || lower.includes("movie")) return "cat-entertainment";
  if (lower.includes("health") || lower.includes("med") || lower.includes("doctor")) return "cat-health";
  if (lower.includes("travel") || lower.includes("transport") || lower.includes("fuel")) return "cat-travel";
  if (lower.includes("invest") || lower.includes("fund") || lower.includes("gold")) return "cat-investment";
  if (lower === "uncategorized") return "cat-uncategorized";
  return "cat-custom";
}

export default function TransactionTable() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Filters
  const [search, setSearch] = useState("");
  const [txnType, setTxnType] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [availableCategories, setAvailableCategories] = useState(DEFAULT_CATEGORIES);
  const [loading, setLoading] = useState(true);

  // Edit Modal State
  const [editingItem, setEditingItem] = useState(null);
  const [editCounterparty, setEditCounterparty] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCategory, setEditCategory] = useState("Uncategorized");
  const [isCustomCategory, setIsCustomCategory] = useState(false);
  const [customCategoryInput, setCustomCategoryInput] = useState("");
  const [updateAllMatching, setUpdateAllMatching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState("");

  const loadCategories = async () => {
    try {
      const res = await listCategories();
      if (res.data?.categories) {
        const merged = Array.from(new Set([...DEFAULT_CATEGORIES, ...res.data.categories]));
        setAvailableCategories(merged);
      }
    } catch {
      // fallback to defaults if endpoint error
      setAvailableCategories(DEFAULT_CATEGORIES);
    }
  };

  const load = async () => {
    setLoading(true);
    const params = { page, page_size: pageSize };
    if (search) params.search = search;
    if (txnType) params.txn_type = txnType;
    if (categoryFilter) params.category = categoryFilter;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    try {
      const res = await listTransactions(params);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      console.error("Failed to load transactions", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    load();
  }, [page]);

  const applyFilters = (e) => {
    e.preventDefault();
    setPage(1);
    load();
  };

  const resetFilters = () => {
    setSearch("");
    setTxnType("");
    setCategoryFilter("");
    setStartDate("");
    setEndDate("");
    setPage(1);
    setTimeout(() => {
      listTransactions({ page: 1, page_size: pageSize }).then((res) => {
        setItems(res.data.items);
        setTotal(res.data.total);
      });
    }, 0);
  };

  const openEditModal = (t) => {
    setEditingItem(t);
    setEditCounterparty(t.counterparty || "");
    setEditDescription(t.description || "");
    const curCat = t.category || "Uncategorized";
    if (DEFAULT_CATEGORIES.includes(curCat)) {
      setEditCategory(curCat);
      setIsCustomCategory(false);
      setCustomCategoryInput("");
    } else {
      setEditCategory("__CUSTOM__");
      setIsCustomCategory(true);
      setCustomCategoryInput(curCat);
    }
    setUpdateAllMatching(false);
  };

  const closeEditModal = () => {
    setEditingItem(null);
    setSaving(false);
  };

  const handleCategorySelectChange = (e) => {
    const val = e.target.value;
    if (val === "__CUSTOM__") {
      setIsCustomCategory(true);
      setEditCategory("__CUSTOM__");
    } else {
      setIsCustomCategory(false);
      setEditCategory(val);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!editingItem) return;

    const finalCategory = isCustomCategory
      ? (customCategoryInput.trim() || "Uncategorized")
      : editCategory;

    const finalCounterparty = editCounterparty.trim() || editingItem.counterparty;
    const finalDescription = editDescription.trim();

    setSaving(true);
    try {
      const res = await updateTransaction(editingItem._id, {
        counterparty: finalCounterparty,
        category: finalCategory,
        description: finalDescription,
        update_all_matching: updateAllMatching,
      });

      const updatedCount = res.data?.updated_count || 1;
      const msg = updateAllMatching
        ? `Successfully updated ${updatedCount} transactions for "${editingItem.counterparty}"!`
        : `Transaction updated successfully!`;

      setToastMessage(msg);
      setTimeout(() => setToastMessage(""), 5000);

      closeEditModal();
      load();
      loadCategories();
    } catch (err) {
      alert("Failed to update transaction: " + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h2>Transactions</h2>
        <span className="muted">{total} total transactions found</span>
      </div>

      {toastMessage && (
        <div className="toast-alert">
          <span>✓ {toastMessage}</span>
          <button
            onClick={() => setToastMessage("")}
            style={{ background: "transparent", color: "inherit", border: "none", cursor: "pointer", fontSize: 16 }}
          >
            ✕
          </button>
        </div>
      )}

      <form className="filters-bar" onSubmit={applyFilters}>
        <input
          placeholder="Search counterparty, description, or ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: 240 }}
        />
        <select value={txnType} onChange={(e) => setTxnType(e.target.value)}>
          <option value="">All types</option>
          <option value="DEBIT">Debit</option>
          <option value="CREDIT">Credit</option>
        </select>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
          <option value="">All categories</option>
          {availableCategories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          title="Start date"
          onChange={(e) => setStartDate(e.target.value)}
        />
        <input
          type="date"
          value={endDate}
          title="End date"
          onChange={(e) => setEndDate(e.target.value)}
        />
        <button type="submit">Apply</button>
        {(search || txnType || categoryFilter || startDate || endDate) && (
          <button type="button" className="secondary" onClick={resetFilters}>
            Reset
          </button>
        )}
        <a
          className="btn secondary"
          style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", marginLeft: "auto" }}
          href={exportCsvUrl({
            ...(search ? { search } : {}),
            ...(txnType ? { txn_type: txnType } : {}),
            ...(categoryFilter ? { category: categoryFilter } : {}),
            ...(startDate ? { start_date: startDate } : {}),
            ...(endDate ? { end_date: endDate } : {}),
          })}
        >
          Export CSV
        </a>
      </form>

      <div className="card">
        {loading ? (
          <p className="muted">Loading transactions...</p>
        ) : items.length === 0 ? (
          <p className="muted">No transactions match these filters.</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Counterparty</th>
                  <th>Description</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Category</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t._id}>
                    <td style={{ whiteSpace: "nowrap" }}>{t.date}</td>
                    <td style={{ whiteSpace: "nowrap", color: "var(--text-muted)" }}>{t.time || "—"}</td>
                    <td>
                      <div style={{ fontWeight: 500, color: "var(--text)" }}>{t.counterparty}</div>
                      {t.txn_id && (
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                          ID: {t.txn_id}
                        </div>
                      )}
                    </td>
                    <td style={{ maxWidth: 220, fontSize: 13, color: "var(--text-muted)" }}>
                      {t.description || "—"}
                    </td>
                    <td>
                      <span className={`badge ${t.type === "DEBIT" ? "debit" : "credit"}`}>
                        {t.type}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{fmtInr(t.amount)}</td>
                    <td>
                      <span className={`category-badge ${getCategoryClass(t.category)}`}>
                        {t.category || "Uncategorized"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn-sm edit-btn"
                        onClick={() => openEditModal(t)}
                        title="Edit name, description, and category"
                      >
                        ✎ Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
              <span className="muted">
                Page {page} of {totalPages} ({total} total)
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </button>
                <button className="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Edit Transaction Modal */}
      {editingItem && (
        <div className="modal-overlay" onClick={closeEditModal}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Transaction Details</h3>
              <button className="modal-close-btn" onClick={closeEditModal}>
                ✕
              </button>
            </div>

            <div className="modal-meta-tag">
              <span>{editingItem.date}</span>
              <span>•</span>
              <span style={{ color: editingItem.type === "DEBIT" ? "var(--red)" : "var(--green)" }}>
                {editingItem.type}
              </span>
              <span>•</span>
              <span>{fmtInr(editingItem.amount)}</span>
            </div>

            <form onSubmit={handleSave}>
              <div className="form-field">
                <label>Counterparty / Recipient Name</label>
                <input
                  type="text"
                  required
                  value={editCounterparty}
                  onChange={(e) => setEditCounterparty(e.target.value)}
                  placeholder="e.g. Swiggy, Rakesh (Friend), Mom, Grocery Store"
                />
              </div>

              <div className="form-field">
                <label>Description / Note</label>
                <input
                  type="text"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="e.g. Food delivery, Monthly rent, Dinner split"
                />
              </div>

              <div className="form-field">
                <label>Category</label>
                <select value={editCategory} onChange={handleCategorySelectChange}>
                  <option value="Person">Person</option>
                  <option value="Friend">Friend</option>
                  <option value="Family">Family</option>
                  <option value="Groceries">Groceries</option>
                  <option value="Food">Food</option>
                  <option value="Shopping">Shopping</option>
                  <option value="Recharge & Bills">Recharge & Bills</option>
                  <option value="Entertainment">Entertainment</option>
                  <option value="Health">Health</option>
                  <option value="Travel">Travel</option>
                  <option value="Investment">Investment</option>
                  <option value="Uncategorized">Uncategorized</option>
                  {availableCategories
                    .filter((c) => !DEFAULT_CATEGORIES.includes(c))
                    .map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  <option value="__CUSTOM__">+ Add Custom Category...</option>
                </select>
              </div>

              {isCustomCategory && (
                <div className="form-field" style={{ animation: "fadeIn 0.15s ease" }}>
                  <label>Custom Category Name</label>
                  <input
                    type="text"
                    required
                    autoFocus
                    placeholder="e.g. Subscriptions, Pet Care, Fitness"
                    value={customCategoryInput}
                    onChange={(e) => setCustomCategoryInput(e.target.value)}
                  />
                </div>
              )}

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={updateAllMatching}
                  onChange={(e) => setUpdateAllMatching(e.target.checked)}
                />
                <div>
                  <div className="checkbox-label">
                    Apply to all matching transactions
                  </div>
                  <div className="checkbox-desc">
                    Also rename and set category for all other past transactions with counterparty "
                    <strong>{editingItem.counterparty}</strong>".
                  </div>
                </div>
              </label>

              <div className="modal-actions">
                <button type="button" className="secondary" onClick={closeEditModal} disabled={saving}>
                  Cancel
                </button>
                <button type="submit" disabled={saving}>
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
