import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Set
from utils.progress_tracker import progress_tracker
from utils.logging_config import get_logger

router = APIRouter()
logger = get_logger("websocket")


class ConnectionManager:
    """Manage WebSocket connections for progress updates"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.task_subscriptions: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            f"New WebSocket connection. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        # Remove from all task subscriptions
        for task_id, subscribers in list(self.task_subscriptions.items()):
            subscribers.discard(websocket)
            if not subscribers:
                del self.task_subscriptions[task_id]
        logger.info(
            f"WebSocket disconnected. Total connections: {len(self.active_connections)}"
        )

    def subscribe_to_task(self, websocket: WebSocket, task_id: str):
        """Subscribe a connection to a specific task's progress updates"""
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        self.task_subscriptions[task_id].add(websocket)

    async def send_progress_update(self, task_id: str, progress_data: dict):
        """Send progress update to all subscribers of a task"""
        if task_id not in self.task_subscriptions:
            return

        message = {"type": "progress_update", "task_id": task_id, "data": progress_data}

        disconnected = set()
        for websocket in self.task_subscriptions[task_id]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send progress update: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            self.task_subscriptions[task_id].discard(ws)
            self.active_connections.discard(ws)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to broadcast message: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            self.disconnect(ws)


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates"""
    await connection_manager.connect(websocket)

    try:
        while True:
            # Listen for client messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)

                if message.get("type") == "subscribe":
                    task_id = message.get("task_id")
                    if task_id:
                        connection_manager.subscribe_to_task(websocket, task_id)

                        # Send current progress if available
                        current_progress = progress_tracker.get_progress(task_id)
                        if current_progress:
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "progress_update",
                                        "task_id": task_id,
                                        "data": current_progress,
                                    }
                                )
                            )

                elif message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket client")
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


async def notify_progress_update(task_id: str):
    """Notify all subscribers about progress update for a task"""
    progress_data = progress_tracker.get_progress(task_id)
    if progress_data:
        await connection_manager.send_progress_update(task_id, progress_data)


# Background task to cleanup old progress data
async def cleanup_old_progress():
    """Cleanup old progress data periodically"""
    while True:
        try:
            progress_tracker.cleanup_completed_tasks(max_age_hours=2)
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Error in progress cleanup: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error
