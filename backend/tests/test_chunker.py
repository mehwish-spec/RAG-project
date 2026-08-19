from app.processing.chunker import ChunkConfig, chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_returns_single_chunk():
    text = "This is a short paragraph that fits in one chunk easily."
    chunks = chunk_text(text, ChunkConfig(chunk_size=1000, chunk_overlap=100))
    assert len(chunks) == 1
    assert chunks[0].content == text
    assert chunks[0].chunk_index == 0


def test_long_text_splits_into_multiple_chunks():
    paragraph = "Sentence number {}. " * 1  # placeholder, build below
    long_text = "\n\n".join(
        f"This is paragraph {i} with some reasonably descriptive filler content to pad it out." for i in range(50)
    )
    config = ChunkConfig(chunk_size=300, chunk_overlap=50, min_chunk_size=20, max_chunk_size=600)
    chunks = chunk_text(long_text, config=config)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= config.max_chunk_size + config.chunk_overlap


def test_chunk_overlap_carries_context_between_chunks():
    long_text = "\n\n".join(f"Paragraph {i} contains unique marker XYZ{i}." for i in range(30))
    config = ChunkConfig(chunk_size=200, chunk_overlap=60, min_chunk_size=20, max_chunk_size=400)
    chunks = chunk_text(long_text, config=config)
    assert len(chunks) > 1
    # The tail of chunk N should reappear at the head of chunk N+1 due to overlap.
    tail_of_first = chunks[0].content[-30:]
    assert any(tail_of_first[:15] in c.content for c in chunks[1:])


def test_chunks_preserve_page_number_and_section():
    chunks = chunk_text("Some content here.", page_number=3, section="Introduction")
    assert chunks[0].page_number == 3
    assert chunks[0].section == "Introduction"


def test_does_not_produce_chunks_smaller_than_min_size_when_mergeable():
    text = "Word. " * 5 + "\n\n" + "Tiny."
    config = ChunkConfig(chunk_size=1000, chunk_overlap=0, min_chunk_size=20, max_chunk_size=2000)
    chunks = chunk_text(text, config=config)
    # "Tiny." alone is below min_chunk_size and should be merged into the previous chunk.
    assert all(len(c.content) >= config.min_chunk_size for c in chunks) or len(chunks) == 1


def test_very_long_single_sentence_is_hard_split():
    long_sentence = "word " * 500  # no punctuation, single "sentence"
    config = ChunkConfig(chunk_size=200, chunk_overlap=20, min_chunk_size=20, max_chunk_size=250)
    chunks = chunk_text(long_sentence, config=config)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= config.max_chunk_size + config.chunk_overlap
