from datetime import datetime, timedelta, timezone


def _make_queue(client, auth_headers):
    project = client.post("/api/projects", json={"name": "Payments"}, headers=auth_headers).json()
    queue = client.post(f"/api/projects/{project['id']}/queues", json={"name": "emails"},
                         headers=auth_headers).json()
    return queue


def test_create_immediate_job(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    resp = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "send-welcome-email", "job_type": "immediate", "payload": {"to": "a@b.com"},
    }, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_type"] == "immediate"


def test_delayed_job_requires_run_at(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    resp = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "delayed-job", "job_type": "delayed", "payload": {},
    }, headers=auth_headers)
    assert resp.status_code == 400


def test_delayed_job_starts_scheduled(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    run_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    resp = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "delayed-job", "job_type": "delayed", "payload": {}, "run_at": run_at,
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["status"] == "scheduled"


def test_recurring_job_requires_valid_cron(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    bad = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "cron-job", "job_type": "recurring", "payload": {}, "cron_expression": "not-a-cron",
    }, headers=auth_headers)
    assert bad.status_code == 400

    good = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "cron-job", "job_type": "recurring", "payload": {}, "cron_expression": "*/5 * * * *",
    }, headers=auth_headers)
    assert good.status_code == 201
    assert good.json()["next_run_at"] is not None


def test_batch_job_creation(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    resp = client.post(f"/api/queues/{queue['id']}/jobs/batch", json={
        "name_prefix": "resize-image",
        "payloads": [{"file": "1.png"}, {"file": "2.png"}, {"file": "3.png"}],
    }, headers=auth_headers)
    assert resp.status_code == 201
    jobs = resp.json()
    assert len(jobs) == 3
    assert len({j["batch_id"] for j in jobs}) == 1  # all share one batch id


def test_job_pagination_and_filtering(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    for i in range(5):
        client.post(f"/api/queues/{queue['id']}/jobs", json={
            "name": f"job-{i}", "job_type": "immediate", "payload": {},
        }, headers=auth_headers)

    page1 = client.get(f"/api/queues/{queue['id']}/jobs?page=1&page_size=2", headers=auth_headers).json()
    assert page1["total"] == 5
    assert len(page1["items"]) == 2

    filtered = client.get(f"/api/queues/{queue['id']}/jobs?status=queued", headers=auth_headers).json()
    assert filtered["total"] == 5


def test_retry_only_allowed_for_failed_or_dead_letter_jobs(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    job = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "job", "job_type": "immediate", "payload": {},
    }, headers=auth_headers).json()

    # still queued -> not eligible for manual retry
    resp = client.post(f"/api/jobs/{job['id']}/retry", headers=auth_headers)
    assert resp.status_code == 400


def test_cancel_job(client, auth_headers):
    queue = _make_queue(client, auth_headers)
    job = client.post(f"/api/queues/{queue['id']}/jobs", json={
        "name": "job", "job_type": "immediate", "payload": {},
    }, headers=auth_headers).json()

    resp = client.post(f"/api/jobs/{job['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
