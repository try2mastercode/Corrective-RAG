import argparse

from app.core.config import get_settings
from app.core.dependencies import build_llm_client, build_retriever
from app.generation.answer import generate_answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question against the local knowledge base.")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument("--top-k", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    top_k = args.top_k or settings.top_k

    retriever = build_retriever(settings)
    llm = build_llm_client(settings)

    chunks = retriever.retrieve(args.question, top_k=top_k)
    answer, sources = generate_answer(args.question, chunks, llm)

    print("Answer:")
    print(answer)
    print("\nSources:")
    for s in sources:
        page_info = f", page {s.page}" if s.page else ""
        print(f"  [{s.id}] {s.source}{page_info}")


if __name__ == "__main__":
    main()
