"""
Dynamic prompt construction. Retrieved context is never hard-coded -
it's assembled at request time from whatever the retriever returns.
"""
from app.vectorstore.base import VectorSearchResult

SYSTEM_PROMPT = (
    "You are a document question-answering assistant.\n"
    "Answer the user's question using ONLY the provided context.\n"
    "Do not invent information that is not supported by the context.\n"
    "If the answer cannot be found in the provided context, clearly say that the "
    "information is not available in the uploaded documents.\n"
    "When possible, reference the source document and page number."
)


def build_context(chunks: list[VectorSearchResult], max_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for i, chunk in enumerate(chunks, start=1):
        page_info = f", page {chunk.page_number}" if chunk.page_number else ""
        header = f"[Source {i}: {chunk.filename}{page_info}]"
        block = f"{header}\n{chunk.content.strip()}"
        if used + len(block) > max_chars and parts:
            break
        parts.append(block)
        used += len(block)
    return "\n\n---\n\n".join(parts)


def build_user_prompt(query: str, context: str) -> str:
    if not context.strip():
        return (
            f"Question: {query}\n\n"
            "No relevant context was found in the uploaded documents. "
            "Tell the user the information is not available in the uploaded documents."
        )
    return f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer the question using only the context above."
