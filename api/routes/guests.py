from datetime import datetime
import hashlib
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response

from api.common import row_dict, rows_dict
from api.dependencies import get_current_user, require_permission
from api.schemas import CustomerCreate, CustomerUpdate, StatusUpdate
from api.config import settings, SECRET_PLACEHOLDER
from database.customer_db import (
    get_customer_by_id, get_customer_by_mobile, search_customers, get_hotel_guests,
    get_guest_stay_summary, get_guest_booking_summary, get_guest_restaurant_summary,
    get_customer_lifecycle, get_guest_booking_history, get_guest_restaurant_history,
    get_guest_hotels, save_customer, update_customer_record, get_next_customer_id,
    ensure_guest_hotel_relationship, validate_guest_hotel_relationship, set_customer_status,
)
from database.database import get_connection

router = APIRouter(tags=["Guests"])
logger = logging.getLogger(__name__)


_ALLOWED_GUEST_ID_TYPES = {"Aadhaar Card", "Driving Licence", "Voter ID Card", "Passport", "Other Government ID"}
_MAX_GUEST_ID_BYTES = 800 * 1024
_GUEST_ID_STORAGE = Path(__file__).resolve().parents[2] / "data" / "private_guest_documents"


def _guest_document_cipher() -> Fernet:
    # Keep secret values out of logs; emit only safe diagnostic metadata when
    # configuration prevents encrypted identity-document storage.
    env_secret = os.getenv("API_SECRET_KEY")
    secret = str(settings.secret_key or "").strip()
    if not secret or secret == SECRET_PLACEHOLDER or len(secret) < 32:
        logger.error(
            "Guest ID encryption unavailable: env_var_present=%s env_secret_length=%s "
            "configured_secret_length=%s configured_secret_is_placeholder=%s "
            "configured_matches_environment=%s app_environment=%s",
            bool(env_secret and env_secret.strip()),
            len(env_secret.strip()) if env_secret else 0,
            len(secret),
            secret == SECRET_PLACEHOLDER,
            bool(env_secret and env_secret.strip() == secret),
            settings.environment,
        )
        raise HTTPException(status_code=503, detail="Secure ID storage is unavailable. Configure a unique API_SECRET_KEY of at least 32 characters before uploading identity documents.")
    return Fernet(urlsafe_b64encode(hashlib.sha256(("HOTEL_WARE_GUEST_ID:" + secret).encode("utf-8")).digest()))


def _ensure_guest_documents_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS guest_identity_documents (
            document_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            hotel_id INTEGER NOT NULL,
            id_type TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            encrypted_path TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'Pending Verification',
            uploaded_by TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            verified_by TEXT,
            verified_at TEXT
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_guest_identity_customer ON guest_identity_documents(customer_id, hotel_id, uploaded_at DESC)")
    connection.commit()


def _validate_guest_file(filename: str, content: bytes):
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=415, detail="Upload a PDF, JPG, JPEG, or PNG identity document.")
    if not content or len(content) > _MAX_GUEST_ID_BYTES:
        raise HTTPException(status_code=413, detail="Identity document must be between 1 byte and 800 KB.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid JPEG image.")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PNG image.")
    return {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[suffix]


@router.get("/customers")
def list_customers(
    search: str | None = None,
    search_field: str = "all",
    guest_status: str | None = None,
    date_type: str = "created",
    date_from: str | None = None,
    date_to: str | None = None,
    user=Depends(get_current_user),
):
    if search or guest_status or date_from or date_to or date_type != "any":
        try:
            rows = search_customers(
                search, search_field, guest_status,
                hotel_id=user["hotel_id"],
                date_type=date_type, date_from=date_from, date_to=date_to,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        rows = get_hotel_guests(user["hotel_id"])
    return {"data": rows_dict(rows)}


@router.get("/customers/lookup/mobile")
def customer_lookup_by_mobile(mobile: str = Query(min_length=5, max_length=30), user=Depends(get_current_user)):
    """Find an existing Guest Master record by exact mobile number."""
    customer = get_customer_by_mobile(mobile)
    if customer is None:
        return {"data": None, "found": False}
    cid = str(customer["customer_id"] if not isinstance(customer, dict) else customer.get("customer_id") or "").strip().upper()
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError:
        return {"data": None, "found": False}
    return {"data": row_dict(customer), "found": True, "message": "Existing guest found. Reuse this Guest Profile."}


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: str, user=Depends(get_current_user)):
    cid = customer_id.strip().upper()
    customer = get_customer_by_id(cid)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    connection = get_connection()
    try:
        feedback_rows = connection.execute(
            "SELECT * FROM feedback WHERE customer_id=? AND hotel_id=? ORDER BY feedback_date DESC, feedback_time DESC, feedback_id DESC",
            (cid, user["hotel_id"]),
        ).fetchall()
    finally:
        connection.close()
    return {"data": {
        "customer": row_dict(customer),
        "stay_summary": get_guest_stay_summary(cid, user["hotel_id"]),
        "booking_summary": get_guest_booking_summary(cid, user["hotel_id"]),
        "restaurant_summary": get_guest_restaurant_summary(cid, user["hotel_id"]),
        "lifecycle": get_customer_lifecycle(cid, user["hotel_id"]),
        "booking_history": rows_dict(get_guest_booking_history(cid, user["hotel_id"])),
        "order_history": rows_dict(get_guest_restaurant_history(cid, user["hotel_id"])),
        "feedback_history": rows_dict(feedback_rows),
        "hotel_relationships": rows_dict(get_guest_hotels(cid)),
    }}


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerCreate, user=Depends(require_permission("Customers", "Create"))):
    existing = get_customer_by_mobile(payload.customer_mobile)
    if existing is not None:
        existing_id = str(existing["customer_id"] if not isinstance(existing, dict) else existing.get("customer_id") or "").strip().upper()
        try:
            validate_guest_hotel_relationship(existing_id, user["hotel_id"])
        except ValueError:
            raise HTTPException(status_code=409, detail="This mobile number is already linked to a Guest Profile. Ask an administrator to resolve the cross-hotel record before creating another profile.")
        raise HTTPException(status_code=409, detail=f"Existing guest found (Customer ID: {existing_id}). Please use the existing Guest Profile instead of creating a duplicate.")
    customer_id = payload.customer_id or get_next_customer_id()
    save_customer(customer_id, payload.customer_name, payload.customer_mobile, payload.customer_email, payload.customer_address, datetime.now(), payload.customer_city, payload.customer_state, payload.customer_country, payload.customer_pincode, payload.guest_status, 1, payload.preferences, payload.special_requests, payload.guest_notes, payload.government_id_type, payload.government_id_status)
    try:
        ensure_guest_hotel_relationship(customer_id, user["hotel_id"])
    except Exception:
        raise
    return {"data": row_dict(get_customer_by_id(customer_id)), "message": "Customer created successfully."}


@router.patch("/customers/{customer_id}/status")
def update_customer_status(customer_id: str, payload: StatusUpdate, user=Depends(require_permission("Customers", "Update"))):
    status = str(payload.status or "").strip()
    if status not in {"Active", "Inactive", "Blacklisted"}:
        raise HTTPException(status_code=400, detail="Invalid guest status.")
    try:
        set_customer_status(customer_id, status, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"data": row_dict(get_customer_by_id(customer_id)), "message": f"Guest status changed to {status}."}


@router.put("/customers/{customer_id}")
def update_customer(customer_id: str, payload: CustomerUpdate, user=Depends(require_permission("Customers", "Update"))):
    update_customer_record(customer_id, payload.customer_name, payload.customer_mobile, payload.customer_email, payload.customer_address, payload.customer_city, payload.customer_state, payload.customer_country, payload.customer_pincode, payload.guest_status, payload.is_active, payload.preferences, payload.special_requests, payload.guest_notes, user["hotel_id"])
    return {"data": row_dict(get_customer_by_id(customer_id)), "message": "Customer updated successfully."}


@router.post("/customers/{customer_id}/government-id", status_code=201)
async def upload_guest_government_id(
    customer_id: str,
    id_type: str = Form(...),
    document: UploadFile = File(...),
    user=Depends(require_permission("Customers", "Update")),
):
    """Store a guest identity document encrypted at rest and linked to the existing Guest Master."""
    cid = customer_id.strip().upper()
    if id_type not in _ALLOWED_GUEST_ID_TYPES:
        raise HTTPException(status_code=400, detail="Select a supported Government ID type.")
    customer = get_customer_by_id(cid)
    if customer is None:
        raise HTTPException(status_code=404, detail="Guest profile not found.")
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Guest profile not found for this hotel.") from exc

    raw = await document.read(_MAX_GUEST_ID_BYTES + 1)
    media_type = _validate_guest_file(document.filename or "identity-document", raw)
    cipher = _guest_document_cipher()
    document_id = str(uuid.uuid4())
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(document.filename or "identity-document").name)[:160] or "identity-document"
    _GUEST_ID_STORAGE.mkdir(parents=True, exist_ok=True)
    encrypted_path = _GUEST_ID_STORAGE / f"{document_id}.enc"
    encrypted_path.write_bytes(cipher.encrypt(raw))

    connection = get_connection()
    try:
        _ensure_guest_documents_table(connection)
        connection.execute(
            "INSERT INTO guest_identity_documents (document_id, customer_id, hotel_id, id_type, original_filename, media_type, encrypted_path, verification_status, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending Verification', ?, ?)",
            (document_id, cid, user["hotel_id"], id_type, safe_name, media_type, str(encrypted_path), user["user_id"], datetime.now().isoformat(timespec="seconds")),
        )
        connection.execute("UPDATE customers SET government_id_type=?, government_id_status='Pending Verification', updated_time=? WHERE customer_id=?", (id_type, datetime.now().isoformat(timespec="seconds"), cid))
        connection.commit()
    except Exception:
        connection.rollback()
        try:
            encrypted_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        connection.close()
    return {"data": {"document_id": document_id, "customer_id": cid, "id_type": id_type, "verification_status": "Pending Verification", "filename": safe_name, "uploaded_at": datetime.now().isoformat(timespec="seconds")}, "message": "Identity document encrypted and uploaded. Verification is pending."}


@router.get("/customers/{customer_id}/government-id")
def list_guest_government_ids(customer_id: str, user=Depends(require_permission("Customers", "View"))):
    cid = customer_id.strip().upper()
    if get_customer_by_id(cid) is None:
        raise HTTPException(status_code=404, detail="Guest profile not found.")
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Guest profile not found for this hotel.") from exc
    connection = get_connection()
    try:
        _ensure_guest_documents_table(connection)
        rows = connection.execute("SELECT document_id, customer_id, id_type, original_filename, media_type, verification_status, uploaded_by, uploaded_at, verified_by, verified_at FROM guest_identity_documents WHERE customer_id=? AND hotel_id=? ORDER BY uploaded_at DESC", (cid, user["hotel_id"])).fetchall()
        return {"data": rows_dict(rows)}
    finally:
        connection.close()


@router.get("/customers/{customer_id}/government-id/{document_id}/download")
def download_guest_government_id(customer_id: str, document_id: str, user=Depends(require_permission("Customers", "View"))):
    cid = customer_id.strip().upper()
    try:
        validate_guest_hotel_relationship(cid, user["hotel_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Guest profile not found for this hotel.") from exc
    connection = get_connection()
    try:
        _ensure_guest_documents_table(connection)
        row = connection.execute("SELECT * FROM guest_identity_documents WHERE document_id=? AND customer_id=? AND hotel_id=?", (document_id, cid, user["hotel_id"])).fetchone()
    finally:
        connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Identity document not found.")
    try:
        encrypted = Path(row["encrypted_path"]).read_bytes()
        content = _guest_document_cipher().decrypt(encrypted)
    except (OSError, InvalidToken) as exc:
        raise HTTPException(status_code=500, detail="Identity document could not be securely decrypted.") from exc
    return Response(content=content, media_type=row["media_type"], headers={"Content-Disposition": f'attachment; filename="{row["original_filename"]}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
