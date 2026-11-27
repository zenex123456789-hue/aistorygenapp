#!/usr/bin/env python3
"""Make a random personal access code for each person.   python tools/make_codes.py alice bob carol

Prints one line to paste into the SF_ACCESS_CODES setting, and a short list you can send to each person privately.
Codes use letters and numbers only (no look-alike characters), so they are easy to type on a phone.
"""
import secrets
import sys

ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def code(n: int = 14) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def main(names: list[str]) -> int:
    if not names:
        print(__doc__)
        return 1
    pairs = [(n, code()) for n in names]
    print("Paste this as SF_ACCESS_CODES:\n")
    print(",".join(f"{n}:{c}" for n, c in pairs))
    print("\nSend each person only their own code:")
    for n, c in pairs:
        print(f"  {n}: {c}")
    print("\nTo cut someone off later, delete their name:code from SF_ACCESS_CODES and redeploy. To replace a code, change it there.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
