from fastapi import FastAPI  
from fastapi.middleware.cors import CORSMiddleware  

from app.api.generate import router as generate_router  
  
app = FastAPI(  
    title="simple-legal-doc",  
    description="High-assurance legal document generation engine",  
    version="0.1.0",  
)  
  
app.include_router(generate_router, prefix="/generate")  

app.add_middleware(  
    CORSMiddleware,  
    allow_origins=["*"],  
    allow_methods=["*"],  
    allow_headers=["*"],  
)  