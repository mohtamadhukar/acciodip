import logging
from services import dip_buyer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

def main():
    """
    Main entry point to run dip buying bot.
    """
    dip_buyer.run()

if __name__ == "__main__":
    main()