import logging
import sys

def setup_logger():
    # HTTP client INFO logs include signed storage query tokens.
    for name in ('httpx', 'httpcore', 'hpack'):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
