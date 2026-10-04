"""Manage WebSocket connections grouped by session identifier.

This module provides a manager for handling multiple concurrent WebSocket
connections, organized by session ID. It ensures thread-safe message
broadcasting and proper connection lifecycle management.

Note:
    This manager is not thread-safe across async tasks that share the same
    manager instance directly without proper synchronization. Use within
    a single async event loop context.

Example:
    >>> manager = WebSocketManager()
    >>> await manager.connect("user_123", websocket)
    >>> await manager.send_json("user_123", {"message": "hello"})
    >>> await manager.disconnect("user_123", websocket)
"""

import asyncio

from fastapi import WebSocket

from utilities_ai._logger import log as _log


class WebSocketManager:
    """Manage multiple WebSocket connections organized by session ID.

    Maintains a registry of active WebSocket connections grouped by session,
    with per-connection locks to ensure thread-safe message delivery. Handles
    connection lifecycle management including acceptance, disconnection, and
    cleanup.

    Attributes:
        ws: Dictionary mapping session IDs to lists of active WebSocket
            connections for that session.
        locks: Dictionary mapping each WebSocket connection to its own
            asyncio.Lock for synchronizing concurrent send operations.
    """

    def __init__(self):
        """Initialize an empty WebSocket connection manager."""
        self.ws: dict[str, list[WebSocket]] = {}
        self.locks: dict[WebSocket, asyncio.Lock] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """Accept a WebSocket connection and register it for a session.

        Accepts the WebSocket handshake, adds the connection to the registry
        for the specified session, and creates a lock to synchronize message
        delivery on this connection.

        Args:
            session_id: The unique identifier of the session to which this
                connection belongs.
            ws: The FastAPI WebSocket connection to accept and register.

        Example:
            >>> await manager.connect("session_abc", websocket)
        """
        await ws.accept()
        self.ws.setdefault(session_id, []).append(ws)
        self.locks[ws] = asyncio.Lock()
        _log.debug(f"[WEBSOCKET_MANAGER] Added WebSocket {ws} to session ID {session_id}\nConnected connections: {self.ws}")

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        """Unregister a WebSocket connection and close it.

        Removes the connection from the session registry and its associated
        lock. If the session has no remaining connections, removes the session
        entry. Closes the WebSocket connection.

        Args:
            session_id: The session ID from which to unregister the connection.
            ws: The WebSocket connection to remove and close.

        Example:
            >>> await manager.disconnect("session_abc", websocket)
        """
        self.locks.pop(ws, None)

        conns = self.ws.get(session_id)
        if not conns:
            return

        if ws in conns:
            conns.remove(ws)
            _log.debug(f"[WEBSOCKET_MANAGER] Removed WebSocket {ws} from session ID {session_id}\nConnected connections: {self.ws}")
        if not conns:
            self.ws.pop(session_id, None)

        await ws.close()

    async def send_json(self, session_id: str, msg: dict) -> None:
        """Broadcast a JSON message to all connections in a session.

        Sends the specified message to every WebSocket connection registered
        for the session. Uses per-connection locks to ensure message delivery
        is not interleaved with other concurrent sends on the same connection.

        Args:
            session_id: The session ID whose connections will receive the
                message.
            msg: The dictionary to serialize and send as JSON to all
                connections.

        Example:
            >>> await manager.send_json("session_abc", {"status": "ready"})
        """
        for ws in self.ws.get(session_id, []):
            async with self.locks[ws]:
                await ws.send_json(msg)
