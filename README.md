# PhonePe Bank Statement Analyzer

A full-stack, production-grade application to upload PhonePe transaction statement PDFs, automatically extract transactions, securely store them per-user in MongoDB, visualize financial metrics with interactive charts, and query your personal spending history via an AI Assistant powered by function-calling tools.

**Tech Stack:**
- **Frontend:** React 18 (Vite), Recharts, Axios, React Router 6
- **Backend:** FastAPI, Motor (Async MongoDB driver), Pandas, PyPDF2, pdfplumber
- **Database:** MongoDB 7.0
- **AI Assistant:** OpenAI Agents SDK (function calling with automated MongoDB querying)
- **Object Storage (Optional):** AWS S3 (for remote PDF statement archiving & presigned downloads)
- **Containerization:** Docker & Docker Compose

---

## Table of Contents

1. [Project Layout](#project-layout)
2. [Prerequisites](#prerequisites)
3. [Step 1: Setting Up the Database (MongoDB)](#step-1-setting-up-the-database-mongodb)
4. [Step 2: Initializing Environment Variables](#step-2-initializing-environment-variables)
5. [Step 3: Starting the Application](#step-3-starting-the-application)
   - [Method A: Docker Compose (Fastest & Recommended)](#method-a-docker-compose-fastest--recommended)
   - [Method B: Local Development (Manual Setup)](#method-b-local-development-manual-setup)
6. [Step 4: End-to-End Verification & First Use](#step-4-end-to-end-verification--first-use)
7. [How PDF Extraction Works](#how-pdf-extraction-works)
8. [AWS & Production Deployment](#aws--production-deployment)
9. [Security Architecture](#security-architecture)
10. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Project Layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan hook, routers
│   │   ├── config.py            # Pydantic Settings loaded from .env
│   │   ├── database.py          # Motor async client & index initialization
│   │   ├── auth.py              # JWT authentication & password hashing
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── auth_router.py   # /auth/signup, /auth/login
│   │   │   ├── upload.py        # /statements/upload (PDF -> parser -> Mongo + S3)
│   │   │   ├── transactions.py  # /transactions (CRUD, filters, CSV export)
│   │   │   ├── dashboard.py     # /dashboard/summary, /top-recipients, /trend, /categories
│   │   │   └── assistant.py     # /assistant/chat (AI financial assistant)
│   │   └── services/
│   │       ├── pdf_parser.py    # pdfplumber-based PhonePe statement parsing
│   │       ├── analytics.py     # Pandas-based financial metric calculations
│   │       ├── s3_service.py    # AWS S3 upload & presigned URLs
│   │       └── ai_agent.py      # OpenAI Agents SDK with function tools
│   ├── .env.example             # Backend environment template
│   ├── Dockerfile               # Backend production container definition
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api.js               # Axios instance, auth interceptors & endpoints
│   │   ├── App.jsx              # Main routing, layout, and sidebar navigation
│   │   └── components/
│   │       ├── Login.jsx        # Auth form (login / register)
│   │       ├── UploadPDF.jsx    # Drag-and-drop PDF upload with password support
│   │       ├── Dashboard.jsx    # Analytics cards & Recharts graphs
│   │       ├── TransactionTable.jsx # Paginated, filterable transaction table
│   │       └── AIAssistant.jsx  # Conversational chat interface
│   ├── .env.example             # Frontend environment template
│   ├── Dockerfile               # Multi-stage Vite build + Nginx container
│   ├── nginx.conf               # Nginx reverse proxy configuration
│   └── package.json             # Frontend dependencies
├── docker-compose.yml           # Multi-container orchestration (Mongo + Backend + Frontend)
└── README.md
```

---

## Prerequisites

First, clone the repository:
```bash
git clone https://github.com/shashankpatil-cs/PPBankStatAnaly.git
cd PPBankStatAnaly
```

Ensure you have the following installed on your machine:

| Requirement | Docker Compose Method | Manual Local Dev Method | Notes |
| :--- | :--- | :--- | :--- |
| **Docker & Docker Compose** | Required (Docker Desktop v20+) | Not required | Easiest zero-config option |
| **Python** | Not required | Python 3.10 or 3.11+ | Make sure `python` and `pip` are in PATH |
| **Node.js** | Not required | Node.js v18.0+ & npm v9+ | Run `node -v` to check |
| **MongoDB** | Provided by container | MongoDB 6.0+ or Docker | Or a free MongoDB Atlas URI |

---

## Step 1: Setting Up the Database (MongoDB)

### How Database Initialization Works
You **do not** need to run any manual database migration scripts, create tables, or manually configure collections.
- When the FastAPI backend starts, its `lifespan` handler calls `init_indexes()` in `app/database.py`.
- This automatically creates the database (default: `phonepe_analyzer`) and collections (`users`, `statements`, `transactions`) along with all required performance and uniqueness indexes:
  - `transactions`: Compound index on `(user_id, date DESC)`, index on `(user_id, statement_id)`, and a unique sparse index on `(user_id, txn_id)`.
  - `statements`: Index on `(user_id, uploaded_at DESC)`.
  - `users`: Unique index on `email`.

### Choose Your MongoDB Setup Option:

#### Option A: Quick Docker MongoDB Container (Recommended for Local Dev)
If you prefer running the backend and frontend locally on your host machine while keeping MongoDB isolated, start a standalone Mongo container:

```bash
docker run -d \
  --name phonepe-mongo \
  -p 27017:27017 \
  -v mongo_data:/data/db \
  mongo:7
```
*Your MongoDB instance is now accessible at `mongodb://localhost:27017`.*

#### Option B: Automated via Docker Compose
If you choose to run the entire app with `docker compose up`, MongoDB 7 is automatically provisioned, network-bridged, and persisted to a named Docker volume (`mongo_data`). No manual steps are required.

#### Option C: Native Local MongoDB Service
If you have MongoDB Community Server installed directly on your machine:
- **Windows:** Ensure the "MongoDB Server" service is running in Windows Services (`services.msc`) or run `net start MongoDB`.
- **macOS (Homebrew):** `brew services start mongodb-community@7.0`
- **Linux (Ubuntu/Debian):** `sudo systemctl start mongod`

#### Option D: Cloud MongoDB Atlas
1. Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. Create a database user and whitelist your IP address (`0.0.0.0/0` for testing).
3. Copy your connection string (e.g. `mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority`).
4. Set `MONGO_URI` in `backend/.env` to this connection string.

---

## Step 2: Initializing Environment Variables

Both the backend and frontend rely on `.env` files for configuration. Example templates are provided in each directory.

### 1. Initialize Backend Environment File

Navigate to the project root and copy `backend/.env.example` to `backend/.env`:

**On Linux / macOS (Bash / Zsh):**
```bash
cp backend/.env.example backend/.env
```

**On Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
```

**On Windows (CMD):**
```cmd
copy backend\.env.example backend\.env
```

#### Backend Environment Variables Reference (`backend/.env`):

| Variable | Default Value | Required? | Description & Recommended Settings |
| :--- | :--- | :--- | :--- |
| `MONGO_URI` | `mongodb://localhost:27017` | **Yes** | Connection string. Use `mongodb://localhost:27017` for local host development, `mongodb://mongo:27017` for Docker Compose, or your MongoDB Atlas URI. |
| `MONGO_DB_NAME` | `phonepe_analyzer` | **Yes** | Target database name in MongoDB. |
| `JWT_SECRET` | `change-me-in-production` | **Yes** | Secret key for signing authentication tokens. **Must change for production!** *(See generation command below)*. |
| `JWT_ALGORITHM` | `HS256` | **Yes** | JWT signing algorithm. |
| `JWT_EXPIRE_MINUTES` | `10080` | **Yes** | Session token expiration time in minutes (default is 7 days). |
| `OPENAI_API_KEY` | *(empty)* | Optional | OpenAI API Key (`sk-...`). Required if you want to use the AI Assistant chat. Everything else works without it. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Optional | OpenAI model ID used for function calling (e.g. `gpt-4o-mini`, `gpt-4o`). |
| `AWS_ACCESS_KEY_ID` | *(empty)* | Optional | AWS IAM Access Key for S3 storage. If blank, PDFs and CSVs are stored locally and in Mongo without S3. |
| `AWS_SECRET_ACCESS_KEY`| *(empty)* | Optional | AWS IAM Secret Access Key. |
| `AWS_REGION` | `ap-south-1` | Optional | AWS Region of your S3 bucket. |
| `S3_BUCKET_NAME` | `phonepe-analyzer-bucket`| Optional | Name of your S3 bucket. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | **Yes** | Comma-separated list of allowed frontend origins for CORS headers. |
| `UPLOAD_DIR` | `/tmp/phonepe_uploads` | **Yes** | Temporary directory where uploaded PDFs are buffered during parsing. *(On Windows local dev, you can use `./uploads`)*. |

> [!TIP]
> **Generate a secure `JWT_SECRET`:**
> Run the following one-liner in your terminal to generate a cryptographically secure 256-bit secret:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```
> Copy the output and paste it into `JWT_SECRET` in `backend/.env`.

---

### 2. Initialize Frontend Environment File

Copy `frontend/.env.example` to `frontend/.env`:

**On Linux / macOS:**
```bash
cp frontend/.env.example frontend/.env
```

**On Windows (PowerShell):**
```powershell
Copy-Item frontend\.env.example frontend\.env
```

**On Windows (CMD):**
```cmd
copy frontend\.env.example frontend\.env
```

#### Frontend Environment Variables Reference (`frontend/.env`):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `/api` | Base path for all API calls. When set to `/api`, Vite's development proxy or Nginx in Docker will forward requests to the FastAPI backend at `http://localhost:8000`. |

---

## Step 3: Starting the Application

You can run the full stack using **Method A (Docker Compose)** or **Method B (Local Manual Setup)**.

---

### Method A: Docker Compose (Fastest & Recommended)

Docker Compose automatically spins up MongoDB, builds the FastAPI backend container, builds the React frontend container with Nginx, and connects them on an internal network.

1. Ensure your `.env` files are configured as described in Step 2.
2. In the project root, run:
   ```bash
   docker compose up --build
   ```
   *(Add `-d` to run containers detached in the background: `docker compose up --build -d`)*

3. Verify running containers:
   ```bash
   docker compose ps
   ```

4. **Access your services:**
   - **Frontend Web App:** [http://localhost:3000](http://localhost:3000)
   - **Backend API Interactive Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Backend Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

5. **Useful Docker commands:**
   - View live logs: `docker compose logs -f`
   - View backend logs only: `docker compose logs -f backend`
   - Stop containers: `docker compose down`
   - Stop containers and remove database volume: `docker compose down -v`

---

### Method B: Local Development (Manual Setup)

Follow this method if you want instant hot-reloading for code modifications without rebuilding containers.

#### 1. Ensure MongoDB is Running
Make sure MongoDB is running on port 27017 (e.g., via Docker `docker run -d -p 27017:27017 --name phonepe-mongo mongo:7` or your local service).

Make sure `backend/.env` has:
```env
MONGO_URI=mongodb://localhost:27017
```

#### 2. Start the FastAPI Backend

Open a terminal and navigate to `backend`:

```bash
cd backend
```

**Create and activate a Python virtual environment:**

- **On macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

- **On Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
  *(If PowerShell gives a script execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

- **On Windows (Command Prompt):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Start the FastAPI development server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see logs indicating successful startup and index creation:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Test the backend health in your browser or with curl:
```bash
curl http://localhost:8000/health
# Output: {"status":"ok"}
```

Interactive API documentation is now live at [http://localhost:8000/docs](http://localhost:8000/docs).

---

#### 3. Start the React Frontend

Open a second terminal window and navigate to `frontend`:

```bash
cd frontend
```

**Install Node dependencies:**
```bash
npm install
```

**Start Vite development server:**
```bash
npm run dev
```

You should see output similar to:
```
  VITE v5.4.8  ready in 210 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.1.x:5173/
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

> [!NOTE]
> Vite is configured to proxy all `/api/*` calls directly to `http://localhost:8000` (see `frontend/vite.config.js`). You do not need to configure custom CORS proxies for local dev.

---

## Step 4: End-to-End Verification & First Use

1. **Sign Up & Log In:**
   - Go to `http://localhost:5173` (or `http://localhost:3000` in Docker).
   - Click "Need an account? Sign up".
   - Register with your name, email, and password. You will receive a JWT and be logged in immediately.

2. **Upload a Statement:**
   - Download an official statement PDF from your PhonePe app (*History -> Download Statement*).
   - Go to the **Upload Statement** tab in the dashboard.
   - If your PDF has an opening password (common for bank and UPI statements), enter it in the password field.
   - Upload the PDF. The backend will parse the pages and return the count of extracted transactions.

3. **Explore Dashboard & Analytics:**
   - Visit the **Dashboard** to see Total Debits, Total Credits, Net Cash Flow, Category Breakdown pie chart, Monthly Spending trend, and Top 5 Recipients.
   - Visit the **Transactions** view to search, filter by date/amount, edit categories, or export your filtered history as a CSV file.

4. **Test the AI Assistant:**
   - Ensure `OPENAI_API_KEY` is provided in `backend/.env`.
   - Navigate to the **AI Assistant** tab.
   - Ask questions like:
     - *"How much did I spend in total last month?"*
     - *"Who did I send the most money to?"*
     - *"Did I receive any payments larger than ₹5,000?"*
   - The assistant autonomously executes tool functions against your scoped MongoDB records to answer with real data.

---

## How PDF Extraction Works

PhonePe and bank statement PDFs are parsed using a dual-engine architecture combining **Coordinate-Based Word Clustering & Transaction Block Grouping** and **OpenAI AI Precision Extraction** with a local deterministic regex fallback:

1. **Coordinate-Based Clustering (`pdfplumber`):**
   - Extracts word bounding boxes (`x0, top`) instead of naive `.extract_text()` newline splits.
   - Clusters words into horizontal rows by vertical proximity (`y_tolerance`).
   - Dynamically identifies column boundaries (`Date`, `Details`, `Type`, `Amount`) across any page width.
   - Groups multi-line rows into transaction blocks anchored on the Date cell, merging wrapped cells (e.g. `INR\n17000.00` is kept intact as `INR 17000.00`, completely eliminating digit-splitting bugs).
2. **OpenAI AI Precision Extraction (Primary Engine):**
   - Sends clean, coordinate-isolated blocks to OpenAI (`gpt-4o-mini` or the model configured in `OPENAI_MODEL`).
   - Uses structured JSON extraction with schema validation to extract:
     - `date`: Validated ISO date (`YYYY-MM-DD`)
     - `type`: `DEBIT` or `CREDIT`
     - `counterparty`: Clean person or merchant name
     - `amount`: Exact positive decimal float
     - `description`: Transaction details, notes, or purpose
     - `txn_id`: Unique PhonePe transaction ID, UTR, or Order ID
     - `category`: Categorization (e.g., Food, Groceries, Shopping, Travel, Recharge & Bills)
   - Strict validation via Pydantic (`ExtractedTransactionValidation`) ensures zero hallucinations or malformed data reach MongoDB.
3. **Deterministic Local Fallback Engine:**
   - If OpenAI is disabled or unavailable, the parser executes over the coordinate-assembled transaction blocks.
   - Evaluates reassembled amount strings and details without line-splitting bugs.
4. **Strict Deduplication & Zero Data Loss:**
   - Deduplicates on `(user_id, txn_id)` and `(date, amount, type, counterparty)`.
   - Records extraction method (`ai` vs `regex_fallback`) and metadata in the database.

---

## AWS & Production Deployment

- **S3 Bucket Configuration:**
  - Create a private S3 bucket.
  - Set `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` in `backend/.env`.
  - In an ECS or EC2 environment, use IAM Task / Instance Roles instead of hardcoded access keys (boto3 discovers roles automatically).
- **MongoDB in Production:**
  - Use MongoDB Atlas or AWS DocumentDB instead of a single container.
  - Set `MONGO_URI` to your replica set connection string.
- **Production Containers:**
  - `backend/Dockerfile` and `frontend/Dockerfile` are self-contained. Push them to Amazon ECR and deploy via AWS ECS (Fargate) or Kubernetes.
  - Inject secrets (`JWT_SECRET`, `OPENAI_API_KEY`, etc.) via AWS Secrets Manager or SSM Parameter Store.

---

## Security Architecture

- **Tenant Isolation:** Every transaction and statement record has a `user_id` field. All MongoDB queries in endpoints and AI tools explicitly filter by the authenticated user's ID extracted from the validated JWT token.
- **AI Tool Sandboxing:** The AI Assistant functions are programmatically closed over the caller's `user_id` server-side. The model cannot override or manipulate user scoping via prompt injection.
- **Password Security:** Passwords are never stored in plaintext; they are securely hashed using `passlib` with `bcrypt`.
- **S3 Scoping:** S3 object keys follow `{user_id}/statements/{statement_id}.pdf` preventing unauthorized cross-user file access.

---

## Troubleshooting & FAQs

### 1. Backend fails with `ServerSelectionTimeoutError` (MongoDB Connection Refused)
- **Cause:** FastAPI cannot reach MongoDB at `MONGO_URI`.
- **Fix:**
  - If running locally without Docker: ensure MongoDB is running (`docker ps` or check local service) and verify that `MONGO_URI=mongodb://localhost:27017` in `backend/.env`.
  - If running inside Docker Compose: ensure `MONGO_URI=mongodb://mongo:27017` (this is automatically injected by `docker-compose.yml`).

### 2. PowerShell: "File ... Activate.ps1 cannot be loaded because running scripts is disabled on this system"
- **Cause:** Windows PowerShell execution policy prevents running unverified scripts.
- **Fix:** In PowerShell, run:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\venv\Scripts\Activate.ps1
  ```

### 3. Port 8000 or Port 27017 Already in Use
- **Cause:** Another process or previous container is occupying the port.
- **Fix:**
  - Find the occupying process:
    - On Windows: `netstat -ano | findstr :8000`
    - On Linux/macOS: `lsof -i :8000`
  - Or stop old Docker containers: `docker stop $(docker ps -q)`

### 4. AI Assistant returns an error or empty response
- **Cause:** `OPENAI_API_KEY` is empty, expired, or invalid.
- **Fix:** Check `backend/.env` and verify your key is active and has access to `OPENAI_MODEL` (`gpt-4o-mini`).

### 5. PDF Upload returns 422 "Could not read PDF"
- **Cause:** The PDF is corrupted or password-protected and no password was provided.
- **Fix:** Enter the PDF password in the password input box before clicking upload. (PhonePe statement passwords are often registered mobile numbers or date of birth formats depending on the account type).
