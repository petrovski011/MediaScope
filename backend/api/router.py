from fastapi import APIRouter

from api.v1 import auth, articles, sources, admin, pipeline, dashboard, export, coordination, narratives, alerts, framings, topics, anomalies, political, userspace, researcher_log

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(articles.router)
router.include_router(sources.router)
router.include_router(admin.router)
router.include_router(pipeline.router)
router.include_router(dashboard.router)
router.include_router(export.router)
router.include_router(coordination.router)
router.include_router(narratives.router)
router.include_router(alerts.router)
router.include_router(framings.router)
router.include_router(topics.router)
router.include_router(anomalies.router)
router.include_router(political.router)
router.include_router(userspace.router)
router.include_router(researcher_log.router)
