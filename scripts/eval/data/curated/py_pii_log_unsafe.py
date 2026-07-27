import logging
def handler(user):
    ssn = user.ssn
    logging.info(ssn)  # privacy: logs a raw SSN
