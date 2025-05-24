import os
import sys
import time
import logging
import requests

DEFAULT_PING_INTERVAL = 240
MAX_FAILURES = 2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)

def get_app_url():
    app_url = os.getenv("APP_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    return app_url

def get_ping_interval():
    try:
        return int(os.getenv("PING_INTERVAL", DEFAULT_PING_INTERVAL))
    except ValueError:
        logging.warning("Invalid PING_INTERVAL value; using default.")
        return DEFAULT_PING_INTERVAL

def get_delay():
    try:
        return int(os.getenv("DELAY", 300))
    except ValueError:
        logging.warning("Invalid DELAY value; using default 300 seconds.")
        return 300

def should_delay_ping():
    return os.getenv("DELAY_PING", "False").lower() in ("true", "1", "yes")

def ping_url(session, url):
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            logging.info(f"Ping successful: {response.status_code} - {url}")
            logger.handlers[0].flush()
            return True
        else:
            logging.warning(f"Ping failed with status: {response.status_code} - {url}")
            logger.handlers[0].flush()
            return False
    except requests.RequestException as e:
        logging.error(f"Error pinging URL: {e}")
        logger.handlers[0].flush()
        return False

def main():
    app_url = get_app_url()
    if not app_url:
        logging.error("No app URL provided. Set the 'APP_URL' environment variable or pass the URL as a command-line argument.")
        logger.handlers[0].flush()
        sys.exit(1)
    
    ping_interval = get_ping_interval()
    logging.info(f"Starting to ping {app_url} every {ping_interval / 60} minutes...")
    logger.handlers[0].flush()
    
    if should_delay_ping():
        delay_seconds = get_delay()
        logging.info(f"Delaying start of pinging by {delay_seconds} seconds as per DELAY_PING setting.")
        logger.handlers[0].flush()
        time.sleep(delay_seconds)
    
    failure_count = 0
    
    with requests.Session() as session:
        try:
            while True:
                success = ping_url(session, app_url)
                if success:
                    failure_count = 0
                else:
                    failure_count += 1
                    if failure_count >= MAX_FAILURES:
                        logging.error(f"Maximum failure count reached ({MAX_FAILURES}). Stopping ping function.")
                        logger.handlers[0].flush()
                        break
                time.sleep(ping_interval)
        except KeyboardInterrupt:
            logging.info("Ping process interrupted by user.")
            logger.handlers[0].flush()

if __name__ == "__main__":
    main()
