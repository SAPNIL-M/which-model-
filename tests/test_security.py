from app.security import sign_session, verify_session


def test_signed_session_round_trip():
    value = sign_session(12, "secret")
    assert verify_session(value, "secret") == 12
    assert verify_session(value, "wrong") is None
