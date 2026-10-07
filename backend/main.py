from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import routes
from api.endpoints import history as history_router
from db.database import init_db

app = FastAPI(title="SafeVision AI Backend", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise database tables on startup
@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(routes.router, prefix="/api")
app.include_router(history_router.router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Backend is running smoothly"}
