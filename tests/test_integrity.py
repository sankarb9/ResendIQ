from resendiq.integrity import verify_text, sha256_text

def test_integrity():
    assert verify_text("abc", "abc")
    assert not verify_text("abc", "abd")
    assert len(sha256_text("abc")) == 64
