from app.auth import create_token, decode_token


def test_token_roundtrip_and_tamper():
    token = create_token("user-1")
    assert decode_token(token) == "user-1"
    body, sig = token.split(".")
    assert decode_token(f"{body}.{sig[:-2]}xx") is None
    assert decode_token("garbage") is None
