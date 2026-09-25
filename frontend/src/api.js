import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// ---- Auth ----
export const signup = (email, password, name) =>
  api.post("/auth/signup", { email, password, name });

export const login = (email, password) => {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  return api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
};

// ---- Statements ----
export const getAiStatus = () => api.get("/statements/ai-status");

export const uploadStatement = (file, pdfPassword, useAi = true, onProgress = null) => {
  const form = new FormData();
  form.append("file", file);
  if (pdfPassword) form.append("pdf_password", pdfPassword);
  form.append("use_ai", useAi);
  return api.post("/statements/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: onProgress,
  });
};
export const listStatements = () => api.get("/statements");

// ---- Dashboard ----
export const getSummary = (params) => api.get("/dashboard/summary", { params });
export const getTopRecipients = (params) => api.get("/dashboard/top-recipients", { params });
export const getTrend = (params) => api.get("/dashboard/trend", { params });
export const getCategories = (params) => api.get("/dashboard/categories", { params });

// ---- Transactions ----
export const listTransactions = (params) => api.get("/transactions", { params });
export const updateTransaction = (id, data) => api.patch(`/transactions/${id}`, data);
export const listCategories = () => api.get("/transactions/categories/list");
export const deleteTransaction = (id) => api.delete(`/transactions/${id}`);
export const exportCsvUrl = (params) => {
  const qs = new URLSearchParams(params).toString();
  return `${api.defaults.baseURL}/transactions/export/csv${qs ? `?${qs}` : ""}`;
};

// ---- AI Assistant ----
export const chatWithAssistant = (message, conversationId) =>
  api.post("/assistant/chat", { message, conversation_id: conversationId });
