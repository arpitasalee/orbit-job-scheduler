def test_create_project(client, auth_headers):
    resp = client.post("/api/projects", json={"name": "Payments", "description": "Payment jobs"},
                        headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Payments"


def test_duplicate_project_name_rejected(client, auth_headers):
    client.post("/api/projects", json={"name": "Payments"}, headers=auth_headers)
    resp = client.post("/api/projects", json={"name": "Payments"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_queue_with_default_retry_policy(client, auth_headers):
    project = client.post("/api/projects", json={"name": "Payments"}, headers=auth_headers).json()
    resp = client.post(f"/api/projects/{project['id']}/queues", json={
        "name": "emails", "priority": 5, "concurrency_limit": 2,
    }, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["priority"] == 5
    assert body["retry_policy"]["strategy"] == "exponential"
    assert body["retry_policy"]["max_retries"] == 3


def test_pause_and_resume_queue(client, auth_headers):
    project = client.post("/api/projects", json={"name": "Payments"}, headers=auth_headers).json()
    queue = client.post(f"/api/projects/{project['id']}/queues", json={"name": "emails"},
                         headers=auth_headers).json()

    paused = client.post(f"/api/queues/{queue['id']}/pause", headers=auth_headers)
    assert paused.json()["is_paused"] is True

    resumed = client.post(f"/api/queues/{queue['id']}/resume", headers=auth_headers)
    assert resumed.json()["is_paused"] is False


def test_cross_org_isolation(client, auth_headers):
    """A user from Org A must not be able to see/access Org B's project."""
    project_a = client.post("/api/projects", json={"name": "Only Mine"}, headers=auth_headers).json()

    reg_b = client.post("/api/auth/register", json={
        "org_name": "Org B", "email": "userb@example.com", "password": "supersecret123",
    })
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    resp = client.get(f"/api/projects/{project_a['id']}", headers=headers_b)
    assert resp.status_code == 404
