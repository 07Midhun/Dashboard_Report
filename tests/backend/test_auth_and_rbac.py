from app.core.config import settings


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_admin_login_by_email_and_username(client):
    # Login via email
    resp_email = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_email,
            "password": settings.seed_admin_password,
            "login_type": "admin",
        },
    )
    assert resp_email.status_code == 200
    data = resp_email.json()
    assert data["user"]["role"] == "admin"
    assert data["access_token"]

    # Login via username
    resp_user = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_username,
            "password": settings.seed_admin_password,
            "login_type": "admin",
        },
    )
    assert resp_user.status_code == 200
    assert resp_user.json()["user"]["username"] == settings.seed_admin_username


def test_customer_login_and_portal_role_mismatch_rejected(client):
    # Customer cannot log in via admin tab
    resp_mismatch = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_customer_user_email,
            "password": settings.seed_customer_user_password,
            "login_type": "admin",
        },
    )
    assert resp_mismatch.status_code == 403

    # Admin cannot log in via customer tab
    resp_admin_mismatch = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_email,
            "password": settings.seed_admin_password,
            "login_type": "customer",
        },
    )
    assert resp_admin_mismatch.status_code == 403

    # Valid customer login
    resp_ok = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_customer_user_email,
            "password": settings.seed_customer_user_password,
            "login_type": "customer",
        },
    )
    assert resp_ok.status_code == 200
    user = resp_ok.json()["user"]
    assert user["role"] == "customer"
    assert any(c["customer_name"] == "Bangalore (BBMP)" for c in user["assigned_customers"])


def test_me_and_logout_revokes_token(client):
    login_resp = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_email,
            "password": settings.seed_admin_password,
            "login_type": "admin",
        },
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == settings.seed_admin_email

    logout_resp = client.post("/api/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # Token must now be rejected
    me_after = client.get("/api/auth/me", headers=headers)
    assert me_after.status_code == 401


def test_invalid_password_rejected(client):
    resp = client.post(
        "/api/auth/login",
        json={
            "identifier": settings.seed_admin_email,
            "password": "WrongPassword999!",
            "login_type": "admin",
        },
    )
    assert resp.status_code == 401

