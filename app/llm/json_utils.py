import json


def extract_json(text: str) -> dict | None:
    """Find the first `{...}` substring that is both brace-balanced and valid JSON, trying each
    `{` occurrence in turn. Scanning for a balanced brace pair (rather than a greedy `\\{.*\\}`
    regex) matters because a greedy regex spans from the first `{` to the *last* `}` anywhere in
    the response -- if the model adds trailing commentary containing a brace after the real
    JSON, or stray braces (e.g. set notation) before it, the greedy match swallows all of it and
    parsing fails even though the model produced valid JSON somewhere in the response."""
    start = 0
    while True:
        start = text.find("{", start)
        if start == -1:
            return None

        depth = 0
        end = None
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end is None:
            return None  # no balanced close from here on

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            start += 1  # this brace wasn't the start of valid JSON -- try the next one
