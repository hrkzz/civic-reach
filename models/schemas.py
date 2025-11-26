from typing import Literal

from pydantic import BaseModel, Field


class CostDetail(BaseModel):
    """Schema for quantifying specific types of friction (Sludge)."""

    deduction: int = Field(..., description="Points deducted for this category (0-25).")
    comment: str = Field(
        ..., description="Specific analysis and explanation of why these points were deducted."
    )


class EastSuggestions(BaseModel):
    """Schema for behavioral insights based on the EAST framework (UK Behavioral Insights Team)."""

    easy: str = Field(..., description="Improvement suggestion based on 'Easy' (Simplify).")
    attractive: str = Field(
        ..., description="Improvement suggestion based on 'Attractive' (Attention)."
    )
    social: str = Field(..., description="Improvement suggestion based on 'Social' (Norms/Trust).")
    timely: str = Field(..., description="Improvement suggestion based on 'Timely' (Promptness).")


class ExtractedDetail(BaseModel):
    label: str = Field(
        ...,
        description=(
            "The label of the information (e.g., 'Payment Reference', "
            "'Polling Station', 'Hearing Date')."
        ),
    )
    value: str = Field(..., description="The exact extracted value.")
    category: Literal[
        "Deadline",
        "Financial",
        "Identifier",
        "Contact",
        "Action",
        "Legal",
        "Other",
    ] = Field(..., description="The category of this information.")


class SludgeAudit(BaseModel):
    """Master schema for the 'Official' audit report. Calculates a 'Friction Score' and provides actionable feedback."""

    total_score: int = Field(..., description="Total score out of 100 (100 minus sum of deductions).")
    overall_summary: str = Field(..., description="Brief summary of the document context.")
    evaluation_summary: str = Field(..., description="Overall assessment of the audit results.")
    improvement_summary: str = Field(..., description="Summary of recommended improvements.")
    sender_details: str | None = Field(
        None,
        description=(
            "The verbatim text block identifying the Sender (Agency Name, Address). "
            "Return null if not found."
        ),
    )
    recipient_details: str | None = Field(
        None,
        description=(
            "The verbatim text block identifying the Recipient (Name, Address). "
            "Return null if not found."
        ),
    )
    key_details: list[ExtractedDetail] = Field(
        ...,
        description=(
            "[CRITICAL] A dynamic list of the most important factual details extracted from the document."
        ),
    )
    search_cost: CostDetail = Field(..., description="Evaluation of Search Cost.")
    decision_cost: CostDetail = Field(..., description="Evaluation of Decision Cost.")
    cognitive_cost: CostDetail = Field(..., description="Evaluation of Cognitive Cost.")
    emotional_cost: CostDetail = Field(..., description="Evaluation of Emotional Cost.")
    east_suggestions: EastSuggestions = Field(
        ..., description="Detailed improvement suggestions based on the EAST framework."
    )


class CitizenGuide(BaseModel):
    """Master schema for the 'Citizen' assistance guide. Focuses on simplification, translation, and actionability."""

    sludge_observation: str = Field(
        ..., description="Analysis of why this document is difficult (in the target language)."
    )
    simple_summary: str = Field(
        ...,
        description=(
            "A simple summary in the target language. Clearly state 'Who' needs to do 'What'."
        ),
    )
    action_guide_markdown: str = Field(
        ..., description="Step-by-step action guide in Markdown (in the target language)."
    )
    risks_and_penalties: list[str] = Field(
        ...,
        description="★CRITICAL: List of warnings regarding disadvantages, penalties (in the target language).",
    )
    required_documents: list[str] = Field(
        ..., description="List of required documents (translated if necessary)."
    )
    important_dates: list[str] = Field(..., description="List of important dates.")
    missing_info_questions: list[str] = Field(
        ...,
        description=(
            "List of simple questions to ask the user to help them fill out the form or write an email "
            "(e.g., 'What is your full name?', 'What is your Case ID?')."
        ),
    )


