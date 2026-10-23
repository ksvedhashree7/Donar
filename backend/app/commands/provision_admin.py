from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.security import hash_password
from app.models import Role, RoleName, User, UserStatus
from app.services.audit import record_audit_event


def provision_admin() -> None:
    settings = get_settings()
    email = (settings.admin_email or "").strip().lower()
    username = (settings.admin_username or "").strip()
    password = settings.admin_password.get_secret_value() if settings.admin_password else ""
    if not email or not username or len(password) < 12:
        raise SystemExit(
            "Set ADMIN_EMAIL, ADMIN_USERNAME, and a 12+ character "
            "ADMIN_PASSWORD before provisioning."
        )

    with SessionFactory.begin() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role.name != RoleName.ADMIN:
                raise SystemExit(
                    "The configured admin email already belongs to a non-admin account."
                )
            print("Administrator account already exists; no credentials were changed.")
            return
        if db.scalar(select(User.id).where(User.username == username)):
            raise SystemExit(
                "The configured admin username is already in use."
            )

        role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN))
        if role is None:
            role = Role(name=RoleName.ADMIN, description="Platform administrator")
            db.add(role)
            db.flush()

        now = datetime.now(timezone.utc)
        user = User(
            role_id=role.id,
            username=username,
            email=email,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified_at=now,
        )
        db.add(user)
        db.flush()
        record_audit_event(
            db,
            actor_id=None,
            actor_role="SYSTEM",
            action="ADMIN_ACCOUNT_PROVISIONED",
            resource_type="user",
            resource_id=str(user.id),
            purpose="initial_admin_setup",
            ip_address=None,
            user_agent=None,
            success=True,
        )

    print("Administrator account provisioned.")


if __name__ == "__main__":
    provision_admin()
