async def test_version_endpoint_returns_pyproject_version(client):
    resp = await client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert isinstance(body["version"], str) and body["version"]
