from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.opportunities import router as opportunities_router

app = FastAPI(title='JejakPeluang API', version='0.1.0')
app.include_router(health_router, prefix='/api/v1')
app.include_router(opportunities_router, prefix='/api/v1')
