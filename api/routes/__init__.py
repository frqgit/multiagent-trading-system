"""API Routes.

Modules:
- analysis: Core stock analysis and chat endpoints
- admin: Admin dashboard and user management
- auth: Authentication endpoints
- trading: Advanced trading features (portfolio, backtest, etc.)
"""

from api.routes.admin import router as admin_router
from api.routes.analysis import router as analysis_router
from api.routes.auth import router as auth_router
from api.routes.trading import router as trading_router

__all__ = ["admin_router", "analysis_router", "auth_router", "trading_router"]
