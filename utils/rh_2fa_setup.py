import logging

import pyotp

logger = logging.getLogger(__name__)
totp = pyotp.TOTP("R2VEYSMKSW75DVU7").now()
print(totp)
logger.info(totp)