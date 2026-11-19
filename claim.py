#!/usr/bin/env python3
"""Mark items claimed (or available again) on the clear-out page.

Usage:
  claim.py add "Toaster" "Mugs"      mark cards as claimed
  claim.py remove "Toaster"          make a card available again
  claim.py partial "Dinner plates"   tag cards "Some claimed" (still available)
  claim.py unpartial "Dinner plates" remove the "Some claimed" tag
  claim.py list                      show what is claimed now

It edits claimed.js next to this file, commits the change and pushes it, so the
live page updates about a minute later. Names are not case sensitive, and a
unique part of a name is enough (for example "toast" for "Toaster").
"""
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
CLAIMED_JS = os.path.join(REPO, "claimed.js")
HEADER = (
    "// Claimed items. One card name per line, exactly as shown on the page.\n"
    "// To mark an item claimed, add its name in quotes with a comma after it.\n"
    "// To make it available again, delete its line.\n"
)
PARTIAL_HEADER = '// Partly claimed items: still available, shown with a "Some claimed" tag.\n'


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def card_names():
    with open(os.path.join(REPO, "index.html"), encoding="utf-8") as f:
        html = f.read()
    return re.findall(r'^\s+[acx]\(\d, "([^"]+)"', html, re.M)


def read_list(var="CLAIMED"):
    if not os.path.exists(CLAIMED_JS):
        return []
    with open(CLAIMED_JS, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"window\.%s\s*=\s*\[(.*?)\]" % var, text, re.S)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else []


def read_claimed():
    return read_list("CLAIMED")


def write_lists(claimed, partial):
    body = "".join('  "%s",\n' % n for n in claimed)
    pbody = "".join('  "%s",\n' % n for n in partial)
    with open(CLAIMED_JS, "w", encoding="utf-8") as f:
        f.write(HEADER + "window.CLAIMED = [\n" + body + "];\n"
                + PARTIAL_HEADER + "window.PARTIAL = [\n" + pbody + "];\n")


def resolve(query, choices):
    """Return the one choice that matches the query, or None after explaining why."""
    q = query.strip().lower()
    exact = [c for c in choices if c.lower() == q]
    if exact:
        return exact[0]
    partial = [c for c in choices if q and q in c.lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        print('"%s" matches more than one: %s. Use the full name.' % (query, ", ".join(partial)))
    else:
        print('No card called "%s".' % query)
    return None


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("add", "remove", "partial", "unpartial", "list"):
        print(__doc__)
        return 2

    mode, queries = args[0], args[1:]

    pulled = git("pull", "--rebase", "--autostash")
    if pulled.returncode != 0:
        print("Could not get the latest version from GitHub:\n" + (pulled.stderr or pulled.stdout))
        return 1

    claimed = read_list("CLAIMED")
    partial = read_list("PARTIAL")
    if mode == "list":
        print("Claimed:\n" + ("\n".join(claimed) if claimed else "  (none)"))
        print("Some claimed:\n" + ("\n".join(partial) if partial else "  (none)"))
        return 0
    if not queries:
        print("Give at least one item name.")
        return 2

    changes = []
    for query in queries:
        if mode in ("add", "partial"):
            name = resolve(query, card_names())
            if not name:
                continue
            if mode == "add":
                if name in claimed:
                    print("%s is already claimed." % name)
                    continue
                claimed.append(name)
                if name in partial:
                    partial.remove(name)  # fully claimed now
            else:
                if name in claimed:
                    print("%s is fully claimed already." % name)
                    continue
                if name in partial:
                    print("%s is already tagged Some claimed." % name)
                    continue
                partial.append(name)
            changes.append(name)
        elif mode == "remove":
            name = resolve(query, claimed)
            if name:
                claimed.remove(name)
                changes.append(name)
        else:
            name = resolve(query, partial)
            if name:
                partial.remove(name)
                changes.append(name)

    if not changes:
        print("Nothing changed.")
        return 1

    write_lists(claimed, partial)
    verb = {"add": "Claimed", "remove": "Available again",
            "partial": "Some claimed", "unpartial": "Fully available"}[mode]
    message = "%s: %s" % (verb, ", ".join(changes))
    git("add", "claimed.js")
    committed = git("commit", "-m", message)
    if committed.returncode != 0:
        print("Could not save the change:\n" + (committed.stderr or committed.stdout))
        return 1
    pushed = git("push")
    if pushed.returncode != 0:
        print("Saved on this computer but the push to GitHub failed:\n" + (pushed.stderr or pushed.stdout))
        return 1
    print(message + ". Live in about a minute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
