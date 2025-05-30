"""
Media plan management tools for the media planning agent.

These tools handle creating, saving, loading, and deleting media plans
using the MediaPlanPy SDK.
"""

from typing import Dict, Any, Optional, Union
from decimal import Decimal
from datetime import datetime, date
import logging

from mediaplanpy import MediaPlan
from mediaplanpy.exceptions import MediaPlanError, ValidationError

from .base import register_tool, create_success_result, create_error_result

logger = logging.getLogger(__name__)

def create_mediaplan_basic(
    session_state,
    campaign_name: str,
    campaign_objective: str,
    start_date: str,
    end_date: str,
    budget_total: float,
    created_by: str,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
    target_audience_name: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a basic media plan with campaign information.

    Args:
        session_state: Current session state
        campaign_name: Name of the campaign
        campaign_objective: Campaign objective (e.g., 'awareness', 'conversion')
        start_date: Campaign start date (YYYY-MM-DD format)
        end_date: Campaign end date (YYYY-MM-DD format)
        budget_total: Total campaign budget
        created_by: Creator email/identifier
        product_name: Product being advertised (optional)
        product_description: Product description (optional)
        target_audience_name: Target audience description (optional)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with media plan information
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first using load_workspace."
        )

    try:
        logger.info(f"Creating media plan: {campaign_name}")

        # Validate date formats
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError as e:
            return create_error_result(
                f"❌ Invalid date format. Please use YYYY-MM-DD format. Error: {str(e)}",
                error=f"Date parsing error: {str(e)}"
            )

        # Validate budget
        if budget_total <= 0:
            return create_error_result(
                "❌ Budget must be greater than 0",
                error="Invalid budget value"
            )

        # Validate date range
        if start_dt >= end_dt:
            return create_error_result(
                "❌ Start date must be before end date",
                error="Invalid date range"
            )

        # Create media plan using MediaPlanPy SDK
        media_plan = MediaPlan.create(
            created_by=created_by,
            campaign_name=campaign_name,
            campaign_objective=campaign_objective,
            campaign_start_date=start_date,
            campaign_end_date=end_date,
            campaign_budget=budget_total,
            workspace_manager=session_state.workspace_manager,
            product_name=product_name,
            product_description=product_description,
            audience_name=target_audience_name
        )

        # Store in session state
        session_state.current_mediaplan = media_plan

        # Extract information for response
        campaign_info = {
            "media_plan_id": media_plan.meta.id,
            "campaign_id": media_plan.campaign.id,
            "name": media_plan.campaign.name,
            "objective": media_plan.campaign.objective,
            "budget": float(media_plan.campaign.budget_total),
            "start_date": media_plan.campaign.start_date.isoformat(),
            "end_date": media_plan.campaign.end_date.isoformat(),
            "created_by": media_plan.meta.created_by,
            "created_at": media_plan.meta.created_at.isoformat(),
            "schema_version": media_plan.meta.schema_version,
            "lineitem_count": len(media_plan.lineitems)
        }

        logger.info(f"Successfully created media plan: {media_plan.meta.id}")

        return create_success_result(
            f"✅ Created media plan '{campaign_name}' successfully! " +
            f"Budget: ${budget_total:,.2f}, Duration: {start_date} to {end_date}. " +
            f"Ready to add line items or save to workspace.",
            campaign_info=campaign_info,
            media_plan_id=media_plan.meta.id,
            next_steps=[
                "Add line items using create_lineitem",
                "Save the media plan using save_mediaplan",
                "Validate the media plan using validate_mediaplan"
            ]
        )

    except ValidationError as e:
        return create_error_result(
            f"❌ Media plan validation failed: {str(e)}",
            error=str(e)
        )

    except MediaPlanError as e:
        return create_error_result(
            f"❌ Media plan creation failed: {str(e)}",
            error=str(e)
        )

    except Exception as e:
        logger.error(f"Unexpected error creating media plan: {e}")
        return create_error_result(
            f"❌ Failed to create media plan: {str(e)}",
            error=str(e)
        )

@register_tool(
    name="save_mediaplan",
    description="Save the current media plan to workspace storage with optional strategic summary.",
    category="mediaplan"
)
def save_mediaplan(
    session_state,
    include_strategic_summary: bool = True,
    path: Optional[str] = None,
    overwrite: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    Save the current media plan to workspace storage.

    Args:
        session_state: Current session state
        include_strategic_summary: Whether to include strategic context in comments
        path: Optional custom path for saving
        overwrite: Whether to overwrite existing files
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with save information
    """
    if not session_state.current_mediaplan:
        return create_error_result(
            "❌ No media plan to save. Create a media plan first using create_mediaplan_basic."
        )

    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first."
        )

    try:
        logger.info(f"Saving media plan: {session_state.current_mediaplan.meta.id}")

        # Add strategic summary to comments if available and requested
        if include_strategic_summary and session_state.strategic_context:
            strategic_summary = session_state.generate_strategic_summary()
            if strategic_summary:
                session_state.current_mediaplan.meta.comments = strategic_summary
                logger.info("Added strategic summary to media plan comments")

        # Save using MediaPlanPy SDK
        saved_path = session_state.current_mediaplan.save(
            workspace_manager=session_state.workspace_manager,
            path=path,
            overwrite=overwrite,
            include_parquet=True,  # Include Parquet for analytics
            include_database=True  # Include database sync if enabled
        )

        # Get save information
        save_info = {
            "media_plan_id": session_state.current_mediaplan.meta.id,
            "campaign_name": session_state.current_mediaplan.campaign.name,
            "saved_path": saved_path,
            "saved_at": datetime.now().isoformat(),
            "includes_strategic_summary": include_strategic_summary and session_state.strategic_context is not None,
            "lineitem_count": len(session_state.current_mediaplan.lineitems),
            "total_budget": float(session_state.current_mediaplan.campaign.budget_total)
        }

        logger.info(f"Successfully saved media plan to: {saved_path}")

        return create_success_result(
            f"✅ Saved media plan '{session_state.current_mediaplan.campaign.name}' successfully! " +
            f"Location: {saved_path}. " +
            f"The plan is now stored in your workspace and ready for use.",
            save_info=save_info,
            saved_path=saved_path
        )

    except Exception as e:
        logger.error(f"Error saving media plan: {e}")
        return create_error_result(
            f"❌ Failed to save media plan: {str(e)}",
            error=str(e)
        )

@register_tool(
    name="load_mediaplan",
    description="Load an existing media plan from workspace by ID or path.",
    category="mediaplan"
)
def load_mediaplan(
    session_state,
    media_plan_id: Optional[str] = None,
    path: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Load an existing media plan.

    Args:
        session_state: Current session state
        media_plan_id: ID of the media plan to load (preferred)
        path: Path to media plan file (alternative to ID)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with loaded media plan information
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first."
        )

    if not media_plan_id and not path:
        return create_error_result(
            "❌ Please provide either media_plan_id or path to load a media plan."
        )

    try:
        logger.info(f"Loading media plan: {media_plan_id or path}")

        # Load media plan using MediaPlanPy SDK
        media_plan = MediaPlan.load(
            workspace_manager=session_state.workspace_manager,
            media_plan_id=media_plan_id,
            path=path
        )

        # Store in session state
        session_state.current_mediaplan = media_plan

        # Extract information for response
        plan_info = {
            "media_plan_id": media_plan.meta.id,
            "campaign_name": media_plan.campaign.name,
            "campaign_objective": media_plan.campaign.objective,
            "budget": float(media_plan.campaign.budget_total),
            "start_date": media_plan.campaign.start_date.isoformat(),
            "end_date": media_plan.campaign.end_date.isoformat(),
            "created_by": media_plan.meta.created_by,
            "created_at": media_plan.meta.created_at.isoformat(),
            "lineitem_count": len(media_plan.lineitems),
            "has_comments": bool(media_plan.meta.comments),
            "schema_version": media_plan.meta.schema_version
        }

        # Check for strategic context in comments
        context_msg = ""
        if media_plan.meta.comments:
            context_msg = f"\n\nStrategic Context: {media_plan.meta.comments[:200]}"
            if len(media_plan.meta.comments) > 200:
                context_msg += "..."

        logger.info(f"Successfully loaded media plan: {media_plan.meta.id}")

        return create_success_result(
            f"✅ Loaded media plan '{media_plan.campaign.name}' successfully! " +
            f"Budget: ${plan_info['budget']:,.2f}, " +
            f"Line items: {plan_info['lineitem_count']}, " +
            f"Created: {plan_info['created_at'][:10]}" +
            context_msg,
            plan_info=plan_info,
            media_plan_loaded=True
        )

    except Exception as e:
        logger.error(f"Error loading media plan: {e}")
        return create_error_result(
            f"❌ Failed to load media plan: {str(e)}",
            error=str(e)
        )

def delete_mediaplan(
    session_state,
    media_plan_id: str,
    confirm_deletion: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Delete a media plan by ID.

    Args:
        session_state: Current session state
        media_plan_id: ID of the media plan to delete
        confirm_deletion: Must be True to actually delete (safety check)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with deletion information
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first."
        )

    # Safety check - require explicit confirmation
    if not confirm_deletion:
        return create_error_result(
            "⚠️ Media plan deletion requires confirmation for safety. " +
            "Set confirm_deletion=True to proceed with deletion. " +
            "This action cannot be undone.",
            requires_confirmation=True,
            media_plan_id=media_plan_id
        )

    try:
        logger.info(f"Deleting media plan: {media_plan_id}")

        # Load media plan first to get details for confirmation
        media_plan = MediaPlan.load(
            workspace_manager=session_state.workspace_manager,
            media_plan_id=media_plan_id
        )

        campaign_name = media_plan.campaign.name

        # Delete using MediaPlanPy SDK
        deletion_result = media_plan.delete(
            workspace_manager=session_state.workspace_manager,
            dry_run=False,  # Actually delete
            include_database=True  # Also delete from database if enabled
        )

        # Clear from session if it was the current plan
        if (session_state.current_mediaplan and
            session_state.current_mediaplan.meta.id == media_plan_id):
            session_state.current_mediaplan = None
            logger.info("Cleared deleted media plan from session state")

        deletion_info = {
            "media_plan_id": media_plan_id,
            "campaign_name": campaign_name,
            "deleted_at": datetime.now().isoformat(),
            "deleted_files": deletion_result.get("deleted_files", []),
            "database_deleted": deletion_result.get("database_deleted", False)
        }

        logger.info(f"Successfully deleted media plan: {media_plan_id}")

        return create_success_result(
            f"✅ Deleted media plan '{campaign_name}' successfully! " +
            f"Removed {len(deletion_info['deleted_files'])} file(s) from workspace.",
            deletion_info=deletion_info
        )

    except Exception as e:
        logger.error(f"Error deleting media plan: {e}")
        return create_error_result(
            f"❌ Failed to delete media plan: {str(e)}",
            error=str(e)
        )

@register_tool(
    name="create_lineitem",
    description="Add a line item to the current media plan with specified parameters.",
    category="mediaplan"
)
def create_lineitem(
    session_state,
    name: str,
    start_date: str,
    end_date: str,
    cost_total: float,
    channel: Optional[str] = None,
    vehicle: Optional[str] = None,
    partner: Optional[str] = None,
    kpi: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create and add a line item to the current media plan.

    Args:
        session_state: Current session state
        name: Line item name
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        cost_total: Total cost for this line item
        channel: Media channel (e.g., 'social', 'search', 'display')
        vehicle: Media vehicle (e.g., 'Facebook', 'Google')
        partner: Media partner/publisher
        kpi: Key performance indicator
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with line item information
    """
    if not session_state.current_mediaplan:
        return create_error_result(
            "❌ No media plan loaded. Create or load a media plan first."
        )

    try:
        logger.info(f"Creating line item: {name}")

        # Validate dates
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError as e:
            return create_error_result(
                f"❌ Invalid date format. Use YYYY-MM-DD. Error: {str(e)}",
                error=f"Date parsing error: {str(e)}"
            )

        # Validate cost
        if cost_total <= 0:
            return create_error_result(
                "❌ Cost must be greater than 0",
                error="Invalid cost value"
            )

        # Create line item data
        lineitem_data = {
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "cost_total": cost_total
        }

        # Add optional fields if provided
        if channel:
            lineitem_data["channel"] = channel
        if vehicle:
            lineitem_data["vehicle"] = vehicle
        if partner:
            lineitem_data["partner"] = partner
        if kpi:
            lineitem_data["kpi"] = kpi

        # Create line item using MediaPlanPy
        lineitem = session_state.current_mediaplan.create_lineitem(
            line_item=lineitem_data,
            validate=True
        )

        lineitem_info = {
            "id": lineitem.id,
            "name": lineitem.name,
            "cost_total": float(lineitem.cost_total),
            "start_date": lineitem.start_date.isoformat(),
            "end_date": lineitem.end_date.isoformat(),
            "channel": getattr(lineitem, 'channel', None),
            "vehicle": getattr(lineitem, 'vehicle', None),
            "partner": getattr(lineitem, 'partner', None),
            "kpi": getattr(lineitem, 'kpi', None)
        }

        # Calculate updated totals
        total_lineitem_cost = sum(float(li.cost_total) for li in session_state.current_mediaplan.lineitems)
        campaign_budget = float(session_state.current_mediaplan.campaign.budget_total)
        remaining_budget = campaign_budget - total_lineitem_cost

        logger.info(f"Successfully created line item: {lineitem.id}")

        return create_success_result(
            f"✅ Created line item '{name}' successfully! " +
            f"Cost: ${cost_total:,.2f}, " +
            f"Remaining budget: ${remaining_budget:,.2f}",
            lineitem_info=lineitem_info,
            budget_summary={
                "campaign_budget": campaign_budget,
                "allocated_budget": total_lineitem_cost,
                "remaining_budget": remaining_budget,
                "total_lineitems": len(session_state.current_mediaplan.lineitems)
            }
        )

    except Exception as e:
        logger.error(f"Error creating line item: {e}")
        return create_error_result(
            f"❌ Failed to create line item: {str(e)}",
            error=str(e)
        )