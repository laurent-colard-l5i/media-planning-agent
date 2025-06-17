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


def load_workspace(
        session_state,
        workspace_path: Optional[str] = None,
        workspace_id: Optional[str] = None,
        **kwargs
) -> Dict[str, Any]:
    """
    Load workspace configuration and store in session state.
    Supports both direct path loading and workspace ID-based loading.

    Args:
        session_state: Current session state
        workspace_path: Direct path to workspace.json file (optional)
        workspace_id: Workspace ID for automatic file discovery (optional)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with workspace information
    """
    # Validate input parameters
    if workspace_path and workspace_id:
        return create_error_result(
            "❌ Please provide either workspace_path OR workspace_id, not both.",
            error="Conflicting parameters"
        )

    try:
        # Determine loading method and log appropriately
        if workspace_id:
            logger.info(f"Loading workspace by ID: {workspace_id}")
            load_method = "workspace_id"
            load_value = workspace_id
        elif workspace_path:
            logger.info(f"Loading workspace from path: {workspace_path}")
            load_method = "workspace_path"
            load_value = workspace_path
        else:
            # Neither provided - try environment variable for path, then fall back to SDK defaults
            env_workspace_path = os.getenv('MEDIAPLANPY_WORKSPACE_PATH')
            if env_workspace_path:
                logger.info(f"Loading workspace from environment variable: {env_workspace_path}")
                load_method = "workspace_path"
                load_value = env_workspace_path
            else:
                logger.info("Loading workspace using SDK default discovery")
                load_method = "default"
                load_value = None

        # Create workspace manager
        manager = WorkspaceManager()

        # Call SDK load method with appropriate parameters
        if load_method == "workspace_id":
            manager.load(workspace_id=workspace_id)
            loaded_from = f"workspace ID: {workspace_id}"
        elif load_method == "workspace_path":
            manager.load(workspace_path=load_value)
            loaded_from = f"path: {load_value}"
        else:
            # Default discovery - let SDK handle it
            manager.load()
            loaded_from = "SDK auto-discovery"

        # Get resolved configuration
        config = manager.get_resolved_config()

        # Validate workspace
        if not manager.validate():
            return create_error_result(
                "❌ Workspace configuration is invalid. Please check your workspace settings.",
                error="Workspace validation failed",
                loaded_from=loaded_from
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
            "loaded_from": loaded_from,
            "loading_method": load_method
        }

        # Create success message based on loading method
        if load_method == "workspace_id":
            success_msg = f"✅ Loaded workspace '{workspace_info['name']}' (ID: {workspace_info['id']}) successfully!"
        elif workspace_path:
            success_msg = f"✅ Loaded workspace '{workspace_info['name']}' from specified path successfully!"
        elif load_value:  # Environment variable
            success_msg = f"✅ Loaded workspace '{workspace_info['name']}' from environment configuration successfully!"
        else:
            success_msg = f"✅ Discovered and loaded workspace '{workspace_info['name']}' automatically!"

        # Add configuration details to message
        success_msg += f" Environment: {workspace_info['environment']}, "
        success_msg += f"Storage: {workspace_info['storage_mode']}, "
        success_msg += f"Database: {'enabled' if workspace_info['database_enabled'] else 'disabled'}"

        logger.info(f"Successfully loaded workspace: {workspace_info['name']} via {load_method}")

        return create_success_result(
            success_msg,
            workspace_info=workspace_info,
            config_summary=workspace_info
        )

    except WorkspaceNotFoundError as e:
        # Enhanced error messaging based on loading method
        if workspace_id:
            error_msg = f"❌ Workspace with ID '{workspace_id}' not found. "
            error_msg += "Please verify the workspace ID is correct and the workspace exists in your configured storage locations."
        elif workspace_path:
            error_msg = f"❌ Workspace configuration file not found at '{workspace_path}'. "
            error_msg += "Please verify the path is correct and the file exists."
        else:
            error_msg = "❌ No workspace configuration found. "
            if not os.getenv('MEDIAPLANPY_WORKSPACE_PATH'):
                error_msg += "Try providing a workspace_id, workspace_path, or set the MEDIAPLANPY_WORKSPACE_PATH environment variable."
            else:
                error_msg += f"The environment path '{os.getenv('MEDIAPLANPY_WORKSPACE_PATH')}' does not contain a valid workspace."

        return create_error_result(
            error_msg,
            error=str(e),
            loading_method=load_method,
            attempted_value=load_value
        )

    except WorkspaceError as e:
        error_msg = f"❌ Workspace error"
        if load_method == "workspace_id":
            error_msg += f" loading workspace ID '{workspace_id}'"
        elif load_value:
            error_msg += f" loading from '{load_value}'"
        error_msg += f": {str(e)}"

        return create_error_result(
            error_msg,
            error=str(e),
            loading_method=load_method
        )

    except Exception as e:
        logger.error(f"Unexpected error loading workspace via {load_method}: {e}")
        error_msg = f"❌ Failed to load workspace"
        if load_method == "workspace_id":
            error_msg += f" with ID '{workspace_id}'"
        elif load_value:
            error_msg += f" from '{load_value}'"
        error_msg += f": {str(e)}"

        return create_error_result(
            error_msg,
            error=str(e),
            loading_method=load_method
        )


def list_mediaplans(
        session_state,
        include_stats: bool = True,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
) -> Dict[str, Any]:
    """
    List media plans in the current workspace with optional filtering.

    Args:
        session_state: Current session state
        include_stats: Whether to include statistics for each media plan
        limit: Maximum number of media plans to return (optional)
        filters: Dictionary of filters to apply. Supports multiple filter types:
                - Exact match: {"field": "value"}
                - List/IN match: {"field": ["value1", "value2"]}
                - Range filter: {"field": {"min": 100, "max": 500}}
                - Regex filter: {"field": {"regex": "pattern"}}
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with filtered media plan list
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first using the load_workspace tool."
        )

    try:
        logger.info(f"Listing media plans in workspace with filters: {filters}")

        # Validate filters if provided
        if filters:
            validation_result = _validate_filters(filters)
            if not validation_result["valid"]:
                return create_error_result(
                    f"❌ Invalid filter format: {validation_result['error']}",
                    error=validation_result['error'],
                    filter_examples=_get_filter_examples()
                )

        # Get media plans using MediaPlanPy SDK with filters
        plans = session_state.workspace_manager.list_mediaplans(
            filters=filters,
            include_stats=include_stats,
            return_dataframe=False
        )

        # Apply limit if specified (post-filtering)
        original_count = len(plans)
        if limit and len(plans) > limit:
            plans = plans[:limit]
            limited_msg = f" (showing first {limit} of {original_count})"
        else:
            limited_msg = ""

        # Create filter summary for user feedback
        filter_summary = ""
        if filters:
            filter_parts = []
            for field, filter_value in filters.items():
                if isinstance(filter_value, list):
                    filter_parts.append(f"{field} in {filter_value}")
                elif isinstance(filter_value, dict):
                    if 'min' in filter_value and 'max' in filter_value:
                        filter_parts.append(f"{field} between {filter_value['min']} and {filter_value['max']}")
                    elif 'min' in filter_value:
                        filter_parts.append(f"{field} >= {filter_value['min']}")
                    elif 'max' in filter_value:
                        filter_parts.append(f"{field} <= {filter_value['max']}")
                    elif 'regex' in filter_value:
                        filter_parts.append(f"{field} matches '{filter_value['regex']}'")
                else:
                    filter_parts.append(f"{field} = {filter_value}")

            if filter_parts:
                filter_summary = f"\n🔍 Applied filters: {', '.join(filter_parts)}"

        # Format response based on number of plans
        if not plans:
            if filters:
                return create_success_result(
                    f"📋 No media plans found matching the specified filters.{filter_summary}" +
                    "\n💡 Try adjusting your filter criteria or use 'list_mediaplans' without filters to see all plans.",
                    media_plans=[],
                    count=0,
                    filters_applied=filters
                )
            else:
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
                "created_by": plan.get("meta_created_by_name", plan.get("meta_created_by", "Unknown")),
                # Handle both v1.0 and v2.0
                "created_at": plan.get("meta_created_at", "Unknown")
            }

            # Add statistics if available
            if include_stats:
                summary.update({
                    "lineitem_count": plan.get("stat_lineitem_count", 0),
                    "total_cost": plan.get("stat_total_cost", 0),
                    "allocated_budget": plan.get("stat_total_cost", 0),  # Alias for clarity
                    "remaining_budget": max(0, summary["budget"] - plan.get("stat_total_cost", 0))
                })

                # Add channel diversity stats if available
                channel_count = plan.get("stat_distinct_channel_count", 0)
                vehicle_count = plan.get("stat_distinct_vehicle_count", 0)
                if channel_count > 0 or vehicle_count > 0:
                    summary["channel_diversity"] = {
                        "distinct_channels": channel_count,
                        "distinct_vehicles": vehicle_count
                    }

            plan_summaries.append(summary)

        success_message = f"✅ Found {len(plans)} media plan(s){limited_msg}"
        if filter_summary:
            success_message += filter_summary

        logger.info(f"Successfully listed {len(plans)} media plans with filters applied")

        return create_success_result(
            success_message,
            media_plans=plan_summaries,
            count=len(plans),
            original_count=original_count if limit else len(plans),
            has_more=limit and original_count > limit,
            filters_applied=filters
        )

    except Exception as e:
        logger.error(f"Error listing media plans: {e}")
        return create_error_result(
            f"❌ Failed to list media plans: {str(e)}",
            error=str(e),
            filters_applied=filters
        )


def _validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate filter format and provide helpful error messages.

    Args:
        filters: Dictionary of filters to validate

    Returns:
        Dictionary with 'valid' boolean and 'error' message if invalid
    """
    if not isinstance(filters, dict):
        return {
            "valid": False,
            "error": "Filters must be a dictionary with field names as keys"
        }

    for field, filter_value in filters.items():
        if not isinstance(field, str):
            return {
                "valid": False,
                "error": f"Filter field names must be strings, got {type(field)}"
            }

        # Check filter value types
        if isinstance(filter_value, dict):
            # Range or regex filter
            valid_keys = {'min', 'max', 'regex'}
            if not any(key in filter_value for key in valid_keys):
                return {
                    "valid": False,
                    "error": f"Dictionary filters must contain 'min', 'max', or 'regex' keys, got {list(filter_value.keys())}"
                }

            # Validate range filters have comparable values
            if 'min' in filter_value and 'max' in filter_value:
                try:
                    if filter_value['min'] > filter_value['max']:
                        return {
                            "valid": False,
                            "error": f"Range filter min ({filter_value['min']}) cannot be greater than max ({filter_value['max']})"
                        }
                except TypeError:
                    return {
                        "valid": False,
                        "error": f"Range filter min and max values must be comparable types"
                    }

        elif isinstance(filter_value, list):
            # List filter
            if len(filter_value) == 0:
                return {
                    "valid": False,
                    "error": f"List filters cannot be empty for field '{field}'"
                }
        # Scalar values (str, int, float, bool) are always valid

    return {"valid": True, "error": None}


def _get_filter_examples() -> Dict[str, Any]:
    """Get example filter formats for error messages."""
    return {
        "exact_match": {"campaign_objective": "awareness"},
        "list_match": {"campaign_objective": ["awareness", "consideration"]},
        "range_filter": {"campaign_budget_total": {"min": 50000, "max": 200000}},
        "regex_filter": {"campaign_name": {"regex": ".*Summer.*"}},
        "date_range": {"campaign_start_date": {"min": "2025-01-01", "max": "2025-12-31"}},
        "combined": {
            "campaign_objective": ["awareness", "consideration"],
            "campaign_budget_total": {"min": 100000}
        }
    }

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
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
) -> Dict[str, Any]:
    """
    List campaigns in the workspace with optional filtering.

    Args:
        session_state: Current session state
        include_stats: Whether to include campaign statistics
        limit: Maximum number of campaigns to return (optional)
        filters: Dictionary of filters to apply. Supports multiple filter types:
                - Exact match: {"field": "value"}
                - List/IN match: {"field": ["value1", "value2"]}
                - Range filter: {"field": {"min": 100, "max": 500}}
                - Regex filter: {"field": {"regex": "pattern"}}
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        Success/error result with filtered campaign list
    """
    if not session_state.workspace_manager:
        return create_error_result(
            "❌ No workspace loaded. Please load a workspace first using the load_workspace tool."
        )

    try:
        logger.info(f"Listing campaigns in workspace with filters: {filters}")

        # Validate filters if provided (reuse helper from list_mediaplans)
        if filters:
            validation_result = _validate_filters(filters)
            if not validation_result["valid"]:
                return create_error_result(
                    f"❌ Invalid filter format: {validation_result['error']}",
                    error=validation_result['error'],
                    filter_examples=_get_campaign_filter_examples()
                )

        # Get campaigns using MediaPlanPy SDK with filters
        campaigns = session_state.workspace_manager.list_campaigns(
            filters=filters,
            include_stats=include_stats,
            return_dataframe=False
        )

        # Apply limit if specified (post-filtering)
        original_count = len(campaigns)
        if limit and len(campaigns) > limit:
            campaigns = campaigns[:limit]
            limited_msg = f" (showing first {limit} of {original_count})"
        else:
            limited_msg = ""

        # Create filter summary for user feedback
        filter_summary = ""
        if filters:
            filter_parts = []
            for field, filter_value in filters.items():
                if isinstance(filter_value, list):
                    filter_parts.append(f"{field} in {filter_value}")
                elif isinstance(filter_value, dict):
                    if 'min' in filter_value and 'max' in filter_value:
                        filter_parts.append(f"{field} between {filter_value['min']} and {filter_value['max']}")
                    elif 'min' in filter_value:
                        filter_parts.append(f"{field} >= {filter_value['min']}")
                    elif 'max' in filter_value:
                        filter_parts.append(f"{field} <= {filter_value['max']}")
                    elif 'regex' in filter_value:
                        filter_parts.append(f"{field} matches '{filter_value['regex']}'")
                else:
                    filter_parts.append(f"{field} = {filter_value}")

            if filter_parts:
                filter_summary = f"\n🔍 Applied filters: {', '.join(filter_parts)}"

        # Format response based on number of campaigns
        if not campaigns:
            if filters:
                return create_success_result(
                    f"📋 No campaigns found matching the specified filters.{filter_summary}" +
                    "\n💡 Try adjusting your filter criteria or use 'list_campaigns' without filters to see all campaigns.",
                    campaigns=[],
                    count=0,
                    filters_applied=filters
                )
            else:
                return create_success_result(
                    "📋 No campaigns found in workspace. Create your first media plan to see campaigns here.",
                    campaigns=[],
                    count=0
                )

        # Format campaign information for display
        campaign_summaries = []
        for campaign in campaigns:
            summary = {
                "id": campaign.get("campaign_id", "Unknown"),
                "name": campaign.get("campaign_name", "Unnamed"),
                "objective": campaign.get("campaign_objective", "Unknown"),
                "budget": campaign.get("campaign_budget_total", 0),
                "start_date": campaign.get("campaign_start_date", "Unknown"),
                "end_date": campaign.get("campaign_end_date", "Unknown")
            }

            # Add statistics if available
            if include_stats:
                # Basic stats
                summary.update({
                    "media_plan_count": campaign.get("stat_media_plan_count", 0),
                    "lineitem_count": campaign.get("stat_lineitem_count", 0),
                    "total_cost": campaign.get("stat_total_cost", 0),
                    "allocated_budget": campaign.get("stat_total_cost", 0),  # Alias for clarity
                    "remaining_budget": max(0, summary["budget"] - campaign.get("stat_total_cost", 0)),
                    "last_updated": campaign.get("stat_last_updated", "Unknown")
                })

                # Timeline stats
                if campaign.get("stat_min_start_date"):
                    summary["earliest_start"] = campaign["stat_min_start_date"]
                if campaign.get("stat_max_end_date"):
                    summary["latest_end"] = campaign["stat_max_end_date"]

                # Channel diversity and dimension stats
                channel_stats = {}
                dimension_fields = ['channel', 'vehicle', 'partner', 'media_product', 'adformat', 'kpi',
                                    'location_name']

                for dim in dimension_fields:
                    count_field = f"stat_distinct_{dim}_count"
                    if campaign.get(count_field, 0) > 0:
                        channel_stats[f"distinct_{dim}s"] = campaign[count_field]

                if channel_stats:
                    summary["channel_diversity"] = channel_stats

                # Performance indicators (if campaign has line items)
                if summary["lineitem_count"] > 0:
                    summary["avg_cost_per_lineitem"] = summary["total_cost"] / summary["lineitem_count"]
                    summary["budget_utilization"] = (summary["total_cost"] / summary["budget"] * 100) if summary[
                                                                                                             "budget"] > 0 else 0

            campaign_summaries.append(summary)

        success_message = f"✅ Found {len(campaigns)} campaign(s){limited_msg}"
        if filter_summary:
            success_message += filter_summary

        logger.info(f"Successfully listed {len(campaigns)} campaigns with filters applied")

        return create_success_result(
            success_message,
            campaigns=campaign_summaries,
            count=len(campaigns),
            original_count=original_count if limit else len(campaigns),
            has_more=limit and original_count > limit,
            filters_applied=filters
        )

    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        return create_error_result(
            f"❌ Failed to list campaigns: {str(e)}",
            error=str(e),
            filters_applied=filters
        )


def _get_campaign_filter_examples() -> Dict[str, Any]:
    """Get example filter formats specific to campaigns."""
    return {
        "exact_match": {"campaign_objective": "awareness"},
        "list_match": {"campaign_objective": ["awareness", "consideration"]},
        "range_filter": {"campaign_budget_total": {"min": 50000, "max": 200000}},
        "regex_filter": {"campaign_name": {"regex": ".*Q[1-4].*"}},
        "date_range": {"campaign_start_date": {"min": "2025-01-01", "max": "2025-12-31"}},
        "performance_filter": {"stat_lineitem_count": {"min": 5}},
        "combined": {
            "campaign_objective": ["awareness", "consideration"],
            "campaign_budget_total": {"min": 100000},
            "stat_distinct_channel_count": {"min": 3}
        }
    }