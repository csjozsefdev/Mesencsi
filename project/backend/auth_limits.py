"""API rate limiting — delegates to grafi_core with Mesencsi test env key."""

from mesencsi_settings import mesencsi_core_settings
from grafi_core.security.rate_limits import create_limiter

limiter = create_limiter(mesencsi_core_settings())
