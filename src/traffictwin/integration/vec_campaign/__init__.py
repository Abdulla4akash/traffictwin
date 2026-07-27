"""Bounded, resumable, sequential execution of predeclared VEC campaigns."""

from traffictwin.integration.vec_campaign.analysis import (
    STANDING_ANALYSIS_LIMITATIONS,
    VEC_CAMPAIGN_ANALYSIS_METHOD_VERSION,
    VecArmDescriptives,
    VecCampaignAnalysis,
    VecCampaignComparison,
    analyze_campaign,
    render_campaign_analysis_markdown,
)
from traffictwin.integration.vec_campaign.models import (
    MAX_CAMPAIGN_CELLS,
    VEC_CAMPAIGN_METHOD_VERSION,
    VEC_CAMPAIGN_SCHEMA_VERSION,
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.integration.vec_campaign.service import (
    STANDING_CAMPAIGN_LIMITATIONS,
    VecCampaignError,
    execute_campaign,
    register_campaign_experiment,
    verify_predeclaration,
)
from traffictwin.integration.vec_campaign.slope_comparison import (
    ActorCapacityCurve,
    ActorSlopeComparison,
    compare_actor_capacity_slopes,
)

__all__ = [
    "ActorCapacityCurve",
    "ActorSlopeComparison",
    "MAX_CAMPAIGN_CELLS",
    "STANDING_ANALYSIS_LIMITATIONS",
    "STANDING_CAMPAIGN_LIMITATIONS",
    "VEC_CAMPAIGN_ANALYSIS_METHOD_VERSION",
    "VEC_CAMPAIGN_METHOD_VERSION",
    "VEC_CAMPAIGN_SCHEMA_VERSION",
    "VecArmDescriptives",
    "VecCampaignAnalysis",
    "VecCampaignApproval",
    "VecCampaignArm",
    "VecCampaignBudget",
    "VecCampaignCell",
    "VecCampaignCellState",
    "VecCampaignComparison",
    "VecCampaignDesign",
    "VecCampaignError",
    "VecCampaignPhase",
    "VecCampaignReceipt",
    "VecCampaignStatus",
    "analyze_campaign",
    "compare_actor_capacity_slopes",
    "execute_campaign",
    "register_campaign_experiment",
    "render_campaign_analysis_markdown",
    "verify_predeclaration",
]
