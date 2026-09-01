from .beancount_ledger import (
    library_versions,
    load_environment,
    tool_call_chars,
)

# `load_environment` is the serving door and the only entry point a runner
# needs. The other two are the shared MEASUREMENT vocabulary:
#
#   tool_call_chars(message)   characters of the canonical serialization of an
#                              assistant message's tool calls (name, id,
#                              arguments — no wrapper), the tool-call half of
#                              the plausibility denominator (Codex T48 §3.1).
#                              `tests/measure_budget.py` keeps its OWN counter
#                              on purpose — it reads archived rows and handles
#                              call shapes this one does not (nested
#                              `{"function": {…}}`, a call serialized as a JSON
#                              string), where this returns 0 and so stays a
#                              conservative lower bound. Two independent
#                              implementations of a fail-closed floor that can
#                              only disagree leniently; exported so the
#                              instrument can cross-check, not so it can stop
#                              having one;
#   library_versions()         the pinned distributions the model-facing tool
#                              schemas are generated from, as
#                              `state["piv_library_versions"]` carries them.
__all__ = ['load_environment', 'tool_call_chars', 'library_versions']
