from app.processing.metadata import compute_content_hash


def test_same_content_produces_same_hash():
    content = b"hello world, this is a test document."
    assert compute_content_hash(content) == compute_content_hash(content)


def test_different_content_produces_different_hash():
    assert compute_content_hash(b"document A") != compute_content_hash(b"document B")


def test_hash_is_sha256_hex_digest():
    h = compute_content_hash(b"some content")
    assert len(h) == 64
    int(h, 16)  # raises ValueError if not valid hex
