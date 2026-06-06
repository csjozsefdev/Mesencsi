"""Rate limiter for demo backend — grafi_core only."""

from grafi_core.security.rate_limits import create_limiter

from demo_backend.settings import demo_core_settings

limiter = create_limiter(demo_core_settings())
