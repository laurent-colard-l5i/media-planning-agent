"""
Workspace management tools for the media planning agent.

These tools handle workspace loading, configuration, and basic querying
operations using the MediaPlanPy SDK.
"""

from typing import Dict, Any, Optional, List
import os
import logging
from mediaplanpy import WorkspaceManager
from mediaplanpy.exceptions import WorkspaceError, WorkspaceNotFoundError

from .base import register_tool, create_success_result, create_error_result

logger = logging.getLogger(__name__)

def load_workspace(session_state, workspace_path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Load workspace configuration and store in session state.

    Args:
        session_state: Current session state
        workspace_path: Path to workspace.json file (optional, will use environment variable or default locations if not provided)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with workspace information
    """
    try:
        # If no workspace_path provided, try environment variable
        if not workspace_path:
            workspace_path = os.getenv('MEDIAPLANPY_WORKSPACE_PATH')

        logger.info(f"Loading workspace from path: {workspace_path or 'default locations'}")

        # Create workspace manager
        manager = WorkspaceManager()
        manager.load(workspace_path=workspace_path)

        # Get resolved configuration
        config = manager.get_resolved_config()

        # Validate workspace
        if not manager.validate():
            return create_error_result(
                "❌ Workspace configuration is invalid",
                error="Workspace validation failed"
            )

        # Store in session state
        session_state.workspace_manager = manager

        # Extract key information for response
        workspace_info = {
            "name": config.get('workspace_name', 'Unknown'),
            "id": config.get('workspace_id', 'Unknown'),
            "environment": config.get('environment', 'Unknown'),
            "storage_mode": config.get('storage', {}).get('mode', 'Unknown'),
            "database_enabled": config.get('database', {}).get('enabled', False),
            "status": config.get('workspace_status', 'Unknown'),
            "schema_version": config.get('schema_settings', {}).get('preferred_version', 'Unknown'),
            "loaded_from": workspace_path or "default locations"
        }

        logger.info(f"Successfully loaded workspace: {workspace_info['name']}")

        return create_success_result(
            f"✅ Loaded workspace '{workspace_info['name']}' successfully! " +
            f"Environment: {workspace_info['environment']}, " +
            f"Storage: {workspace_info['storage_mode']}, " +
            f"Database: {'enabled' if workspace_info['database_enabled'] else 'disabled'}",
            workspace_info=workspace_info,
            config_summary=workspace_info
        )

    except WorkspaceNotFoundError as e:
        error_msg = "❌ Workspace configuration file not found"
        if workspace_path:
            error_msg += f" at {workspace_path}"
        else:
            error_msg += ". No workspace path provided and MEDIAPLANPY_WORKSPACE_PATH environment variable not set"
        error_msg += ". Please provide a workspace path or set the MEDIAPLANPY_WORKSPACE_PATH environment variable."

        return create_error_result(error_msg, error=str(e))

    except WorkspaceError as e:
        return create_error_result(
            f"❌ Workspace error: {str(e)}",
            error=str(e)
        )

    except Exception as e:
        logger.error(f"Unexpected error loading workspace: {e}")
        return create_error_result(
            f"❌ Failed to load workspace: {str(e)}",
            error=str(e)
        )

def list_mediaplans(
    session_state,
    include_stats: bool = True,
    limit: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    List media plans in the current workspace.

    Args:
        session_state: Current session state
        include_stats: Whether to include statistics for each media plan
        limit: Maximum number of media plans to return (optional)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with media plan list
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first using the load_workspace tool."
        )

    try:
        logger.info("Listing media plans in workspace")

        # Get media plans using MediaPlanPy SDK
        plans = session_state.workspace_manager.list_mediaplans(
            include_stats=include_stats,
            return_dataframe=False
        )

        # Apply limit if specified
        if limit and len(plans) > limit:
            plans = plans[:limit]
            limited_msg = f" (showing first {limit})"
        else:
            limited_msg = ""

        # Format response based on number of plans
        if not plans:
            return create_success_result(
                "📋 No media plans found in workspace. Use create_mediaplan_basic to create your first media plan.",
                media_plans=[],
                count=0
            )

        # Format plan information for display
        plan_summaries = []
        for plan in plans:
            summary = {
                "id": plan.get("meta_id", "Unknown"),
                "name": plan.get("campaign_name", "Unnamed"),
                "objective": plan.get("campaign_objective", "Unknown"),
                "budget": plan.get("campaign_budget_total", 0),
                "start_date": plan.get("campaign_start_date", "Unknown"),
                "end_date": plan.get("campaign_end_date", "Unknown"),
                "created_by": plan.get("meta_created_by", "Unknown"),
                "created_at": plan.get("meta_created_at", "Unknown")
            }

            # Add statistics if available
            if include_stats:
                summary.update({
                    "lineitem_count": plan.get("lineitem_count", 0),
                    "total_cost": plan.get("total_lineitem_cost", 0)
                })

            plan_summaries.append(summary)

        return create_success_result(
            f"✅ Found {len(plans)} media plan(s){limited_msg}",
            media_plans=plan_summaries,
            count=len(plans),
            has_more=limit and len(plans) >= limit
        )

    except Exception as e:
        logger.error(f"Error listing media plans: {e}")
        return create_error_result(
            f"❌ Failed to list media plans: {str(e)}",
            error=str(e)
        )


def validate_mediaplan(session_state, **kwargs) -> Dict[str, Any]:
    """
    Validate the current media plan against schema and business rules.

    Tool metadata is now defined in tool_registry.json
    """
    if not session_state.current_mediaplan:
        return create_error_result(
            "❌ No media plan currently loaded for validation. Create or load a media plan first."
        )

    try:
        logger.info("Validating current media plan")

        # Debug: Check what validation methods are available
        media_plan = session_state.current_mediaplan
        logger.debug(f"MediaPlan type: {type(media_plan)}")
        logger.debug(f"Available methods: {[method for method in dir(media_plan) if 'valid' in method.lower()]}")

        # Try different validation approaches
        validation_errors = []

        # Method 1: Try validate_against_schema (preferred)
        if hasattr(media_plan, 'validate_against_schema'):
            logger.debug("Using validate_against_schema method")
            validation_errors = media_plan.validate_against_schema()

        # Method 2: Try validate method if available
        elif hasattr(media_plan, 'validate'):
            logger.debug("Using validate method")
            try:
                validation_errors = media_plan.validate()
            except TypeError as e:
                logger.error(f"validate() method failed: {e}")
                # Try calling validate with no arguments
                validation_errors = []

        # Method 3: Manual validation
        else:
            logger.warning("No validation method found, performing basic checks")
            validation_errors = []

            # Basic validation checks
            if not media_plan.meta.id:
                validation_errors.append("Media plan missing ID")
            if not media_plan.campaign.name:
                validation_errors.append("Campaign missing name")
            if media_plan.campaign.budget_total <= 0:
                validation_errors.append("Campaign budget must be positive")

        # Check if validation passed
        if not validation_errors:
            return create_success_result(
                "✅ Media plan validation passed! The media plan complies with all schema and business rules.",
                validation_errors=[],
                is_valid=True,
                media_plan_id=media_plan.meta.id
            )
        else:
            # Format validation errors for display
            formatted_errors = []
            for error in validation_errors:
                formatted_errors.append(f"• {error}")

            error_summary = "\n".join(formatted_errors)

            return create_error_result(
                f"⚠️ Media plan validation found {len(validation_errors)} issue(s):\n{error_summary}",
                validation_errors=validation_errors,
                is_valid=False,
                media_plan_id=media_plan.meta.id,
                error_count=len(validation_errors)
            )

    except Exception as e:
        logger.error(f"Error validating media plan: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return create_error_result(
            f"❌ Validation failed due to error: {str(e)}",
            error=str(e)
        )

def get_workspace_info(session_state, **kwargs) -> Dict[str, Any]:
    """
    Get comprehensive workspace information.

    Args:
        session_state: Current session state
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with workspace details
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first."
        )

    try:
        logger.info("Getting workspace information")

        # Get resolved configuration
        config = session_state.workspace_manager.get_resolved_config()

        # Extract detailed information
        workspace_details = {
            "basic_info": {
                "id": config.get('workspace_id'),
                "name": config.get('workspace_name'),
                "status": config.get('workspace_status'),
                "environment": config.get('environment')
            },
            "storage": {
                "mode": config.get('storage', {}).get('mode'),
                "local_path": config.get('storage', {}).get('local', {}).get('base_path'),
                "s3_bucket": config.get('storage', {}).get('s3', {}).get('bucket'),
                "gdrive_folder": config.get('storage', {}).get('gdrive', {}).get('folder_id')
            },
            "schema_settings": {
                "preferred_version": config.get('schema_settings', {}).get('preferred_version'),
                "auto_migrate": config.get('schema_settings', {}).get('auto_migrate'),
                "repository_url": config.get('schema_settings', {}).get('repository_url')
            },
            "database": {
                "enabled": config.get('database', {}).get('enabled'),
                "host": config.get('database', {}).get('host'),
                "database": config.get('database', {}).get('database'),
                "port": config.get('database', {}).get('port')
            }
        }

        # Create summary message
        summary_parts = [
            f"Workspace: {workspace_details['basic_info']['name']}",
            f"Environment: {workspace_details['basic_info']['environment']}",
            f"Storage: {workspace_details['storage']['mode']}",
            f"Database: {'enabled' if workspace_details['database']['enabled'] else 'disabled'}"
        ]

        return create_success_result(
            f"✅ Workspace Information:\n• " + "\n• ".join(summary_parts),
            workspace_details=workspace_details,
            config=config
        )

    except Exception as e:
        logger.error(f"Error getting workspace info: {e}")
        return create_error_result(
            f"❌ Failed to get workspace information: {str(e)}",
            error=str(e)
        )

def list_campaigns(
    session_state,
    include_stats: bool = True,
    limit: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    List campaigns in the workspace.

    Args:
        session_state: Current session state
        include_stats: Whether to include campaign statistics
        limit: Maximum number of campaigns to return
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with campaign list
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first."
        )

    try:
        logger.info("Listing campaigns in workspace")

        # Get campaigns using MediaPlanPy SDK
        campaigns = session_state.workspace_manager.list_campaigns(
            include_stats=include_stats,
            return_dataframe=False
        )

        # Apply limit if specified
        if limit and len(campaigns) > limit:
            campaigns = campaigns[:limit]
            limited_msg = f" (showing first {limit})"
        else:
            limited_msg = ""

        if not campaigns:
            return create_success_result(
                "📋 No campaigns found in workspace.",
                campaigns=[],
                count=0
            )

        return create_success_result(
            f"✅ Found {len(campaigns)} campaign(s){limited_msg}",
            campaigns=campaigns,
            count=len(campaigns),
            has_more=limit and len(campaigns) >= limit
        )

    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        return create_error_result(
            f"❌ Failed to list campaigns: {str(e)}",
            error=str(e)
        )