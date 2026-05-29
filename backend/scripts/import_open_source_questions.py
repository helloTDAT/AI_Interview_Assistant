from __future__ import annotations

import argparse
from pathlib import Path

from app.services.learning_rag import LearningRagService


def main() -> None:
    parser = argparse.ArgumentParser(description="Import approved open-source Markdown interview notes into local RAG.")
    parser.add_argument("--repo", required=True, help="Repository slug, for example Snailclimb/JavaGuide")
    parser.add_argument("--path", required=True, help="Local Markdown file path")
    parser.add_argument("--license", default="Apache-2.0", help="SPDX-like license name")
    parser.add_argument("--source-url", default="", help="Original source URL")
    args = parser.parse_args()

    markdown_path = Path(args.path)
    markdown = markdown_path.read_text(encoding="utf-8")
    chunks = LearningRagService().import_markdown(
        repo=args.repo,
        path=str(markdown_path),
        markdown=markdown,
        license_name=args.license,
        source_url=args.source_url,
    )
    print(
        f"Imported {len(chunks)} chunks from {args.repo} "
        f"(license={args.license}, source_url={args.source_url or 'n/a'})."
    )


if __name__ == "__main__":
    main()
