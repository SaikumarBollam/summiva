from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from celery import Celery

from core.database.database import get_db

from config.settings.settings import settings
from apps.auth.utils import get_current_user
from apps.auth.models import User
from .models import Tag, TaggedDocument
from .schemas import (
    TagCreate,
    TagInDB,
    TagUpdate,
    TaggedDocumentInDB,
    TaggingRequest,
    TaggingResponse
)
from .utils import extract_tags
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson import ObjectId
from src.utils.security import get_authenticated_user_id
from src.database.mongo_session import mongo_db

security = HTTPBearer()
router = APIRouter()
celery = Celery(
    'tagging',
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND)
)

@router.post("/tags", response_model=TagInDB)
async def create_tag(
    tag: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TagInDB:
    db_tag = Tag(
        name=tag.name,
        description=tag.description
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@router.get("/tags", response_model=List[TagInDB])
async def get_tags(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[TagInDB]:
    tags = db.query(Tag)\
        .offset(skip)\
        .limit(limit)\
        .all()
    return tags

@router.post("/tag", response_model=TaggingResponse)
async def tag_text(
    request: TaggingRequest,
    current_user: User = Depends(get_current_user)
) -> TaggingResponse:
    try:
        result = extract_tags(
            request.text,
            max_tags=request.max_tags,
            min_confidence=request.min_confidence
        )
        return TaggingResponse(
            tags=result["tags"],
            processing_time=result["processing_time"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/documents/{document_id}/tag", response_model=TaggedDocumentInDB)
async def tag_document(
    document_id: int,
    tag_id: int,
    confidence_score: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TaggedDocumentInDB:
    # Verify document exists and belongs to user
    document = db.query(Document)\
        .filter(Document.id == document_id)\
        .filter(Document.user_id == current_user.id)\
        .first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Verify tag exists
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    
    # Create tagged document
    tagged_document = TaggedDocument(
        document_id=document_id,
        tag_id=tag_id,
        confidence_score=confidence_score
    )
    db.add(tagged_document)
    db.commit()
    db.refresh(tagged_document)
    return tagged_document 


@router.get("/api/v1/documents/{doc_id}/tags")
def get_tags(doc_id: str, creds: HTTPAuthorizationCredentials = Security(security)):
    user_id = get_authenticated_user_id(creds)
    user_docs = mongo_db["user_docs"].find_one({"user_id": user_id})
    if not user_docs or doc_id not in user_docs.get("doc_ids", []):
        raise HTTPException(status_code=403, detail="Unauthorized")

    doc = mongo_db["docs"].find_one({"_id": ObjectId(doc_id)}, {"tags": 1})
    if not doc or "tags" not in doc:
        raise HTTPException(status_code=404, detail="Tags not found")

    return doc["tags"]
