"""
SentinelAI Case Management Service
==================================

Service for managing investigation cases and workflow.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from sentinelai.models.schemas import (
    CaseResponse,
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseCommentRequest,
    RiskLevelEnum,
    CaseStatusEnum,
)
from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)


class CaseManagementService:
    """
    Service for managing AML investigation cases.
    
    Provides functionality for case creation, updates,
    assignment, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = get_logger("service.case_management")
        # In-memory storage for demo (use database in production)
        self._cases: Dict[str, Dict[str, Any]] = {}
        self._comments: Dict[str, List[Dict[str, Any]]] = {}
    
    async def create_case(
        self,
        request: CaseCreateRequest,
        analysis_result: Optional[Dict[str, Any]] = None
    ) -> CaseResponse:
        """
        Create a new investigation case.
        
        Args:
            request: Case creation request
            analysis_result: Optional analysis result to attach
            
        Returns:
            Created case response
        """
        case_id = uuid.uuid4()
        case_number = f"CASE-{datetime.utcnow().strftime('%Y%m%d')}-{case_id.hex[:6].upper()}"
        
        now = datetime.utcnow()
        
        case = {
            "id": case_id,
            "case_number": case_number,
            "title": request.title,
            "description": request.description,
            "status": CaseStatusEnum.OPEN,
            "priority": request.priority,
            "assigned_to": request.assigned_to,
            "alert_ids": request.alert_ids,
            "analysis_result": analysis_result,
            "ai_summary": None,
            "ai_recommendation": None,
            "sar_filed": False,
            "review_deadline": now + timedelta(hours=24),
            "sar_deadline": now + timedelta(days=30),
            "created_at": now,
            "updated_at": now,
            "closed_at": None,
        }
        
        self._cases[str(case_id)] = case
        self._comments[str(case_id)] = []
        
        # Add creation comment
        await self.add_comment(
            case_id,
            CaseCommentRequest(
                content=f"Case created: {request.title}",
                comment_type="SYSTEM"
            ),
            author="SYSTEM"
        )
        
        self.logger.info(
            f"Case created: {case_number}",
            extra={"case_id": str(case_id), "priority": request.priority.value}
        )
        
        return self._to_response(case)
    
    async def get_case(self, case_id: uuid.UUID) -> Optional[CaseResponse]:
        """Get a case by ID"""
        case = self._cases.get(str(case_id))
        if case:
            return self._to_response(case)
        return None
    
    async def list_cases(
        self,
        status: Optional[CaseStatusEnum] = None,
        priority: Optional[RiskLevelEnum] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CaseResponse]:
        """
        List cases with optional filters.
        
        Args:
            status: Filter by status
            priority: Filter by priority
            assigned_to: Filter by assignee
            limit: Maximum results
            offset: Result offset
            
        Returns:
            List of matching cases
        """
        cases = list(self._cases.values())
        
        # Apply filters
        if status:
            cases = [c for c in cases if c["status"] == status]
        if priority:
            cases = [c for c in cases if c["priority"] == priority]
        if assigned_to:
            cases = [c for c in cases if c["assigned_to"] == assigned_to]
        
        # Sort by created_at descending
        cases.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Apply pagination
        cases = cases[offset:offset + limit]
        
        return [self._to_response(c) for c in cases]
    
    async def update_case(
        self,
        case_id: uuid.UUID,
        request: CaseUpdateRequest
    ) -> Optional[CaseResponse]:
        """
        Update a case.
        
        Args:
            case_id: Case ID
            request: Update request
            
        Returns:
            Updated case response
        """
        case = self._cases.get(str(case_id))
        if not case:
            return None
        
        old_values = {}
        new_values = {}
        
        if request.status is not None:
            old_values["status"] = case["status"]
            case["status"] = request.status
            new_values["status"] = request.status
            
            if request.status in [
                CaseStatusEnum.CLOSED_NO_ACTION,
                CaseStatusEnum.CLOSED_FALSE_POSITIVE
            ]:
                case["closed_at"] = datetime.utcnow()
        
        if request.priority is not None:
            old_values["priority"] = case["priority"]
            case["priority"] = request.priority
            new_values["priority"] = request.priority
        
        if request.assigned_to is not None:
            old_values["assigned_to"] = case["assigned_to"]
            case["assigned_to"] = request.assigned_to
            new_values["assigned_to"] = request.assigned_to
        
        if request.investigation_notes is not None:
            case["investigation_notes"] = request.investigation_notes
        
        case["updated_at"] = datetime.utcnow()
        
        # Add update comment
        if new_values:
            await self.add_comment(
                case_id,
                CaseCommentRequest(
                    content=f"Case updated: {new_values}",
                    comment_type="SYSTEM"
                ),
                author="SYSTEM"
            )
        
        self.logger.info(
            f"Case updated: {case['case_number']}",
            extra={
                "case_id": str(case_id),
                "changes": new_values
            }
        )
        
        return self._to_response(case)
    
    async def assign_case(
        self,
        case_id: uuid.UUID,
        assignee: str
    ) -> Optional[CaseResponse]:
        """Assign a case to an analyst"""
        return await self.update_case(
            case_id,
            CaseUpdateRequest(assigned_to=assignee)
        )
    
    async def escalate_case(
        self,
        case_id: uuid.UUID,
        reason: str,
        escalated_by: str
    ) -> Optional[CaseResponse]:
        """Escalate a case"""
        case = self._cases.get(str(case_id))
        if not case:
            return None
        
        # Update status
        case["status"] = CaseStatusEnum.ESCALATED
        case["priority"] = RiskLevelEnum.HIGH
        case["updated_at"] = datetime.utcnow()
        
        # Add escalation comment
        await self.add_comment(
            case_id,
            CaseCommentRequest(
                content=f"Case escalated by {escalated_by}. Reason: {reason}",
                comment_type="ESCALATION"
            ),
            author=escalated_by
        )
        
        self.logger.info(
            f"Case escalated: {case['case_number']}",
            extra={"case_id": str(case_id), "escalated_by": escalated_by}
        )
        
        return self._to_response(case)
    
    async def file_sar(
        self,
        case_id: uuid.UUID,
        sar_reference: str,
        filed_by: str
    ) -> Optional[CaseResponse]:
        """Mark case as SAR filed"""
        case = self._cases.get(str(case_id))
        if not case:
            return None
        
        case["status"] = CaseStatusEnum.SAR_FILED
        case["sar_filed"] = True
        case["sar_reference"] = sar_reference
        case["sar_filed_at"] = datetime.utcnow()
        case["updated_at"] = datetime.utcnow()
        
        await self.add_comment(
            case_id,
            CaseCommentRequest(
                content=f"SAR filed by {filed_by}. Reference: {sar_reference}",
                comment_type="DECISION"
            ),
            author=filed_by
        )
        
        self.logger.info(
            f"SAR filed for case: {case['case_number']}",
            extra={"case_id": str(case_id), "sar_reference": sar_reference}
        )
        
        return self._to_response(case)
    
    async def close_case(
        self,
        case_id: uuid.UUID,
        status: CaseStatusEnum,
        reason: str,
        closed_by: str
    ) -> Optional[CaseResponse]:
        """Close a case"""
        if status not in [
            CaseStatusEnum.CLOSED_NO_ACTION,
            CaseStatusEnum.CLOSED_FALSE_POSITIVE,
            CaseStatusEnum.SAR_FILED
        ]:
            raise ValueError("Invalid closing status")
        
        case = self._cases.get(str(case_id))
        if not case:
            return None
        
        case["status"] = status
        case["closed_at"] = datetime.utcnow()
        case["updated_at"] = datetime.utcnow()
        
        await self.add_comment(
            case_id,
            CaseCommentRequest(
                content=f"Case closed by {closed_by}. Status: {status.value}. Reason: {reason}",
                comment_type="DECISION"
            ),
            author=closed_by
        )
        
        self.logger.info(
            f"Case closed: {case['case_number']}",
            extra={"case_id": str(case_id), "status": status.value}
        )
        
        return self._to_response(case)
    
    async def add_comment(
        self,
        case_id: uuid.UUID,
        request: CaseCommentRequest,
        author: str
    ) -> Dict[str, Any]:
        """Add a comment to a case"""
        comment = {
            "id": uuid.uuid4(),
            "case_id": case_id,
            "author": author,
            "content": request.content,
            "comment_type": request.comment_type,
            "created_at": datetime.utcnow()
        }
        
        if str(case_id) not in self._comments:
            self._comments[str(case_id)] = []
        
        self._comments[str(case_id)].append(comment)
        
        # Update case timestamp
        if str(case_id) in self._cases:
            self._cases[str(case_id)]["updated_at"] = datetime.utcnow()
        
        return comment
    
    async def get_comments(
        self,
        case_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Get all comments for a case"""
        return self._comments.get(str(case_id), [])
    
    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get dashboard metrics"""
        cases = list(self._cases.values())
        
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        
        open_cases = [c for c in cases if c["status"] == CaseStatusEnum.OPEN]
        under_review = [c for c in cases if c["status"] == CaseStatusEnum.UNDER_REVIEW]
        escalated = [c for c in cases if c["status"] == CaseStatusEnum.ESCALATED]
        
        # Cases by priority
        by_priority = {}
        for level in RiskLevelEnum:
            by_priority[level.value] = len([
                c for c in open_cases if c["priority"] == level
            ])
        
        # Overdue cases
        overdue = [
            c for c in open_cases
            if c.get("review_deadline") and c["review_deadline"] < now
        ]
        
        return {
            "total_open_cases": len(open_cases),
            "under_review": len(under_review),
            "escalated": len(escalated),
            "overdue_cases": len(overdue),
            "cases_by_priority": by_priority,
            "cases_created_24h": len([
                c for c in cases if c["created_at"] > last_24h
            ]),
            "cases_closed_24h": len([
                c for c in cases
                if c.get("closed_at") and c["closed_at"] > last_24h
            ]),
        }
    
    def _to_response(self, case: Dict[str, Any]) -> CaseResponse:
        """Convert internal case dict to response"""
        return CaseResponse(
            id=case["id"],
            case_number=case["case_number"],
            title=case["title"],
            status=case["status"],
            priority=case["priority"],
            assigned_to=case.get("assigned_to"),
            ai_summary=case.get("ai_summary"),
            ai_recommendation=case.get("ai_recommendation"),
            sar_filed=case.get("sar_filed", False),
            review_deadline=case.get("review_deadline"),
            created_at=case["created_at"],
            updated_at=case["updated_at"]
        )
