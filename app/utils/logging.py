import logging
import sys

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("propvista")
    logger.setLevel(logging.INFO)
    
    # Check if handler is already set
    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        
        # Stream handler for container/console logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logging()
