from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers.projects import router as api_router
from app.api.routers.projects import ws_router as ws_router  # Import WS router
from app.api.routers.patient_profile import router as patient_router
from app.api.routers.standard_query import router as standard_query_router

def create_app():
    app = FastAPI()
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"]  # Important for downloads
    )
    
    # Include routers
    app.include_router(api_router, prefix="/api/Projects")
    app.include_router(patient_router, prefix="/api/Projects")
    app.include_router(standard_query_router, prefix="/api/Projects")
    app.include_router(ws_router, prefix="/ws-projects")


    
    return app

app = create_app()
# Only for development/testing
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)