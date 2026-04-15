from fastapi import Depends

from .config import Settings, get_settings
from .services import DataService, RiskCalculator


def get_data_service(settings: Settings = Depends(get_settings)) -> DataService:
    return DataService(settings)


def get_risk_calculator(
    settings: Settings = Depends(get_settings),
    data_service: DataService = Depends(get_data_service),
) -> RiskCalculator:
    return RiskCalculator(settings=settings, data_service=data_service)
