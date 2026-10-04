"""WebSocket heartbeat mechanism to keep connections alive and detect disconnections.

This module provides a heartbeat task that periodically sends ping messages to
maintain WebSocket connections and detect client or network failures. The heartbeat
runs as an independent asyncio task, typically alongside the main message handler.

Note:
    The heartbeat task is designed to run indefinitely until cancelled by the
    connection manager or until an unrecoverable error occurs. All exceptions
    (except `asyncio.CancelledError`) are logged with full traceback and
    re-raised to allow graceful shutdown of the connection.

Example:
    >>> import asyncio
    >>> from fastapi import WebSocket
    >>> from pydantic import BaseModel
    >>> from websocket_manager import WebSocketManager
    >>>
    >>> class PingResponse(BaseModel):
    ...     type: str
    ...     response: str
    ...     session_id: str
    ...
    >>> async def run_heartbeat():
    ...     websocket = ...  # obtained from FastAPI
    ...     manager = WebSocketManager()
    ...     task = asyncio.create_task(
    ...         websocket_heartbeat(
    ...             websocket, manager, "session_123",
    ...             ResponseModel=PingResponse, interval=30
    ...         )
    ...     )
    ...     # Task runs until manually cancelled
    ...     await asyncio.sleep(120)
    ...     task.cancel()
"""

import asyncio
import traceback

from fastapi import WebSocket
from pydantic import BaseModel

from utilities_ai._logger import log as _log

from .websocket_manager import WebSocketManager


async def websocket_heartbeat(
    websocket: WebSocket,
    ws_manager: WebSocketManager,
    session_id: str,
    *,
    ResponseModel: type[BaseModel],
    interval: int = 30,
    **kwargs,
) -> None:
    """Send periodic ping messages to maintain a WebSocket connection.

    Constructs a ping response message using the provided `ResponseModel` and
    sends it at regular intervals over the WebSocket connection. The task runs
    indefinitely until cancelled or until an unrecoverable error occurs.

    This function is typically run as an independent asyncio task alongside
    the main message handler. Both tasks share access to the connection via
    the manager's lock mechanism to prevent concurrent writes.

    Args:
        websocket: The FastAPI WebSocket connection to send heartbeats through.
        ws_manager: The WebSocketManager instance managing this connection.
            Used to access the async lock for the given websocket.
        session_id: The unique identifier for this WebSocket session. Included
            in ping messages and used for logging.
        ResponseModel: A Pydantic BaseModel class used to construct the ping
            response. Must accept `type`, `response`, and `session_id` parameters.
        interval: Time in seconds between successive heartbeat messages.
            Defaults to 30.
        **kwargs: Additional keyword arguments to pass to the ResponseModel
            constructor (e.g., custom fields required by the response schema).

    Returns:
        None. This coroutine does not return under normal operation; it runs
        until cancelled or an error occurs.

    Raises:
        asyncio.CancelledError: Raised when the task is cancelled by the
            calling code. This is re-raised without modification to signal
            graceful shutdown.
        Exception: Any other exception encountered during execution (e.g.,
            network errors, JSON serialization failures) is logged with full
            traceback and re-raised. This allows the caller to detect and
            handle connection failures appropriately.

    Note:
        Thread-safety: The function uses `ws_manager.locks[websocket]` to
        synchronize access to the WebSocket connection, ensuring that
        heartbeat messages do not interleave with messages from other
        handlers.

    Example:
        >>> response_model = ...  # Your Pydantic model
        >>> heartbeat_task = asyncio.create_task(
        ...     websocket_heartbeat(
        ...         ws, manager, "session_abc",
        ...         ResponseModel=response_model,
        ...         interval=45
        ...     )
        ... )
        >>> # Later, to gracefully stop the heartbeat:
        >>> heartbeat_task.cancel()
    """
    response = ResponseModel(type="ping", response="", session_id=session_id, **kwargs)

    try:
        while True:
            await asyncio.sleep(interval)
            # Acquire lock to prevent concurrent writes to the websocket
            async with ws_manager.locks[websocket]:
                await websocket.send_json(response.model_dump())

    except asyncio.CancelledError:
        # Allow cancellation to propagate for clean task shutdown
        raise

    except Exception:
        _log.error(f"[WEBSOCKET_MANAGER] <{session_id}> {traceback.format_exc()}")
        raise
