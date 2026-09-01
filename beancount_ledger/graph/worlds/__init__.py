"""Authored worlds: irreducible facts only, and the task registry."""

from .alpine_2025_11 import BANK_RECON_001, WORLD as ALPINE_2025_11

# task id -> (world, task spec). The production composition root reads
# this and nothing else to build an environment.
REGISTRY = {BANK_RECON_001.id: (ALPINE_2025_11, BANK_RECON_001)}
