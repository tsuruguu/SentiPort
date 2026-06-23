def test_get_active_port_calls(client):
    response = client.get("/api/v1/port-calls/active")
    assert response.status_code == 200
    assert "message" in response.json()

def test_generate_documents(client):
    response = client.post("/api/v1/documents/generate")
    assert response.status_code == 200