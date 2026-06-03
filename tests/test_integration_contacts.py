contact_payload = {
    "first_name": "Peter",
    "last_name": "Parker",
    "email": "peter@bugle.com",
    "phone": "+380501112233",
    "birthday": "2001-08-10",
}


def _auth(get_token):
    return {"Authorization": f"Bearer {get_token}"}


def test_contacts_require_auth(client):
    response = client.get("/api/contacts/")
    assert response.status_code == 401, response.text


def test_create_contact(client, get_token):
    response = client.post(
        "/api/contacts/", json=contact_payload, headers=_auth(get_token)
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["first_name"] == "Peter"
    assert data["email"] == "peter@bugle.com"
    assert "id" in data


def test_create_duplicate_contact(client, get_token):
    response = client.post(
        "/api/contacts/", json=contact_payload, headers=_auth(get_token)
    )
    assert response.status_code == 409, response.text


def test_get_contacts(client, get_token):
    response = client.get("/api/contacts/", headers=_auth(get_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["first_name"] == "Peter"


def test_get_contact(client, get_token):
    response = client.get("/api/contacts/1", headers=_auth(get_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == 1
    assert data["last_name"] == "Parker"


def test_get_contact_not_found(client, get_token):
    response = client.get("/api/contacts/999", headers=_auth(get_token))
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Contact not found"


def test_search_contacts(client, get_token):
    response = client.get(
        "/api/contacts/", params={"first_name": "Pet"}, headers=_auth(get_token)
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Peter"


def test_update_contact(client, get_token):
    updated = {**contact_payload, "first_name": "Spider"}
    response = client.put("/api/contacts/1", json=updated, headers=_auth(get_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["first_name"] == "Spider"


def test_update_contact_not_found(client, get_token):
    response = client.put(
        "/api/contacts/999", json=contact_payload, headers=_auth(get_token)
    )
    assert response.status_code == 404, response.text


def test_upcoming_birthdays(client, get_token):
    response = client.get(
        "/api/contacts/birthdays", params={"days": 7}, headers=_auth(get_token)
    )
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_delete_contact(client, get_token):
    response = client.delete("/api/contacts/1", headers=_auth(get_token))
    assert response.status_code == 200, response.text
    assert response.json()["id"] == 1


def test_repeat_delete_contact(client, get_token):
    response = client.delete("/api/contacts/1", headers=_auth(get_token))
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Contact not found"
