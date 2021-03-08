# Quart-WebSocketRooms
Quart-WebSocketRooms is a Quart extension that provides a basic API for 'room' based WebSocket Apps.

# Basic Usage
A basic chat room type app would look something like this:
```python
from quart_websocketrooms import WebSocketRooms

app = WebSocketRooms(__name__)

@app.incoming_processing_step()
async def chat_message(user, message):
    step_responses = []
    if message["type"] == "chat_message"
        await user.room.broadcast(message)

    return step_responses

app.bind_to_route("/ws")

```
