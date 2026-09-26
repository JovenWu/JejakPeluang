from fastapi import FastAPI
from app.api.auth import auth_router, users_router
from app.api.health import router as health_router
from app.api.opportunities import router as opportunities_router
from app.api.submissions import router as submissions_router
from app.security import CsrfOriginMiddleware

app = FastAPI(title='JejakPeluang API', version='0.1.0')
app.add_middleware(CsrfOriginMiddleware)
app.include_router(health_router, prefix='/api/v1')
app.include_router(opportunities_router, prefix='/api/v1')
app.include_router(submissions_router, prefix='/api/v1')
app.include_router(auth_router, prefix='/api/v1/auth')
app.include_router(users_router, prefix='/api/v1/users')
