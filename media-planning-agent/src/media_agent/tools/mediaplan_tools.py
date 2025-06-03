"""
Media plan management tools for the media planning agent.

These tools handle creating, saving, loading, and deleting media plans
using the MediaPlanPy SDK.
"""

from typing import Dict, Any, Optional, Union, List
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


def create_lineitem(
        session_state,
        line_items: List[Dict[str, Any]],
        **kwargs
) -> Dict[str, Any]:
    """
    Create one or more line items using MediaPlanPy batch support.

    This tool is now a thin wrapper around the enhanced SDK method that supports
    batch creation with atomic operations and comprehensive validation.

    Args:
        session_state: Current session state
        line_items: List of line item dictionaries. Each dictionary supports
                   all fields from mediaplanschema v1.0.0 specification.
                   Required fields: name, start_date, end_date, cost_total
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with line items information
    """
    # Basic session state validation
    if not session_state.current_mediaplan:
        return create_error_result(
            "❌ No media plan loaded. Create or load a media plan first."
        )

    if not line_items or not isinstance(line_items, list):
        return create_error_result(
            "❌ line_items parameter is required and must be a list of line item objects."
        )

    if len(line_items) == 0:
        return create_error_result(
            "❌ line_items list cannot be empty. Provide at least one line item to create."
        )

    try:
        logger.info(f"Creating {len(line_items)} line item(s) via SDK batch method")

        # Call enhanced SDK method directly - let it handle all validation and business logic
        result = session_state.current_mediaplan.create_lineitem(
            line_items=line_items,
            validate=True  # Let SDK handle comprehensive validation
        )

        # SDK returns List[LineItem] for batch operations
        created_lineitems = result if isinstance(result, list) else [result]

        # Extract information for agent response
        lineitem_summaries = []
        total_cost = 0

        for lineitem in created_lineitems:
            lineitem_info = {
                "id": lineitem.id,
                "name": lineitem.name,
                "cost_total": float(lineitem.cost_total),
                "start_date": lineitem.start_date.isoformat(),
                "end_date": lineitem.end_date.isoformat(),
            }

            # Include optional fields if present
            optional_fields = ['channel', 'vehicle', 'partner', 'kpi', 'target_audience',
                               'location_type', 'location_name', 'adformat']
            for field in optional_fields:
                value = getattr(lineitem, field, None)
                if value is not None:
                    lineitem_info[field] = value

            lineitem_summaries.append(lineitem_info)
            total_cost += float(lineitem.cost_total)

        # Calculate updated budget information
        campaign_budget = float(session_state.current_mediaplan.campaign.budget_total)
        total_allocated = sum(float(li.cost_total) for li in session_state.current_mediaplan.lineitems)
        remaining_budget = campaign_budget - total_allocated

        # Create success response
        success_message = f"✅ Successfully created {len(created_lineitems)} line item(s)! "
        success_message += f"Total cost: ${total_cost:,.2f}, "
        success_message += f"Remaining budget: ${remaining_budget:,.2f}"

        logger.info(f"Successfully created {len(created_lineitems)} line items via SDK")

        return create_success_result(
            success_message,
            lineitems_created=lineitem_summaries,
            created_count=len(created_lineitems),
            budget_summary={
                "campaign_budget": campaign_budget,
                "allocated_budget": total_allocated,
                "remaining_budget": remaining_budget,
                "total_lineitems": len(session_state.current_mediaplan.lineitems)
            }
        )

    except Exception as e:
        # Let SDK exceptions bubble up with clear context
        logger.error(f"SDK create_lineitem failed: {e}")

        # Format SDK error for agent consumption
        error_message = f"❌ Failed to create line items: {str(e)}"

        # Add helpful context based on common error types
        error_context = ""
        error_str = str(e).lower()

        if "budget" in error_str or "exceed" in error_str:
            error_context = "\n💡 Try reducing line item costs or adjusting budget allocation."
        elif "date" in error_str:
            error_context = "\n💡 Check that line item dates are within the campaign period and properly formatted (YYYY-MM-DD)."
        elif "validation" in error_str or "required" in error_str:
            error_context = "\n💡 Ensure all required fields (name, start_date, end_date, cost_total) are provided."
        elif "schema" in error_str:
            error_context = "\n💡 Check that field names and values match the mediaplanschema specification."

        return create_error_result(
            error_message + error_context,
            error=str(e),
            error_type=type(e).__name__,
            suggested_action="review_line_item_data"
        )
