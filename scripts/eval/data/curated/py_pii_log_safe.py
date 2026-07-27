import logging
def handler(user):
    order_id = user.order_id
    logging.info(order_id)  # safe: not personal data
