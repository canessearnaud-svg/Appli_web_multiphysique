import redis
from rq import Worker

from .config import settings

if __name__ == "__main__":
    conn = redis.Redis.from_url(settings.REDIS_URL)
    worker = Worker(["sim"], connection=conn)
    worker.work()
