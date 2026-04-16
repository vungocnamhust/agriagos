from __future__ import annotations

from enum import Enum


class AggregateType(str, Enum):
    project_scope = "ProjectScope"
    project_assignment = "ProjectAssignment"
    project_contribution_event = "ProjectContributionEvent"
    project_cost_record = "ProjectCostRecord"
    project_revenue_record = "ProjectRevenueRecord"


class ProjectScopeEventName(str, Enum):
    created = "project_scope.created"
    updated = "project_scope.updated"
    activated = "project_scope.activated"
    paused = "project_scope.paused"
    closed = "project_scope.closed"
    archived = "project_scope.archived"


class ProjectAssignmentEventName(str, Enum):
    created = "project_assignment.created"
    ended = "project_assignment.ended"


class ProjectContributionEventName(str, Enum):
    recorded = "project_contribution.recorded"
    confirmed = "project_contribution.confirmed"
    rejected = "project_contribution.rejected"


class ProjectCostRecordEventName(str, Enum):
    recorded = "project_cost_record.recorded"


class ProjectRevenueRecordEventName(str, Enum):
    recorded = "project_revenue_record.recorded"