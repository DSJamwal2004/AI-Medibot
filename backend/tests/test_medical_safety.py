from app.services.medical_safety import detect_emergency

def test_emergency_detection():
    assert detect_emergency("I have chest pain and dizziness") is True
    assert detect_emergency("I feel suicidal") is True
    assert detect_emergency("I have severe bleeding") is True

    assert detect_emergency("I have a mild headache") is False
    assert detect_emergency("I feel tired today") is False
