"""Asking a question at a console, for the scripts run from a terminal.

The web app never reaches these: it runs the scripts with no console attached,
so can_prompt() is False and every script falls back to its flags.
"""

import sys


def can_prompt():
    """Only offer a prompt when there is a real console to answer from."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def confirm(question, default_yes=False):
    """Ask a yes or no question. The capital letter is what Enter does.

    default_yes is for the questions that only confirm the thing the user
    already asked for. It stays off for anything that overrides a check, where
    Enter has to mean no.
    """
    prompt = "%s [Y/n] " if default_yes else "%s [y/N] "
    try:
        answer = input(prompt % question).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not answer:
        return default_yes
    return answer in ("y", "yes")
