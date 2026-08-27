from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mua_platform.business.models import (
    DEFAULT_BUSINESS_ID,
    DEFAULT_BUSINESS_NAME,
    BusinessSpace,
    utc_now,
)
from mua_platform.business.schemas import BusinessSpaceCreate, BusinessSpaceUpdate


def business_name_key(name: str) -> str:
    return " ".join(name.strip().casefold().split())


class BusinessSpaceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_default_business(self) -> BusinessSpace:
        existing = self.db.get(BusinessSpace, DEFAULT_BUSINESS_ID)
        if existing is not None:
            return existing
        business = BusinessSpace(
            id=DEFAULT_BUSINESS_ID,
            name=DEFAULT_BUSINESS_NAME,
            name_key=business_name_key(DEFAULT_BUSINESS_NAME),
            description=None,
            is_default=True,
            created_by="system",
        )
        self.db.add(business)
        self.db.flush()
        return business

    def default_business(self) -> BusinessSpace:
        business = self.db.get(BusinessSpace, DEFAULT_BUSINESS_ID)
        if business is None:
            business = self.ensure_default_business()
            self.db.commit()
            self.db.refresh(business)
        return business

    def get_active(self, business_id: str) -> BusinessSpace | None:
        return self.db.scalar(
            select(BusinessSpace).where(
                BusinessSpace.id == business_id,
                BusinessSpace.archived_at.is_(None),
            )
        )

    def list_active(self) -> list[BusinessSpace]:
        self.ensure_default_business()
        return list(
            self.db.scalars(
                select(BusinessSpace)
                .where(BusinessSpace.archived_at.is_(None))
                .order_by(BusinessSpace.is_default.desc(), BusinessSpace.created_at)
            )
        )

    def create(
        self,
        payload: BusinessSpaceCreate,
        *,
        created_by: str,
    ) -> BusinessSpace:
        business = BusinessSpace(
            id=f"biz_{uuid4().hex}",
            name=payload.name,
            name_key=business_name_key(payload.name),
            description=payload.description,
            is_default=False,
            task_concurrency_limit=payload.task_concurrency_limit,
            created_by=created_by,
        )
        try:
            self.db.add(business)
            self.db.flush()
            return business
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("business_name_exists") from exc

    def update(
        self,
        business_id: str,
        payload: BusinessSpaceUpdate,
    ) -> BusinessSpace | None:
        business = self.get_active(business_id)
        if business is None:
            return None
        if payload.name is not None:
            business.name = payload.name
            business.name_key = business_name_key(payload.name)
        if "description" in payload.model_fields_set:
            business.description = payload.description
        if payload.task_concurrency_limit is not None:
            business.task_concurrency_limit = payload.task_concurrency_limit
        try:
            self.db.commit()
            self.db.refresh(business)
            return business
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("business_name_exists") from exc

    def archive(self, business_id: str) -> BusinessSpace | None:
        business = self.get_active(business_id)
        if business is None:
            return None
        if business.is_default:
            raise ValueError("default_business_cannot_archive")
        business.archived_at = utc_now()
        self.db.commit()
        self.db.refresh(business)
        return business
