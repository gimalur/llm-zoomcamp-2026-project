import sys

from loguru import logger

from config import Config


def init_logger():
    logger.remove()

    dev_format = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
        '<level>{level: <8}</level> | '
        '<cyan>{name}</cyan>:<magenta>{function}</magenta>:<yellow>{line}</yellow> - '
        '<level>{message}</level>'
    )

    prod_format = '{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}'

    is_prod = Config.Environment.ENV_TYPE == 'prod'
    log_level = 'INFO' if is_prod else 'DEBUG'
    log_format = prod_format if is_prod else dev_format
    logger.add(
        sys.stderr,
        colorize=not is_prod,
        level=log_level,
        format=log_format,
        enqueue=True,
    )
    return logger.opt(lazy=True)
