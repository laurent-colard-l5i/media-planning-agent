"""
Session state management for the media planning agent.

This module handles the conversation session state, strategic context,
and current media plan information during agent interactions.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid


@dataclass
class StrategicContext:
    """Strategic context captured during consultation session."""

    # Basic campaign information
    business_context: str = ""
    objectives: List[str] = field(default_factory=list)

    # Target audience information
    target_audience: Dict[str, Any] = field(default_factory=dict)

    # Budget and timeline
    budget_info: Dict[str, Any] = field(default_factory=dict)
    timeline: Dict[str, str] = field(default_factory=dict)

    # Channel and tactical preferences
    channel_preferences: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)

    # Success metrics and KPIs
    success_metrics: List[str] = field(default_factory=list)

    # Additional context
    industry_context: str = ""
    competitive_context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "business_context": self.business_context,
            "objectives": self.objectives,
            "target_audience": self.target_audience,
            "budget_info": self.budget_info,
            "timeline": self.timeline,
            "channel_preferences": self.channel_preferences,
            "constraints": self.constraints,
            "success_metrics": self.success_metrics,
            "industry_context": self.industry_context,
            "competitive_context": self.competitive_context
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategicContext":
        """Create from dictionary."""
        return cls(**data)


class SessionState:
    """Manages conversation session state and strategic context."""

    def __init__(self):
        self.session_id: str = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.created_at: datetime = datetime.now()

        # Strategic context
        self.strategic_context: Optional[StrategicContext] = None

        # Current working objects
        self.current_mediaplan = None
        self.workspace_manager = None

        # Session history
        self.conversation_history: List[Dict[str, str]] = []
        self.recommendations: List[Dict[str, Any]] = []

        # Session metadata
        self.last_activity: datetime = datetime.now()

    def update_strategic_context(self, context_data: Dict[str, Any]) -> None:
        """Update strategic context with new information."""
        if self.strategic_context is None:
            self.strategic_context = StrategicContext()

        for key, value in context_data.items():
            if hasattr(self.strategic_context, key):
                if isinstance(value, list) and isinstance(getattr(self.strategic_context, key), list):
                    # Extend lists rather than replace
                    existing_list = getattr(self.strategic_context, key)
                    for item in value:
                        if item not in existing_list:
                            existing_list.append(item)
                else:
                    setattr(self.strategic_context, key, value)

        self._update_activity()

    def generate_strategic_summary(self) -> str:
        """Generate concise strategic summary for meta.comments field."""
        if not self.strategic_context:
            return ""

        summary_parts = []

        # Business context (truncated)
        if self.strategic_context.business_context:
            context_short = self.strategic_context.business_context[:80]
            if len(self.strategic_context.business_context) > 80:
                context_short += "..."
            summary_parts.append(f"Context: {context_short}")

        # Objectives
        if self.strategic_context.objectives:
            objectives_str = ", ".join(self.strategic_context.objectives[:3])  # Max 3 objectives
            if len(self.strategic_context.objectives) > 3:
                objectives_str += "..."
            summary_parts.append(f"Objectives: {objectives_str}")

        # Target audience summary
        if self.strategic_context.target_audience:
            audience_parts = []
            if "age_range" in self.strategic_context.target_audience:
                audience_parts.append(f"Age: {self.strategic_context.target_audience['age_range']}")
            if "demographics" in self.strategic_context.target_audience:
                audience_parts.append(self.strategic_context.target_audience['demographics'])
            if audience_parts:
                summary_parts.append(f"Audience: {', '.join(audience_parts)}")

        # Channel preferences
        if self.strategic_context.channel_preferences:
            channels_str = ", ".join(self.strategic_context.channel_preferences[:4])  # Max 4 channels
            if len(self.strategic_context.channel_preferences) > 4:
                channels_str += "..."
            summary_parts.append(f"Channels: {channels_str}")

        # Combine and limit total length
        full_summary = " | ".join(summary_parts)
        return full_summary[:500]  # Limit to 500 chars for comments field

    def add_conversation_turn(self, user_input: str, agent_response: str) -> None:
        """Add conversation turn to history."""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_input,
            "agent": agent_response
        })
        self._update_activity()

    def add_recommendation(self, recommendation: Dict[str, Any]) -> None:
        """Add a strategic recommendation."""
        recommendation["timestamp"] = datetime.now().isoformat()
        recommendation["id"] = f"rec_{len(self.recommendations)}_{uuid.uuid4().hex[:6]}"
        self.recommendations.append(recommendation)
        self._update_activity()

    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current session."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "duration_minutes": (self.last_activity - self.created_at).total_seconds() / 60,
            "conversation_turns": len(self.conversation_history),
            "recommendations_count": len(self.recommendations),
            "has_strategic_context": self.strategic_context is not None,
            "has_current_mediaplan": self.current_mediaplan is not None,
            "workspace_loaded": self.workspace_manager is not None
        }

    def reset_strategic_context(self) -> None:
        """Reset strategic context (useful for starting new media plan)."""
        self.strategic_context = None
        self.recommendations.clear()
        self._update_activity()

    def reset_session(self) -> None:
        """Reset entire session (useful for starting completely fresh)."""
        self.__init__()

    def _update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session state to dictionary (for debugging/logging)."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "strategic_context": self.strategic_context.to_dict() if self.strategic_context else None,
            "conversation_history": self.conversation_history,
            "recommendations": self.recommendations,
            "has_current_mediaplan": self.current_mediaplan is not None,
            "workspace_loaded": self.workspace_manager is not None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Create session state from dictionary (for persistence if needed later)."""
        instance = cls()
        instance.session_id = data.get("session_id", instance.session_id)
        instance.created_at = datetime.fromisoformat(data["created_at"])
        instance.last_activity = datetime.fromisoformat(data["last_activity"])

        if data.get("strategic_context"):
            instance.strategic_context = StrategicContext.from_dict(data["strategic_context"])

        instance.conversation_history = data.get("conversation_history", [])
        instance.recommendations = data.get("recommendations", [])

        return instance