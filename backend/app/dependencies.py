from fastapi import Depends

from .config import Settings, get_settings
from .services import DataService, RiskAnalyticsService


def get_data_service(settings: Settings = Depends(get_settings)) -> DataService:
    return DataService(settings=settings)


def get_risk_service(
    settings: Settings = Depends(get_settings),
    data_service: DataService = Depends(get_data_service),
) -> RiskAnalyticsService:
    return RiskAnalyticsService(settings=settings, data_service=data_service)
