import pytest
from resendiq.packet_generator import split_text, generate_sample

def test_split_text():
    packets = split_text("abcdefghij", 4)
    assert [p.payload for p in packets] == ["abcd", "efgh", "ij"]

def test_empty_text():
    assert split_text("") == []

def test_invalid_payload_size():
    with pytest.raises(ValueError): split_text("abc", 0)

def test_generate_sample():
    assert generate_sample(2, 3) == "AAABBB"
