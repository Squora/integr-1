import asyncio
import json
import uuid
import os
from aio_pika import connect_robust, Message, DeliveryMode

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
REQUEST_QUEUE = "api.requests"


class AsyncAPIClient:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.reply_queue = None
        self.responses = {}
        self.lock = asyncio.Lock()

    async def connect(self):
        self.connection = await connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()

        self.reply_queue = await self.channel.declare_queue("", exclusive=True)
        await self.reply_queue.consume(self._on_response)

        print(f"[Клиент] Подключено. Reply queue: {self.reply_queue.name}")

    async def _on_response(self, message):
        body = json.loads(message.body)
        correlation_id = message.correlation_id
        async with self.lock:
            self.responses[correlation_id] = body
        await message.ack()

    async def call(self, action: str, version: str = "v1", data: dict = None,
                   auth: str = "supersecretapikey", idempotency_key: str = None):
        if not self.channel or self.channel.is_closed:
            raise ConnectionError("Клиент не подключён")

        correlation_id = str(uuid.uuid4())
        message_body = {
            "id": str(uuid.uuid4()),
            "version": version,
            "action": action,
            "data": data or {},
            "auth": auth
        }
        if idempotency_key:
            message_body["idempotency_key"] = idempotency_key

        await self.channel.default_exchange.publish(
            Message(
                body=json.dumps(message_body).encode(),
                correlation_id=correlation_id,
                reply_to=self.reply_queue.name,
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=REQUEST_QUEUE
        )

        print(f"[Запрос] {action} ({version}) → correlation_id: {correlation_id}")

        while True:
            async with self.lock:
                if correlation_id in self.responses:
                    response = self.responses.pop(correlation_id)
                    break
            await asyncio.sleep(0.1)

        status = response.get("status")
        error = response.get("error")
        print(f"[Ответ] status={status}, error={error}")
        return response

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        print("[Клиент] Соединение закрыто")