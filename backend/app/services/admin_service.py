from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.config_models import AuditLog, ExternalLink, LedClassificationRule
from app.models.hierarchy import Customer
from app.models.user import User, UserCustomerPermission
from app.schemas.admin import (
    AuditLogOut,
    ExternalLinkOut,
    ExternalLinksBulkUpdate,
    LedRuleCreate,
    LedRuleOut,
    LedRuleUpdate,
    UserCreate,
    UserUpdate,
)
from app.schemas.auth import UserOut
from app.services.audit_service import record_audit_log
from app.services.auth_service import serialize_user


def list_users(db: Session) -> list[UserOut]:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [serialize_user(db, u) for u in users]


def create_user(db: Session, payload: UserCreate, admin_id: int, ip: str | None) -> UserOut:
    email = payload.email.strip().lower()
    username = payload.username.strip().lower() if payload.username and payload.username.strip() else None

    dup = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == email,
                func.lower(User.username) == username if username else False,
            )
        )
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email or username already exists.",
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        status=payload.status,
    )
    db.add(user)
    db.flush()

    if payload.role == "customer" and payload.customer_ids:
        valid_cust_ids = set(
            db.scalars(select(Customer.id).where(Customer.id.in_(payload.customer_ids))).all()
        )
        for cid in valid_cust_ids:
            db.add(
                UserCustomerPermission(
                    user_id=user.id, customer_id=cid, access_level="read_only"
                )
            )

    record_audit_log(
        db,
        user_id=admin_id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        details={"email": email, "role": payload.role, "customer_ids": payload.customer_ids},
        ip_address=ip,
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


def update_user(
    db: Session, user_id: int, payload: UserUpdate, admin_id: int, ip: str | None
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.name is not None:
        user.name = payload.name.strip()

    if payload.email is not None:
        email = payload.email.strip().lower()
        dup = db.scalar(
            select(User).where(func.lower(User.email) == email, User.id != user_id)
        )
        if dup is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use.")
        user.email = email

    if payload.username is not None:
        username = payload.username.strip().lower() or None
        if username is not None:
            dup_u = db.scalar(
                select(User).where(func.lower(User.username) == username, User.id != user_id)
            )
            if dup_u is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Username is already in use."
                )
        user.username = username

    if payload.password:
        user.password_hash = hash_password(payload.password)

    if payload.role is not None:
        user.role = payload.role

    if payload.status is not None:
        if user.id == admin_id and payload.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own active administrator account.",
            )
        user.status = payload.status

    if payload.customer_ids is not None:
        db.query(UserCustomerPermission).filter(
            UserCustomerPermission.user_id == user.id
        ).delete(synchronize_session=False)
        if user.role == "customer" and payload.customer_ids:
            valid_cust_ids = set(
                db.scalars(select(Customer.id).where(Customer.id.in_(payload.customer_ids))).all()
            )
            for cid in valid_cust_ids:
                db.add(
                    UserCustomerPermission(
                        user_id=user.id, customer_id=cid, access_level="read_only"
                    )
                )

    record_audit_log(
        db,
        user_id=admin_id,
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        details={"role": user.role, "status": user.status},
        ip_address=ip,
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


def list_external_links(db: Session) -> list[ExternalLinkOut]:
    rows = db.scalars(select(ExternalLink).order_by(ExternalLink.id.asc())).all()
    return [
        ExternalLinkOut(
            id=r.id,
            link_key=r.link_key,
            link_name=r.link_name,
            url=r.url,
            is_enabled=r.is_enabled,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


def update_external_links(
    db: Session, payload: ExternalLinksBulkUpdate, admin_id: int, ip: str | None
) -> list[ExternalLinkOut]:
    for item in payload.links:
        row = db.scalar(select(ExternalLink).where(ExternalLink.link_key == item.link_key))
        if row is None:
            continue
        if item.link_name is not None:
            row.link_name = item.link_name.strip()
        if item.url is not None:
            clean_url = item.url.strip() or None
            if clean_url is not None and not (
                clean_url.startswith("http://") or clean_url.startswith("https://")
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"External URL for {row.link_name} must start with http:// or https://",
                )
            row.url = clean_url
        if item.is_enabled is not None:
            row.is_enabled = item.is_enabled
        row.updated_by = admin_id

    record_audit_log(
        db,
        user_id=admin_id,
        action="external_links.update",
        entity_type="external_link",
        details={"updated_keys": [i.link_key for i in payload.links]},
        ip_address=ip,
    )
    db.commit()
    return list_external_links(db)


def list_led_rules(db: Session) -> list[LedRuleOut]:
    rules = db.scalars(
        select(LedClassificationRule).order_by(
            LedClassificationRule.classification.asc(),
            LedClassificationRule.id.asc(),
        )
    ).all()
    return [
        LedRuleOut(
            id=r.id,
            pattern=r.pattern,
            match_type=r.match_type,
            classification=r.classification,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in rules
    ]


def create_led_rule(
    db: Session, payload: LedRuleCreate, admin_id: int, ip: str | None
) -> LedRuleOut:
    pat = payload.pattern.strip()
    dup = db.scalar(
        select(LedClassificationRule).where(
            func.lower(LedClassificationRule.pattern) == pat.lower(),
            LedClassificationRule.match_type == payload.match_type,
        )
    )
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A classification rule with this pattern and match type already exists.",
        )

    rule = LedClassificationRule(
        pattern=pat,
        match_type=payload.match_type,
        classification=payload.classification,
        is_active=payload.is_active,
        created_by=admin_id,
    )
    db.add(rule)
    db.flush()
    record_audit_log(
        db,
        user_id=admin_id,
        action="led_rule.create",
        entity_type="led_classification_rule",
        entity_id=rule.id,
        details={"pattern": pat, "classification": payload.classification},
        ip_address=ip,
    )
    db.commit()
    db.refresh(rule)
    return LedRuleOut(
        id=rule.id,
        pattern=rule.pattern,
        match_type=rule.match_type,
        classification=rule.classification,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


def update_led_rule(
    db: Session, rule_id: int, payload: LedRuleUpdate, admin_id: int, ip: str | None
) -> LedRuleOut:
    rule = db.get(LedClassificationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LED rule not found.")

    if payload.pattern is not None:
        rule.pattern = payload.pattern.strip()
    if payload.match_type is not None:
        rule.match_type = payload.match_type
    if payload.classification is not None:
        rule.classification = payload.classification
    if payload.is_active is not None:
        rule.is_active = payload.is_active

    record_audit_log(
        db,
        user_id=admin_id,
        action="led_rule.update",
        entity_type="led_classification_rule",
        entity_id=rule.id,
        details={"pattern": rule.pattern, "is_active": rule.is_active},
        ip_address=ip,
    )
    db.commit()
    db.refresh(rule)
    return LedRuleOut(
        id=rule.id,
        pattern=rule.pattern,
        match_type=rule.match_type,
        classification=rule.classification,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


def delete_led_rule(db: Session, rule_id: int, admin_id: int, ip: str | None) -> None:
    rule = db.get(LedClassificationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LED rule not found.")
    record_audit_log(
        db,
        user_id=admin_id,
        action="led_rule.delete",
        entity_type="led_classification_rule",
        entity_id=rule.id,
        details={"pattern": rule.pattern},
        ip_address=ip,
    )
    db.delete(rule)
    db.commit()


def list_audit_logs(db: Session, limit: int = 100) -> list[AuditLogOut]:
    logs = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    ).all()
    user_cache: dict[int, User | None] = {}
    out: list[AuditLogOut] = []
    for log in logs:
        u = None
        if log.user_id is not None:
            if log.user_id not in user_cache:
                user_cache[log.user_id] = db.get(User, log.user_id)
            u = user_cache[log.user_id]
        out.append(
            AuditLogOut(
                id=log.id,
                user_id=log.user_id,
                user_name=u.name if u else None,
                user_email=u.email if u else None,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
        )
    return out

