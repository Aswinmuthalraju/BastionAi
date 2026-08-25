from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.deps import get_current_user
from app.ingest.pipeline import delete_document, get_document, ingest_document, list_documents

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    data_scope: str = Form("refinery_ops"),
    allowed_roles: str = Form("operator,engineer,admin"),
    user: dict = Depends(get_current_user),
):
    if user["role"] != "admin":
        # Only admins may widen visibility beyond the standard operational scope.
        data_scope = "refinery_ops"
        allowed_roles = "operator,engineer,admin"

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB upload limit.")
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    result = ingest_document(
        file_bytes=content,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        data_scope=data_scope,
        allowed_roles=[r.strip() for r in allowed_roles.split(",") if r.strip()],
        uploaded_by=user["user_id"],
    )
    return result


@router.get("/documents")
def list_documents_endpoint(user: dict = Depends(get_current_user)):
    return {"documents": list_documents(user["data_scopes"], user["role"])}


def _assert_visible(doc: dict, user: dict):
    import json as _json
    roles = _json.loads(doc["allowed_roles"])
    scope_ok = "*" in user["data_scopes"] or doc["data_scope"] in user["data_scopes"]
    role_ok = "admin" in user["role"] or user["role"] in roles
    if not (scope_ok and role_ok):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This document is outside your authorized data scope.")


@router.get("/documents/{doc_id}")
def get_document_endpoint(doc_id: str, user: dict = Depends(get_current_user)):
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' does not exist.")
    _assert_visible(doc, user)
    return doc


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str, user: dict = Depends(get_current_user)):
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' does not exist.")
    _assert_visible(doc, user)
    return FileResponse(doc["stored_path"], media_type=doc["content_type"], filename=doc["filename"])


@router.delete("/documents/{doc_id}")
def delete_document_endpoint(doc_id: str, user: dict = Depends(get_current_user)):
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Document '{doc_id}' does not exist.")
    _assert_visible(doc, user)
    deleted = delete_document(doc_id)
    if not deleted:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document.")
    return {"message": "Document deleted successfully", "doc_id": doc_id}

