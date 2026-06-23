import uuid


def test_recalculate_risk_score(client, mock_db):
    test_vessel_id = str(uuid.uuid4())
    test_assessment_id = str(uuid.uuid4())

    # Mockujemy zachowanie surowego zapytania SQL: db.execute().scalar()
    mock_result = mock_db.execute.return_value
    mock_result.scalar.return_value = test_assessment_id

    response = client.post(f"/api/v1/risk/{test_vessel_id}/calculate")

    assert response.status_code == 200
    assert response.json()["message"] == "Ryzyko przeliczone pomyślnie!"
    assert response.json()["new_assessment_id"] == test_assessment_id

    # Sprawdzamy czy API wywołało w bazie funkcję z odpowiednim parametrem
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()