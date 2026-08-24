"""DOOF compute pool — job-level distribution, not layer-split inference.

Many jobs → many computers. One transformer is not sharded across friends.
"""
from .jobs import ALLOWED_JOB_TYPES, validate_payload
from .pool import dispatch_inference, execute_local, start_worker_loop
from .scheduler import select_node

__all__ = [
    "ALLOWED_JOB_TYPES",
    "validate_payload",
    "dispatch_inference",
    "execute_local",
    "start_worker_loop",
    "select_node",
]
