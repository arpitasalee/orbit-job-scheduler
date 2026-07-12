def test_register_creates_org_and_returns_token(client):
    resp = client.post("/api/auth/register", json={
        "org_name": "Acme Inc", "email": "founder@acme.com", "password": "supersecret123",
    })
    assert resp.status_code == 201
    assert "access_token" in resp.json()


def test_register_duplicate_email_rejected(client):
    payload = {"org_name": "Acme Inc", "email": "dupe@acme.com", "password": "supersecret123"}
    client.post("/api/auth/register", json=payload)
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


def test_login_success_and_failure(client):
    client.post("/api/auth/register", json={
        "org_name": "Acme Inc", "email": "user@acme.com", "password": "correct-password",
    })
    good = client.post("/api/auth/login", json={"email": "user@acme.com", "password": "correct-password"})
    assert good.status_code == 200

    bad = client.post("/api/auth/login", json={"email": "user@acme.com", "password": "wrong-password"})
    assert bad.status_code == 401


def test_me_requires_valid_token(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"].startswith("test-")

    unauthenticated = client.get("/api/auth/me")
    assert unauthenticated.status_code == 401
