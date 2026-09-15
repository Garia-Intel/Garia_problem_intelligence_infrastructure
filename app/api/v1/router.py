from fastapi import APIRouter

from app.api.v1 import documents, health, pipeline, problems, qa, reviews, sources

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(documents.router)
api_router.include_router(problems.router)
api_router.include_router(pipeline.router)
api_router.include_router(qa.router)
api_router.include_router(reviews.router)
