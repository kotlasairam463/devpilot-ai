# test_webhook.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app          # <-- note the api. prefix

client = TestClient(app)

fake_files = [
    {"filename": "auth.py", "code": "def login(u,p): return db.execute(f'SELECT * FROM users WHERE name={u}')", "patch": "", "additions": 1, "deletions": 0}
]

with patch("api.main.github.get_pr_files", return_value=fake_files):  # <-- also prefixed
    response = client.post("/webhook", json={
        "action": "opened",
        "pull_request": {"number": 1, "title": "Test PR", "html_url": "https://github.com/test/repo/pull/1"},
        "repository": {"full_name": "test/repo"}
    })
    print(response.status_code, response.json())