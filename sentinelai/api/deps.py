"""Shared API dependencies and singletons."""

from __future__ import annotations

from typing import Optional

from sentinelai.services.analysis import AnalysisService
from sentinelai.services.case_management import AlertService, CaseManagementService

_analysis: Optional[AnalysisService] = None
_cases: Optional[CaseManagementService] = None
_alerts: Optional[AlertService] = None


def get_analysis_service() -> AnalysisService:
    global _analysis
    if _analysis is None:
        _analysis = AnalysisService(cases=get_case_service())
    return _analysis


def get_case_service() -> CaseManagementService:
    global _cases
    if _cases is None:
        _cases = CaseManagementService()
    return _cases


def get_alert_service() -> AlertService:
    global _alerts
    if _alerts is None:
        _alerts = AlertService()
    return _alerts


def reset_services() -> None:
    global _analysis, _cases, _alerts
    _analysis = _cases = _alerts = None
