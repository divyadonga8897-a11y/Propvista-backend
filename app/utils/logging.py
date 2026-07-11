import logging
import sys

# Reconfigure stdout and stderr to UTF-8 to support emoji logging on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
