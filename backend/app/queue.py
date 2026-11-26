import redis
from rq import Queue

from .config import settings

redis_conn = redis.Redis.from_url(settings.REDIS_URL)
queue = Queue("sim", connection=redis_conn)
