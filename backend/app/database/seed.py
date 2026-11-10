from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.config_models import ExternalLink, LedClassificationRule
from app.models.hierarchy import Customer, Region, Zone
from app.models.user import User, UserCustomerPermission


INITIAL_HIERARCHY = {
    "Bangalore (BBMP)": {
        "BOMMANAHALLI": ["Bommanahalli"],
        "EAST": [
            "CV Raman Nagar",
            "Hebbal",
            "Pulakeshi Nagar",
            "Sarvagna Nagar",
            "Shanthi Nagar",
            "Sivaji Nagar",
        ],
    }
}

DEFAULT_LED_RULES = [
    # LED rules
    ("LED", "word", "led"),
    ("LED 40W", "exact", "led"),
    ("LED 60W", "exact", "led"),
    ("LED 90W", "exact", "led"),
    ("LED Street Light", "contains", "led"),
    # Non-LED rules
    ("SVL", "word", "non_led"),
    ("Sodium Vapour", "contains", "non_led"),
    ("Sodium Vapor", "contains", "non_led"),
    ("HPSV", "word", "non_led"),
    ("LPSV", "word", "non_led"),
    ("Conventional", "contains", "non_led"),
    ("Metal Halide", "contains", "non_led"),
    ("CFL", "word", "non_led"),
    ("Fluorescent", "contains", "non_led"),
    ("Halogen", "contains", "non_led"),
    ("Incandescent", "contains", "non_led"),
    ("Mercury Vapour", "contains", "non_led"),
    ("Mercury Vapor", "contains", "non_led"),
]

DEFAULT_EXTERNAL_LINKS = [
    ("om_dashboard", "O&M Dashboard"),
    ("energy_saving_report", "Energy Saving Report"),
]


def seed_initial_data(db: Session) -> None:
    if not settings.seed_default_data:
        return

    # 1. Seed initial Admin account
    admin = db.scalar(select(User).where(User.email == settings.seed_admin_email))
    if admin is None:
        admin = User(
            name=settings.seed_admin_name,
            email=settings.seed_admin_email,
            username=settings.seed_admin_username,
            password_hash=hash_password(settings.seed_admin_password),
            role="admin",
            status="active",
        )
        db.add(admin)
        db.flush()

    # 2. Seed initial Customer, Regions, and Zones
    bbmp_customer: Customer | None = None
    for customer_name, regions_map in INITIAL_HIERARCHY.items():
        customer = db.scalar(select(Customer).where(Customer.customer_name == customer_name))
        if customer is None:
            customer = Customer(customer_name=customer_name, status="active")
            db.add(customer)
            db.flush()
        if customer_name == "Bangalore (BBMP)":
            bbmp_customer = customer

        for region_name, zone_names in regions_map.items():
            region = db.scalar(
                select(Region).where(
                    Region.customer_id == customer.id,
                    Region.region_name == region_name,
                )
            )
            if region is None:
                region = Region(customer_id=customer.id, region_name=region_name, status="active")
                db.add(region)
                db.flush()

            for zone_name in zone_names:
                zone = db.scalar(
                    select(Zone).where(
                        Zone.region_id == region.id,
                        Zone.zone_name == zone_name,
                    )
                )
                if zone is None:
                    db.add(Zone(region_id=region.id, zone_name=zone_name, status="active"))

    # 3. Seed sample Customer user linked to Bangalore (BBMP)
    customer_user = db.scalar(select(User).where(User.email == settings.seed_customer_user_email))
    if customer_user is None:
        customer_user = User(
            name=settings.seed_customer_user_name,
            email=settings.seed_customer_user_email,
            username=settings.seed_customer_user_username,
            password_hash=hash_password(settings.seed_customer_user_password),
            role="customer",
            status="active",
        )
        db.add(customer_user)
        db.flush()

    if bbmp_customer is not None:
        perm = db.scalar(
            select(UserCustomerPermission).where(
                UserCustomerPermission.user_id == customer_user.id,
                UserCustomerPermission.customer_id == bbmp_customer.id,
            )
        )
        if perm is None:
            db.add(
                UserCustomerPermission(
                    user_id=customer_user.id,
                    customer_id=bbmp_customer.id,
                    access_level="read_only",
                )
            )

    # 4. Seed default LED classification rules
    for pattern, match_type, classification in DEFAULT_LED_RULES:
        existing_rule = db.scalar(
            select(LedClassificationRule).where(
                LedClassificationRule.pattern == pattern,
                LedClassificationRule.match_type == match_type,
            )
        )
        if existing_rule is None:
            db.add(
                LedClassificationRule(
                    pattern=pattern,
                    match_type=match_type,
                    classification=classification,
                    is_active=True,
                    created_by=admin.id,
                )
            )

    # 5. Seed configurable external links
    for link_key, link_name in DEFAULT_EXTERNAL_LINKS:
        existing_link = db.scalar(
            select(ExternalLink).where(ExternalLink.link_key == link_key)
        )
        if existing_link is None:
            db.add(
                ExternalLink(
                    link_key=link_key,
                    link_name=link_name,
                    url=None,
                    is_enabled=True,
                    updated_by=admin.id,
                )
            )

    db.commit()

