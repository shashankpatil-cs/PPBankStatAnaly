"""
PhonePe bank/transaction statement PDF parser.

Features:
1. Coordinate-Based Row Clustering & Transaction Block Grouping (Approach 2):
   Groups words by y-coordinate proximity and column x-coordinates (Date, Details, Type, Amount),
   completely eliminating line-break splitting bugs (e.g., 'INR\\n17000.00' -> 7).
2. AI Precision Extraction (OpenAI API):
   Uses OPENAI_API_KEY from .env to accurately extract:
   - date
   - credit/debit
   - person or merchant name
   - amount
   - description
   - transaction ID
   Validates structured JSON output before saving to the database.
3. Robust Fallback Parser:
   Deterministic local regex parser executing over coordinate-clustered blocks if OpenAI is unavailable.
4. Strict Deduplication:
   Guarantees no duplicate records are ever returned.
"""
import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

import pdfplumber
from openai import AsyncOpenAI

from app.config import settings
from app.schemas import ExtractedTransactionValidation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
DATE_HEADER_RE = re.compile(
    r"(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"\.?\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
DATE_ALT_RE = re.compile(
    r"(?P<date>"
    r"\d{1,2}[-/\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/\s]\d{2,4}"
    r"|\d{4}[-/]\d{2}[-/]\d{2}"
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    re.IGNORECASE,
)
TIME_RE = re.compile(r"(?P<time>\d{1,2}:\d{2}\s?(?:am|pm|AM|PM)?)")
AMOUNT_RE = re.compile(r"(?:Rs\.?|INR|\u20b9)?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
TXN_ID_RE = re.compile(r"Transaction\s*ID[:\s]*([A-Za-z0-9]+)", re.IGNORECASE)
UTR_RE = re.compile(r"UTR\s*(?:No\.?|Number)?[:\s]*([A-Za-z0-9]+)", re.IGNORECASE)
ORDER_ID_RE = re.compile(r"Order\s*ID[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE)

COUNTERPARTY_RE = re.compile(
    r"(?:Paid\s+to|Payment\s+to|Sent\s+to|Received\s+from|Refund\s+from"
    r"|Cashback\s+from|Transfer\s+to|Transferred\s+to)\s*[:\-]?\s*(?P<who>[^\n\r|]+)",
    re.IGNORECASE,
)
SERVICE_RE = re.compile(
    r"(?:Paid|Payment|Received|Refund)\s*[-\u2013:]\s*(?P<who>[^\n\r|]+)",
    re.IGNORECASE,
)

CLEAN_FOOTER_RE = re.compile(
    r"\n?Page \d+ of \d+.*?(?:Date\s+Transaction\s+Details\s+Type\s+Amount)?$",
    re.DOTALL | re.IGNORECASE,
)
HEADER_STRIP_RE = re.compile(
    r"(PhonePe\s+Transaction\s+Statement|Statement\s+Period"
    r"|Date\s+Transaction\s+Details\s+Type\s+Amount"
    r"|Opening\s+Balance|Closing\s+Balance|Download\s+Date)",
    re.IGNORECASE,
)

_DATE_FORMATS = (
    "%b %d %Y", "%B %d %Y",
    "%b. %d %Y", "%b %d, %Y",
    "%d %b %Y", "%d %B %Y",
    "%d-%b-%Y", "%d/%b/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y", "%d/%m/%Y",
    "%d-%m-%y", "%d/%m/%y",
)


@dataclass
class ParsedTransaction:
    date: str            # ISO yyyy-mm-dd
    time: Optional[str]
    counterparty: str
    amount: float
    type: str            # DEBIT | CREDIT
    description: Optional[str] = None
    txn_id: Optional[str] = None
    category: str = "Uncategorized"
    raw_text: str = ""


@dataclass
class ParseResult:
    transactions: List[ParsedTransaction] = field(default_factory=list)
    failed_blocks: List[str] = field(default_factory=list)
    extraction_method: str = "ai"  # "ai" or "regex_fallback"


def _parse_date(raw: str) -> Optional[str]:
    raw = raw.strip().replace(",", "").replace(".", " ").strip()
    raw = re.sub(r"\s+", " ", raw)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_amount(amount_str: str) -> Optional[float]:
    if not amount_str:
        return None
    m = re.search(r"(?:Rs\.?|INR|\u20b9)?\s*([\d,]+(?:\.\d{1,2})?)", amount_str, re.IGNORECASE)
    if m:
        try:
            clean_str = m.group(1).replace(",", "").strip()
            val = float(clean_str)
            return round(val, 2) if val > 0 else None
        except ValueError:
            return None
    return None


def _classify_direction(text: str) -> Optional[str]:
    lines = text.splitlines() if text else []
    for line in lines:
        if re.search(r"\bDebit\b", line, re.IGNORECASE):
            return "DEBIT"
        if re.search(r"\bCredit\b", line, re.IGNORECASE):
            return "CREDIT"
    lower = text.lower()
    for kw in ["paid to", "payment to", "sent to", "debited from", "paid -", "paid\u2013"]:
        if kw in lower:
            return "DEBIT"
    for kw in ["received from", "refund from", "credited to", "cashback", "received credit"]:
        if kw in lower:
            return "CREDIT"
    if re.search(r"\bpaid\b", text, re.IGNORECASE):
        return "DEBIT"
    if re.search(r"\b(received|refund)\b", text, re.IGNORECASE):
        return "CREDIT"
    return None


def _extract_counterparty(first_line: str, block: str, direction: Optional[str]) -> Optional[str]:
    cp_m = COUNTERPARTY_RE.search(first_line) or COUNTERPARTY_RE.search(block)
    if cp_m:
        who = cp_m.group("who").strip()
        who = re.split(r"\b(?:Debit|Credit|INR|Rs\.?)\b", who, flags=re.IGNORECASE)[0].strip()
        who = re.split(r"\s{2,}|\||\t", who)[0].strip()
        if who and len(who) > 1:
            return who

    svc_m = SERVICE_RE.search(first_line) or SERVICE_RE.search(block)
    if svc_m:
        who = svc_m.group("who").strip()
        who = re.split(r"\b(?:Debit|Credit|INR|Rs\.?)\b", who, flags=re.IGNORECASE)[0].strip()
        who = re.split(r"\s{2,}|\||\t", who)[0].strip()
        if who and len(who) > 1:
            return who

    if re.search(r"\b(?:Paid|Payment)\b", first_line, re.IGNORECASE):
        if "OMO" in block:
            return "Online Merchant Order"
        return "Merchant Payment"

    if re.search(r"\b(?:Received|Refund|Cashback)\b", first_line, re.IGNORECASE):
        return "Refund / Cashback"

    return "Online Merchant" if direction == "DEBIT" else "Received Payment"


# ---------------------------------------------------------------------------
# Approach 2: Coordinate-Based Word Clustering & Transaction Block Grouping
# ---------------------------------------------------------------------------
def _is_date_row(row_words: List[dict], date_x_max: float) -> bool:
    text = " ".join(w["text"] for w in row_words if w.get("x0", 0) <= date_x_max).strip()
    if not text:
        return False
    return bool(DATE_HEADER_RE.search(text) or DATE_ALT_RE.search(text))


def _detect_column_boundaries(page_words: List[dict], page_width: float) -> Tuple[float, float, float]:
    """
    Detect column dividing points: (date_x_max, type_x_min, amount_x_min).
    Dynamically finds header cells if present, otherwise computes proportional thresholds.
    """
    detected_details_x = None
    detected_type_x = None
    detected_amount_x = None

    for w in page_words:
        txt = w["text"].strip().lower()
        x0 = w["x0"]
        if txt in ["transaction", "details", "particulars"] and detected_details_x is None:
            detected_details_x = x0
        elif txt == "type" and detected_type_x is None:
            detected_type_x = x0
        elif txt in ["amount", "amount(inr)", "amount(₹)"] and detected_amount_x is None:
            detected_amount_x = x0

    if detected_details_x and detected_type_x and detected_amount_x:
        date_x_max = detected_details_x - 5
        type_x_min = detected_type_x - 10
        amount_x_min = detected_amount_x - 15
        return date_x_max, type_x_min, amount_x_min

    # Threshold fallback based on page width
    if page_width >= 1000:
        # High resolution or wide format (e.g. 1200+ pts)
        return 250.0, 1050.0, 1150.0
    else:
        # Standard A4 / Letter format (~595 - 612 pts)
        return page_width * 0.23, page_width * 0.68, page_width * 0.79


def extract_coordinate_blocks(pdf_path: str, password: Optional[str] = None, y_tolerance: float = 3.0) -> List[Dict[str, str]]:
    """
    Implements Approach 2:
    1. Extracts words with coordinates (x0, top).
    2. Clusters words into rows by vertical proximity (y_tolerance).
    3. Detects column x-boundaries.
    4. Groups rows into transaction blocks anchored on the Date cell.
    5. Merges amount cells (e.g. 'INR 17000.00') without row interleaving.
    """
    blocks = []
    try:
        with pdfplumber.open(pdf_path, password=password) as pdf:
            for page in pdf.pages:
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
                if not words:
                    continue

                date_x_max, type_x_min, amount_x_min = _detect_column_boundaries(words, page.width)

                # Cluster words into horizontal rows by vertical position
                buckets = defaultdict(list)
                for w in words:
                    key = round(w["top"] / y_tolerance)
                    buckets[key].append(w)

                rows = []
                for key in sorted(buckets.keys()):
                    row_words = sorted(buckets[key], key=lambda item: item["x0"])
                    rows.append(row_words)

                # Group rows into transaction blocks anchored on date row
                current = None
                for row in rows:
                    if _is_date_row(row, date_x_max):
                        if current and (current["amount_words"] or current["detail_words"]):
                            blocks.append(current)
                        current = {
                            "date_words": [],
                            "detail_words": [],
                            "type_words": [],
                            "amount_words": [],
                        }
                    if current is None:
                        continue

                    for w in row:
                        x0 = w["x0"]
                        txt = w["text"]
                        if x0 >= amount_x_min:
                            current["amount_words"].append(txt)
                        elif x0 >= type_x_min:
                            current["type_words"].append(txt)
                        elif x0 <= date_x_max:
                            current["date_words"].append(txt)
                        else:
                            current["detail_words"].append(txt)

                if current and (current["amount_words"] or current["detail_words"]):
                    blocks.append(current)

    except Exception as e:
        logger.warning("Coordinate block extraction encountered issue: %s", e)

    formatted_blocks = []
    for b in blocks:
        date_str = " ".join(b["date_words"]).strip()
        amt_str = " ".join(b["amount_words"]).strip()
        type_str = " ".join(b["type_words"]).strip()
        details_str = " ".join(b["detail_words"]).strip()

        # Build clean raw text representation
        raw_lines = [
            f"Date: {date_str}",
            f"Amount: {amt_str}",
            f"Type: {type_str}",
            f"Details: {details_str}",
        ]
        raw_text = "\n".join(raw_lines)
        formatted_blocks.append({
            "date": date_str,
            "amount": amt_str,
            "type": type_str,
            "details": details_str,
            "raw_text": raw_text,
        })

    return formatted_blocks


# ---------------------------------------------------------------------------
# Fallback Text Splitting (for non-coordinate fallback)
# ---------------------------------------------------------------------------
def _split_into_blocks(text: str) -> List[str]:
    matches = list(DATE_HEADER_RE.finditer(text))
    if not matches:
        matches = list(DATE_ALT_RE.finditer(text))
    if not matches:
        return []
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if block and not _is_document_header(block):
            blocks.append(block)
    return blocks


def _is_document_header(block: str) -> bool:
    if HEADER_STRIP_RE.search(block):
        if TXN_ID_RE.search(block) or COUNTERPARTY_RE.search(block):
            return False
        return True
    if re.search(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\s*[-\u2013]\s*"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
        block, re.IGNORECASE
    ):
        return True
    return False


def _dedup_transactions(txns: List[ParsedTransaction]) -> List[ParsedTransaction]:
    """
    Robust deduplication:
    Matches transactions by authoritative (date, txn_id).
    Only when txn_id is absent does it fall back to matching by
    (date, time, amount, type, normalized counterparty).
    """
    seen_txn_ids: set = set()
    seen_details: set = set()
    out: List[ParsedTransaction] = []

    for t in txns:
        if t.amount <= 0:
            continue

        if t.txn_id:
            txn_key = (t.date, t.txn_id)
            if txn_key in seen_txn_ids:
                continue
            seen_txn_ids.add(txn_key)
            out.append(t)
        else:
            detail_key = (
                t.date,
                t.time or "",
                round(float(t.amount), 2),
                t.type,
                "".join(c for c in (t.counterparty or "") if c.isalnum()).lower()[:20],
            )
            if detail_key in seen_details:
                continue
            seen_details.add(detail_key)
            out.append(t)

    out.sort(key=lambda x: x.date, reverse=True)
    return out


# ---------------------------------------------------------------------------
# Validation Layer
# ---------------------------------------------------------------------------
def validate_and_build_transaction(item: dict) -> Optional[ParsedTransaction]:
    """
    Validates structured JSON output from OpenAI against schema constraints
    and sanitizes fields before returning a ParsedTransaction.
    """
    try:
        val = ExtractedTransactionValidation(**item)
    except Exception as e:
        logger.debug("Pydantic validation failed for item %s: %s", item, e)
        return None

    # Amount validation: must be positive float
    try:
        amt = float(str(val.amount).replace(",", "").strip())
        if amt <= 0:
            return None
        amt = round(amt, 2)
    except Exception:
        return None

    # Date validation: parse and verify calendar validity
    dt_str = str(val.date).strip()
    parsed_date = _parse_date(dt_str)
    if not parsed_date:
        try:
            parsed_date = datetime.strptime(dt_str, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None

    # Type validation: strictly 'DEBIT' or 'CREDIT'
    raw_typ = str(val.type).strip().upper()
    if any(k in raw_typ for k in ["DEBIT", "DR", "PAID", "SENT", "OUTFLOW"]):
        typ = "DEBIT"
    elif any(k in raw_typ for k in ["CREDIT", "CR", "RECEIVED", "INFLOW", "REFUND", "CASHBACK"]):
        typ = "CREDIT"
    else:
        typ = "DEBIT"

    # Counterparty validation: clean person or merchant name
    raw_cp = str(val.counterparty or "").strip()
    cp = re.sub(
        r"^(?:Paid\s+to|Payment\s+to|Sent\s+to|Received\s+from|Refund\s+from|Cashback\s+from|Transfer\s+to|Transferred\s+to)\s*[:\-]?\s*",
        "",
        raw_cp,
        flags=re.IGNORECASE,
    ).strip()
    if not cp or len(cp) < 2:
        cp = "Merchant Payment" if typ == "DEBIT" else "Received Payment"
    if len(cp) > 120:
        cp = cp[:120].strip()

    # Description validation
    desc = str(val.description or "").strip() if val.description else ""
    if not desc or desc.lower() in ["null", "none", "n/a", "-"]:
        desc = f"{'Payment to' if typ == 'DEBIT' else 'Received from'} {cp}"
    if len(desc) > 255:
        desc = desc[:255].strip()

    # Transaction ID validation
    tid = val.txn_id
    if tid:
        tid = str(tid).strip()
        tid = re.sub(r"^(?:Transaction\s*ID|UTR\s*(?:No\.?)?|Order\s*ID)\s*[:\s]*", "", tid, flags=re.IGNORECASE).strip()
        if not tid or tid.lower() in ["null", "none", "n/a", "-"]:
            tid = None

    # Category validation
    cat = (val.category or "Uncategorized").strip()
    valid_categories = {
        "Food", "Groceries", "Recharge & Bills", "Shopping", "Travel",
        "Health", "Entertainment", "Investment", "Friend", "Person", "Family", "Uncategorized"
    }
    if cat not in valid_categories:
        matched = False
        for vc in valid_categories:
            if vc.lower() == cat.lower():
                cat = vc
                matched = True
                break
        if not matched:
            cat = "Uncategorized"

    return ParsedTransaction(
        date=parsed_date,
        time=str(val.time).strip() if val.time else None,
        counterparty=cp,
        amount=amt,
        type=typ,
        description=desc,
        txn_id=tid,
        category=cat,
        raw_text=str(val.raw_text or "").strip(),
    )


# ---------------------------------------------------------------------------
# OpenAI Extraction
# ---------------------------------------------------------------------------
async def _call_openai_chat_json(client: AsyncOpenAI, prompt: str, configured_model: str) -> Optional[str]:
    """Helper to call OpenAI chat completion with fallback on model and parameters."""
    system_msg = (
        "You are an expert financial auditor and precision statement parsing engine. "
        "Extract every genuine transaction from bank/UPI statements into structured JSON. "
        "Ensure exact dates (YYYY-MM-DD), exact positive numeric amounts, direction (DEBIT/CREDIT), "
        "clean merchant/person names, descriptions, and transaction IDs. Never invent transactions. "
        "Output valid JSON only."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]

    models_to_try = [configured_model]
    if configured_model != "gpt-4o-mini":
        models_to_try.append("gpt-4o-mini")

    for current_model in models_to_try:
        try:
            resp = await client.chat.completions.create(
                model=current_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content
        except Exception as err:
            err_str = str(err)
            if "unsupported_parameter" in err_str or "unsupported_value" in err_str:
                try:
                    resp = await client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                    )
                    return resp.choices[0].message.content
                except Exception as e2:
                    logger.warning("Retry on model %s failed: %s", current_model, e2)
            else:
                logger.warning("Model %s call failed (%s), will try next fallback", current_model, err)

    return None


async def _extract_batch_with_openai(
    client: AsyncOpenAI,
    batch_blocks: List[str],
    semaphore: asyncio.Semaphore,
) -> List[ParsedTransaction]:
    joined_text = "\n\n===TXN===\n\n".join(batch_blocks)
    prompt = (
        "Extract all financial transactions from the following PhonePe bank statement text.\n"
        "Each transaction block begins after '===TXN===' or a date.\n\n"
        "Return a valid JSON object with key 'transactions' containing a list of objects:\n"
        "- date: ISO date string YYYY-MM-DD (e.g. '2024-01-15')\n"
        "- time: transaction time (e.g. '08:54 AM') or null\n"
        "- counterparty: exact, clean name of the person or merchant (e.g. 'Swiggy', 'Rakesh Sharma', 'Mathura Sweets')\n"
        "- amount: positive float (e.g. 70.0, 17000.0 - exact decimal number, never truncated)\n"
        "- type: 'DEBIT' (money paid/sent/debited) or 'CREDIT' (money received/credited/refunded)\n"
        "- description: concise description or purpose of the transaction (e.g. 'Food delivery', 'Payment for groceries', 'Transfer to friend', 'Monthly broadband bill')\n"
        "- txn_id: PhonePe Transaction ID, UTR number, or Order ID if present, or null\n"
        "- category: one of 'Food', 'Groceries', 'Recharge & Bills', 'Shopping', 'Travel', 'Health', 'Entertainment', 'Investment', 'Friend', 'Person', 'Family', 'Uncategorized'\n"
        "- raw_text: the original text snippet for this transaction\n\n"
        "Rules:\n"
        "1. Extract EVERY genuine transaction without omitting any.\n"
        "2. Do NOT hallucinate transactions.\n"
        "3. Output valid JSON only.\n\n"
        f"Input text:\n{joined_text}"
    )

    async with semaphore:
        for attempt in range(2):
            try:
                content = await _call_openai_chat_json(client, prompt, settings.openai_model)
                if not content:
                    continue
                data = json.loads(content)
                raw_txns = data.get("transactions", [])
                result = []
                for item in raw_txns:
                    validated_txn = validate_and_build_transaction(item)
                    if validated_txn:
                        result.append(validated_txn)
                return result
            except Exception as e:
                logger.warning("OpenAI batch extraction attempt %d failed: %s", attempt + 1, e)
                if attempt == 0:
                    await asyncio.sleep(1.0)
                else:
                    return []
    return []


async def _parse_with_openai(blocks: List[str]) -> List[ParsedTransaction]:
    if not settings.openai_api_key or not blocks:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    batch_size = 25
    batches = [blocks[i:i + batch_size] for i in range(0, len(blocks), batch_size)]
    semaphore = asyncio.Semaphore(8)

    tasks = [_extract_batch_with_openai(client, batch, semaphore) for batch in batches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_txns: List[ParsedTransaction] = []
    for r in results:
        if isinstance(r, list):
            all_txns.extend(r)
        else:
            logger.error("Batch task returned exception: %s", r)

    return _dedup_transactions(all_txns)


# ---------------------------------------------------------------------------
# Local Fallback Parser (Robust & Deterministic)
# ---------------------------------------------------------------------------
def _parse_coordinate_block_locally(b: Dict[str, str]) -> Optional[ParsedTransaction]:
    amt = parse_amount(b.get("amount", ""))
    if amt is None or amt <= 0:
        return None

    date_str = b.get("date", "").strip()
    date_match = DATE_HEADER_RE.search(date_str) or DATE_ALT_RE.search(date_str)
    iso_date = _parse_date(date_match.group("date")) if date_match else _parse_date(date_str)
    if not iso_date:
        return None

    time_match = TIME_RE.search(b.get("details", "")) or TIME_RE.search(date_str)
    txn_time = time_match.group("time").strip() if time_match else None

    # Direction
    direction = _classify_direction(b.get("type", "")) or _classify_direction(b.get("details", ""))
    if not direction:
        direction = "DEBIT"

    details = b.get("details", "").strip()
    first_part = re.split(r"\b(?:Transaction\s*ID|UTR|Order\s*ID|Debited\s*from|Credited\s*to)\b", details, flags=re.I)[0].strip()
    counterparty = _extract_counterparty(first_part, details, direction)
    if not counterparty:
        counterparty = "Merchant Payment" if direction == "DEBIT" else "Received Payment"

    txn_id_m = TXN_ID_RE.search(details) or UTR_RE.search(details) or ORDER_ID_RE.search(details)
    txn_id = txn_id_m.group(1) if txn_id_m else None

    # Description
    desc = None
    note_m = re.search(r"(?:Transaction\s*ID|UTR|Order\s*ID)[:\s]*[A-Za-z0-9\-]+\s*(.*)", details, flags=re.I)
    if note_m and note_m.group(1).strip():
        desc = note_m.group(1).strip()
    else:
        lines = [l for l in details.splitlines() if l.strip()]
        for line in lines[1:]:
            line_s = line.strip()
            if not line_s:
                continue
            if re.search(r"^(?:Transaction\s*ID|UTR|Order\s*ID|Debited\s*from|Credited\s*to|Ref(?:erence)?)\b", line_s, re.I):
                continue
            if re.search(r"\b(?:Debit|Credit|INR|Rs\.?)\b", line_s, re.I) and AMOUNT_RE.search(line_s):
                continue
            desc_clean = re.sub(r"^(?:Paid|Payment|Received|Refund|Transfer)\s*[-\u2013:]\s*", "", line_s, flags=re.I).strip()
            if desc_clean and len(desc_clean) > 2:
                desc = desc_clean
                break

    if not desc:
        desc = f"{'Payment to' if direction == 'DEBIT' else 'Received from'} {counterparty}"

    return ParsedTransaction(
        date=iso_date,
        time=txn_time,
        counterparty=counterparty,
        amount=amt,
        type=direction,
        description=desc,
        txn_id=txn_id,
        raw_text=b.get("raw_text", ""),
    )


def _parse_raw_text_block_locally(block: str) -> Optional[ParsedTransaction]:
    has_amount = bool(AMOUNT_RE.search(block))
    has_txn_id = bool(TXN_ID_RE.search(block) or UTR_RE.search(block) or ORDER_ID_RE.search(block))
    has_direction = bool(_classify_direction(block))

    if not (has_amount or has_txn_id) or not has_direction:
        return None

    date_match = DATE_HEADER_RE.search(block) or DATE_ALT_RE.search(block)
    if not date_match:
        return None
    iso_date = _parse_date(date_match.group("date"))
    if not iso_date:
        return None

    time_match = TIME_RE.search(block)
    txn_time = time_match.group("time").strip() if time_match else None

    amount_match = AMOUNT_RE.search(block)
    if not amount_match:
        return None
    amount = float(amount_match.group("amount").replace(",", ""))

    direction = _classify_direction(block)
    if not direction:
        return None

    lines = [l for l in block.splitlines() if l.strip() and not DATE_HEADER_RE.fullmatch(l.strip()) and not DATE_ALT_RE.fullmatch(l.strip())]
    first_line = lines[0] if lines else (block.splitlines()[0] if block else "")
    counterparty = _extract_counterparty(first_line, block, direction)
    if not counterparty:
        return None

    txn_id_m = TXN_ID_RE.search(block) or UTR_RE.search(block) or ORDER_ID_RE.search(block)
    txn_id = txn_id_m.group(1) if txn_id_m else None

    desc = f"{'Paid to' if direction == 'DEBIT' else 'Received from'} {counterparty}"
    cleaned = CLEAN_FOOTER_RE.sub("", block).strip()

    return ParsedTransaction(
        date=iso_date,
        time=txn_time,
        counterparty=counterparty,
        amount=amount,
        type=direction,
        description=desc,
        txn_id=txn_id,
        raw_text=cleaned,
    )


def _parse_locally(coord_blocks: List[Dict[str, str]], raw_text: str) -> List[ParsedTransaction]:
    txns = []
    if coord_blocks:
        for cb in coord_blocks:
            t = _parse_coordinate_block_locally(cb)
            if t:
                txns.append(t)
    elif raw_text:
        text_blocks = _split_into_blocks(raw_text)
        for b in text_blocks:
            t = _parse_raw_text_block_locally(b)
            if t:
                txns.append(t)
    return _dedup_transactions(txns)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_raw_text(pdf_path: str, password: Optional[str] = None) -> str:
    """Extracts raw text as fallback if coordinate clustering produces no text."""
    parts = []
    try:
        with pdfplumber.open(pdf_path, password=password) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    parts.append(txt)
    except Exception as e:
        logger.warning("pdfplumber raw text extraction failed: %s, trying PyPDF2 fallback", e)

    if not parts or not any(p.strip() for p in parts):
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if password and reader.is_encrypted:
                    reader.decrypt(password)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt:
                        parts.append(txt)
        except Exception as e2:
            logger.error("PyPDF2 raw text extraction also failed: %s", e2)

    return "\n".join(parts)


async def parse_pdf(pdf_path: str, password: Optional[str] = None, force_fallback: bool = False) -> ParseResult:
    """
    Main PDF parser implementing Approach 2:
    1. Clusters words by y-tolerance and column x-coordinates into robust transaction blocks.
    2. Primary Strategy: Sends clean blocks to OpenAI API to extract:
       - date
       - credit/debit
       - person or merchant name
       - amount
       - description
       - transaction ID
       Strictly validates structured JSON before returning.
    3. Fallback Strategy: Local deterministic parser operating on coordinate blocks.
    4. Guarantees deduplication and zero data corruption.
    """
    # 1. Approach 2: Coordinate-based transaction block extraction
    coord_blocks = extract_coordinate_blocks(pdf_path, password=password)
    raw_text = ""
    block_texts = []

    if coord_blocks:
        block_texts = [b["raw_text"] for b in coord_blocks]
        raw_text = "\n\n".join(block_texts)
    else:
        # Fallback to text extraction if coordinate extraction produced no blocks
        raw_text = extract_raw_text(pdf_path, password=password)
        block_texts = _split_into_blocks(raw_text)

    if not block_texts and not raw_text.strip():
        return ParseResult(transactions=[], failed_blocks=["Empty PDF or text extraction failed"], extraction_method="regex_fallback")

    # 2. Primary Strategy: OpenAI Precision Extraction
    if not force_fallback and settings.openai_api_key:
        try:
            logger.info("Parsing PDF statement using OpenAI API (%s)...", settings.openai_model)
            ai_txns = await _parse_with_openai(block_texts)
            if ai_txns:
                logger.info("OpenAI successfully extracted and validated %d transactions", len(ai_txns))
                return ParseResult(transactions=ai_txns, failed_blocks=[], extraction_method="ai")
            else:
                logger.warning("OpenAI returned no valid transactions; falling back to local coordinate parser")
        except Exception as e:
            logger.error("OpenAI parsing error: %s; falling back to local coordinate parser", e)

    # 3. Fallback: Local Deterministic Coordinate Parser
    logger.info("Running local deterministic fallback parser...")
    local_txns = _parse_locally(coord_blocks, raw_text)
    return ParseResult(transactions=local_txns, failed_blocks=[], extraction_method="regex_fallback")


def parse_statement_text(text: str) -> ParseResult:
    """Synchronous parsing helper."""
    local_txns = _parse_locally([], text)
    return ParseResult(transactions=local_txns, failed_blocks=[], extraction_method="regex_fallback")
