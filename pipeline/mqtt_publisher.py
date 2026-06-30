import json
import aiomqtt
import logging

logger = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self, broker_host: str, topic: str):
        self.broker_host = broker_host
        self.topic = topic
        self.client = None

    async def connect(self):
        self.client = aiomqtt.Client(self.broker_host)
        await self.client.__aenter__()

    async def publish(self, payload: dict):
        try:
            await self.client.publish(
                self.topic,
                json.dumps(payload),
                qos=1
            )
            logger.info("Message published")
        except Exception as e:
            logger.exception(f"Publish failed: {e}")

    async def disconnect(self):
        if self.client:
            await self.client.__aexit__(None, None, None)