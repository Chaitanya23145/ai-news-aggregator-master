import logging
from app.database.connection import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Tables created successfully!")
