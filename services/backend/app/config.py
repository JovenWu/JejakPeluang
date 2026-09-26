"""Runtime configuration checks.

Development tolerates baked-in defaults; APP_ENV=production fails fast at
startup when any safety-critical value is missing or still its dev default.
"""
import logging
from os import environ

logger = logging.getLogger(__name__)

_DEV_DEFAULTS = {
    'AUTH_SECRET': 'jp-dev-auth-secret-change-me',
    'RATE_LIMIT_SALT': 'jp-dev-rate-limit-salt',
}


def production_mode() -> bool:
    return environ.get('APP_ENV', '').lower() in ('production', 'prod')


def assert_production_config() -> None:
    """Raise RuntimeError listing every unsafe production setting."""
    if not production_mode():
        return
    problems: list[str] = []
    for name, dev_value in _DEV_DEFAULTS.items():
        value = environ.get(name, '')
        if not value or value == dev_value:
            problems.append(f'{name} must be set to a non-default secret')
    if environ.get('COOKIE_SECURE', '').lower() != 'true':
        problems.append('COOKIE_SECURE must be true in production')
    if environ.get('JOB_BROKER', 'redis') == 'redis' and not environ.get(
            'REDIS_URL'):
        problems.append('JOB_BROKER=redis requires REDIS_URL')
    if problems:
        raise RuntimeError('unsafe production configuration: '
            + '; '.join(problems))
    logger.info('production configuration check passed')
