def test_emergency_ends_conversation(client, auth_headers):
    response = client.post(
        "/api/v1/chat",
        json={"message": "I have severe chest pain"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "emergency" in response.json()["reply"].lower()

    # (Later) fetch conversation and assert ended_at is set
