def test_healthchecker(client):
    response = client.get("/api/healthchecker")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Welcome to Contacts API!"
