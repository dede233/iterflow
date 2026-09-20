from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User, Release

router=APIRouter(prefix="/releases",tags=["releases"])


@router.get("")
def list_releases(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),current:User=Depends(require_permission("rd.release.view"))):
    items=db.scalars(select(Release).order_by(Release.released_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":items,"page":page,"page_size":page_size}
