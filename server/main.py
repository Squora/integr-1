import asyncio
import json
import logging
import os
from aio_pika import connect_robust, Message, DeliveryMode

from utils.db import get_db
from utils.auth import verify_api_key
from handlers import v1, v2, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_QUEUE = "api.requests"
DLQ = "api.dlq"


async def process_message(message):
    async with message.process(requeue=True):
        try:
            data = json.loads(message.body.decode())
        except json.JSONDecodeError:
            await send_error(message.correlation_id, "Invalid JSON", message.reply_to)
            return

        if not verify_api_key(data.get("auth")):
            await send_error(message.correlation_id, "Invalid API key", message.reply_to)
            return

        action = data.get("action")
        version = data.get("version", "v1")
        idempotency_key = data.get("idempotency_key")

        db_gen = get_db()
        db = next(db_gen)

        try:
            if action == "create_book" and version == "v1":
                result = v1.handle_create_book(db, data["data"], idempotency_key)
            elif action == "get_books" and version == "v1":
                result = v1.handle_get_books(db)
            elif action == "get_book" and version == "v1":
                result = v1.handle_get_book(db, data["data"]["book_id"])
            elif action == "update_book" and version == "v1":
                result = v1.handle_update_book(db, data["data"]["book_id"], data["data"])
            elif action == "delete_book" and version == "v1":
                result = v1.handle_delete_book(db, data["data"]["book_id"])
            elif action == "create_book" and version == "v2":
                result = v2.handle_create_book_v2(db, data["data"], idempotency_key)
            elif action == "get_books" and version == "v2":
                result = v2.handle_get_books_v2(db, data["data"].get("genre"))
            elif action == "login":
                result = auth.handle_login(db, data["data"]["username"], data["data"]["password"])
            else:
                result = {"error": "Unknown action or version"}

            if "error" in result:
                await send_response(
                    correlation_id=message.correlation_id,
                    status="error",
                    error=result["error"],
                    reply_to=message.reply_to
                )
            else:
                await send_response(
                    correlation_id=message.correlation_id,
                    status="ok",
                    data=result,
                    reply_to=message.reply_to
                )

        except Exception as e:
            logger.error(f"Error processing {action}: {e}")
            await send_to_dlq(message)
        finally:
            db.close()


async def send_response(correlation_id, status="ok", data=None, error=None, reply_to=None):
    connection = await connect_robust(os.getenv("RABBITMQ_URL"))
    async with connection:
        channel = await connection.channel()
        routing_key = reply_to or "api.responses"  # fallback, но обычно reply_to есть
        await channel.default_exchange.publish(
            Message(
                body=json.dumps({
                    "correlation_id": correlation_id,
                    "status": status,
                    "data": data,
                    "error": error
                }).encode(),
                correlation_id=correlation_id,
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )


async def send_error(correlation_id, error_msg, reply_to=None):
    await send_response(
        correlation_id=correlation_id,
        status="error",
        error=error_msg,
        reply_to=reply_to
    )


async def send_to_dlq(message):
    connection = await connect_robust(os.getenv("RABBITMQ_URL"))
    async with connection:
        channel = await connection.channel()
        await channel.default_exchange.publish(
            Message(body=message.body, headers=message.headers),
            routing_key=DLQ
        )


async def main():
    connection = await connect_robust(os.getenv("RABBITMQ_URL"))
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)

        await channel.declare_queue(REQUEST_QUEUE, durable=True)
        await channel.declare_queue(DLQ, durable=True, arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": REQUEST_QUEUE
        })

        queue = await channel.get_queue(REQUEST_QUEUE)
        logger.info("Server started. Waiting for messages in api.requests...")
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await process_message(message)


if __name__ == "__main__":
    asyncio.run(main())