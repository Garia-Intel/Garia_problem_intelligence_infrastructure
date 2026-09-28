from fastapi import APIRouter

from app.api.v1 import (
    canonical,
    documents,
    health,
    pipeline,
    problems,
    qa,
    quality,
    reviews,
    sources,
    verifications,
    versions,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(documents.router)
api_router.include_router(problems.router)
api_router.include_router(pipeline.router)
api_router.include_router(qa.router)
api_router.include_router(reviews.router)
api_router.include_router(verifications.router)
api_router.include_router(quality.router)
api_router.include_router(versions.router)
api_router.include_router(canonical.router)
api_router.include_router(canonical.candidate_router)
