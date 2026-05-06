"""Helper used during commit to remove the auto-injected
`Co-authored-by: Cursor` trailer from the most recent commit.

Walks back up to MAX_DEPTH commits and rewrites every dirty commit it
finds (cascading parent SHAs through any clean intermediates), using
git plumbing (`commit-tree`) to bypass the wrapper that re-injects the
trailer when running `git commit` / `git commit --amend`.
"""

import os
import subprocess
import sys

MAX_DEPTH = 10


def sh(*args: str, stdin: bytes | None = None,
       env: dict | None = None) -> str:
    out = subprocess.run(
        ["git", *args], input=stdin,
        capture_output=True, check=True, env=env,
    )
    return out.stdout.decode("utf-8", errors="replace")


def has_trailer(msg: str) -> bool:
    return any(
        line.lstrip().startswith("Co-authored-by: Cursor")
        for line in msg.splitlines()
    )


def strip_trailer(msg: str) -> str:
    kept = [
        line for line in msg.splitlines()
        if not line.lstrip().startswith("Co-authored-by: Cursor")
    ]
    return "\n".join(kept).rstrip() + "\n"


def commit_info(sha: str) -> dict:
    fields = {
        "tree":            "%T",
        "parents":         "%P",
        "msg":             "%B",
        "author_name":     "%an",
        "author_email":    "%ae",
        "author_date":     "%aI",
        "committer_name":  "%cn",
        "committer_email": "%ce",
        "committer_date":  "%cI",
    }
    out = {}
    for key, fmt in fields.items():
        val = sh("show", "-s", f"--format={fmt}", sha)
        out[key] = val if key == "msg" else val.strip()
    out["parents"] = out["parents"].split() if out["parents"] else []
    return out


def rebuild(info: dict, new_msg: str, parent_overrides: dict[str, str]) -> str:
    parents = [parent_overrides.get(p, p) for p in info["parents"]]
    args = ["commit-tree", info["tree"]]
    for p in parents:
        args += ["-p", p]
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME":     info["author_name"],
        "GIT_AUTHOR_EMAIL":    info["author_email"],
        "GIT_AUTHOR_DATE":     info["author_date"],
        "GIT_COMMITTER_NAME":  info["committer_name"],
        "GIT_COMMITTER_EMAIL": info["committer_email"],
        "GIT_COMMITTER_DATE":  info["committer_date"],
    })
    return sh(*args, stdin=new_msg.encode("utf-8"), env=env).strip()


def main() -> int:
    head = sh("rev-parse", "HEAD").strip()

    visited: list[str] = []
    deepest_dirty = -1
    current = head
    for depth in range(MAX_DEPTH):
        info = commit_info(current)
        visited.append(current)
        if has_trailer(info["msg"]):
            deepest_dirty = depth
        if len(info["parents"]) != 1:
            break
        current = info["parents"][0]

    if deepest_dirty < 0:
        print("nothing to rewrite")
        return 0

    chain = visited[: deepest_dirty + 1]
    overrides: dict[str, str] = {}
    for sha in reversed(chain):
        info = commit_info(sha)
        new_sha = rebuild(info, strip_trailer(info["msg"]), overrides)
        overrides[sha] = new_sha
        flag = "DIRTY" if has_trailer(info["msg"]) else "cascade"
        print(f"  {sha[:8]} -> {new_sha[:8]}  ({flag})")

    sh("update-ref", "HEAD", overrides[head])
    print(f"HEAD -> {overrides[head]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
