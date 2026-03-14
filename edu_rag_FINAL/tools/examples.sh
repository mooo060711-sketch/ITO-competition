#!/usr/bin/env bash
set -e
# Example: ingest knowledge_base and then ask a question

python -m src.rag.cli ingest --dir knowledge_base --index kb --source-type knowledge_base --session-id kb --reset
python -m src.rag.cli ingest --dir uploads/demo01 --index uploads_demo01 --source-type uploads --session-id demo01 --reset

python -m src.rag.cli query --question "请总结这份资料的核心知识点" --index kb uploads_demo01 --top-k 6 --with-trace
