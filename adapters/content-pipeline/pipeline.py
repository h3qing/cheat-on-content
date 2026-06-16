"""Content pipeline CLI — writes discovered signals / voice drafts to Supabase.

The judgment lives with Claude (web-search → relevance scoring → source_signals; signal +
voice-profile.md → draft → post_ideas). This CLI is the I/O the agent calls.

    python pipeline.py add-signals signals.json   # [{title,summary,url,theme,relevance_score,source_name,source_type}, ...]
    python pipeline.py add-idea idea.json          # {topic,angle,hook,body,status,predicted_engagement,notes}
    python pipeline.py list-signals
    python pipeline.py list-ideas

Run with the linkedin-tracker venv + CHEAT_PROJECT_ROOT pointing at it:
    CHEAT_PROJECT_ROOT=~/linkedin-tracker ~/linkedin-tracker/.venv/bin/python pipeline.py ...
"""
import json
import sys

import store


def _load(path: str):
    return json.loads(sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read())


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "add-signals":
        print(json.dumps(store.insert_signals(_load(sys.argv[2])), ensure_ascii=False))
    elif cmd == "add-idea":
        print(json.dumps(store.insert_idea(_load(sys.argv[2])), ensure_ascii=False))
    elif cmd == "list-signals":
        for r in store.list_signals():
            print(r)
    elif cmd == "list-ideas":
        for r in store.list_ideas():
            print(r)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
