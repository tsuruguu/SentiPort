def test_get_vessels(client):
    response = client.get("/api/v1/vessels/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_ports(client):
    response = client.get("/api/v1/ports/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_companies(client):
    response = client.get("/api/v1/companies/")
    assert response.status_code == 200