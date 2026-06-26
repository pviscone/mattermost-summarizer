"""Monkey-patch to propagate OpenTelemetry trace context into OpenHands sub-agent threads.

Background
----------
OpenHands delegates work to sub-agents via ``DelegateExecutor._delegate_tasks``, which
spawns plain ``threading.Thread`` objects.  Python's ``contextvars`` do *not* propagate
across thread boundaries automatically, so every sub-agent conversation starts a brand-
new Laminar root span with no parent.  In MLflow / Laminar traces this makes all
sub-agent spans appear as siblings of the root ``conversation`` span instead of
nesting cleanly under the ``DelegateAction`` span.

Fix
---
1.  We capture the active OTel ``Context`` object in the *parent* thread at the moment
    ``_delegate_tasks`` is entered — this context includes the currently-active span
    (the ``DelegateAction`` tool span).
2.  We store that context in a ``contextvars.ContextVar`` before launching each worker
    thread and restore it inside the thread before the sub-agent conversation is
    initialised.
3.  We patch ``LocalConversation._start_observability_span`` so that when a parent
    context is present it passes it to ``Laminar.start_span`` via the ``context=``
    keyword argument, making the new root span a child of the active parent span.

Usage
-----
Call ``install()`` once, as early as possible (before any openhands imports create
conversations).  ``summarize.py`` does this automatically::

    from mattermost_summarizer.tracing_patch import install
    install()
"""

from __future__ import annotations

import contextvars
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Holds the OTel Context that should be used as the parent for a new
# sub-agent conversation's root span.  Set in the parent thread, read in
# the child thread inside _start_observability_span.
_parent_otel_context: contextvars.ContextVar[Any | None] = contextvars.ContextVar("_parent_otel_context", default=None)

_installed = False


def install() -> None:
    """Apply the monkey-patches.  Safe to call multiple times (idempotent)."""
    global _installed
    if _installed:
        return
    _installed = True

    _patch_delegate_executor()
    _patch_local_conversation()
    logger.debug("tracing_patch: OTel context-propagation patches installed")


def _patch_delegate_executor() -> None:
    """Wrap DelegateExecutor._delegate_tasks to capture + forward OTel context."""
    try:
        from openhands.tools.delegate.impl import DelegateExecutor
    except ImportError:
        logger.debug("tracing_patch: DelegateExecutor not importable, skipping patch")
        return

    original_delegate_tasks = DelegateExecutor._delegate_tasks  # type: ignore[attr-defined]

    def _patched_delegate_tasks(self: Any, action: Any) -> Any:  # type: ignore[return]
        try:
            from opentelemetry import context as otel_context

            current_ctx = otel_context.get_current()
        except Exception:
            current_ctx = None

        if current_ctx is None:
            return original_delegate_tasks(self, action)

        # We need the threads spawned inside _delegate_tasks to inherit current_ctx.
        # The threads are created by the original method, so we temporarily patch
        # threading.Thread to wrap its target with context propagation.
        original_thread_init = threading.Thread.__init__

        def _ctx_aware_thread_init(
            thread_self: threading.Thread,
            *args: Any,
            target: Any = None,
            **kwargs: Any,
        ) -> None:
            if target is not None:
                original_target = target
                captured_ctx = current_ctx

                def _wrapped_target(*t_args: Any, **t_kwargs: Any) -> Any:
                    # Inject the parent OTel context into this thread so that
                    # _start_observability_span can pick it up.
                    token = _parent_otel_context.set(captured_ctx)
                    try:
                        return original_target(*t_args, **t_kwargs)
                    finally:
                        _parent_otel_context.reset(token)

                kwargs["target"] = _wrapped_target
            original_thread_init(thread_self, *args, **kwargs)

        threading.Thread.__init__ = _ctx_aware_thread_init  # type: ignore[method-assign]
        try:
            return original_delegate_tasks(self, action)
        finally:
            threading.Thread.__init__ = original_thread_init  # type: ignore[method-assign]

    DelegateExecutor._delegate_tasks = _patched_delegate_tasks  # type: ignore[attr-defined]
    logger.debug("tracing_patch: DelegateExecutor._delegate_tasks patched")


def _patch_local_conversation() -> None:
    """Wrap LocalConversation._start_observability_span to accept a parent OTel context."""
    try:
        from openhands.sdk.conversation.impl.local_conversation import LocalConversation
    except ImportError:
        logger.debug("tracing_patch: LocalConversation not importable, skipping patch")
        return

    from openhands.sdk.observability.laminar import should_enable_observability
    from openhands.sdk.observability.laminar import RootSpan

    original_start_span = LocalConversation._start_observability_span  # type: ignore[attr-defined]

    def _patched_start_observability_span(self: Any, session_id: str, *args, **kwargs) -> None:
        parent_ctx = _parent_otel_context.get()
        if parent_ctx is None:
            # Not in a sub-agent thread — use normal behaviour.
            return original_start_span(self, session_id)

        if not should_enable_observability():
            return
        if self._observability_root_span is not None:
            return

        try:
            from lmnr import Laminar

            span = Laminar.start_span("conversation", context=parent_ctx)
            root = RootSpan.__new__(RootSpan)
            root.span = span
            root._ended = False
            self._observability_root_span = root
            logger.debug("tracing_patch: sub-agent conversation span created with parent context")
        except Exception:
            logger.debug(
                "tracing_patch: failed to create parented span, falling back",
                exc_info=True,
            )
            return original_start_span(self, session_id)

    LocalConversation._start_observability_span = _patched_start_observability_span  # type: ignore[attr-defined]
    logger.debug("tracing_patch: LocalConversation._start_observability_span patched")
