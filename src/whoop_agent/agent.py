"""Claude AI agent for health data analysis and schedule generation."""

import json
from typing import Any

import anthropic

SYSTEM_PROMPT = """\
You are an expert sports scientist, sleep researcher, and health optimization coach. \
You analyze WHOOP wearable data to create personalized weekly health schedules.

Your approach:
- Base every recommendation on the user's actual physiological data
- Consider recovery scores to determine training readiness (green >67%, yellow 34-66%, red <33%)
- Use HRV trends to gauge nervous system readiness
- Analyze sleep patterns to recommend optimal sleep/wake times
- Balance strain across the week to prevent overtraining
- Factor in workout history for variety and progressive overload

When generating a weekly schedule, include for EACH day:
1. **Training recommendation**: workout type, intensity (low/moderate/high), and duration
2. **Recovery focus**: specific recovery activities if needed (active recovery, stretching, mobility)
3. **Sleep target**: recommended bedtime and wake time based on their patterns
4. **Strain target**: target day strain range based on recovery

Format guidelines:
- Use clear day-by-day structure (Monday through Sunday)
- Start with a brief analysis summary of their current trends
- End with key insights and warnings (overtraining risk, sleep debt, etc.)
- Be specific with workout suggestions (not just "exercise" but "30-min zone 2 run" or "strength training - upper body")
- Adapt to their actual workout preferences based on history
"""

SCHEDULE_PROMPT = """\
Here is my WHOOP health data from the past {days} days:

{data}

Based on this data, please:
1. Analyze my recent recovery, sleep, and strain trends
2. Generate a detailed weekly schedule for next week starting Monday
3. Include specific workout recommendations, sleep targets, and recovery strategies
4. Flag any concerns (overtraining, sleep debt, declining HRV, etc.)
"""

SUMMARY_PROMPT = """\
Here is my WHOOP health data from the past {days} days:

{data}

Please provide a concise health summary covering:
1. Recovery trend (improving, stable, declining)
2. Sleep quality analysis
3. Training load assessment
4. Top 3 actionable recommendations
"""

CHAT_SYSTEM_PROMPT = """\
You are a health coach with access to the user's WHOOP data. Answer their questions \
based on their actual physiological data. Be specific and data-driven in your responses.

Here is the user's recent WHOOP data:

{data}
"""


def _create_client(api_key: str) -> anthropic.Anthropic:
    """Create an Anthropic client."""
    return anthropic.Anthropic(api_key=api_key)


def generate_schedule(api_key: str, health_data: dict[str, Any]) -> str:
    """Generate a weekly health schedule based on WHOOP data.

    Args:
        api_key: Anthropic API key.
        health_data: Structured health data from data.fetch_health_data().

    Returns:
        The AI-generated weekly schedule as a string.
    """
    client = _create_client(api_key)
    days = health_data["period"]["days"]
    data_str = json.dumps(health_data, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": SCHEDULE_PROMPT.format(days=days, data=data_str),
            }
        ],
    )

    return response.content[0].text


def generate_summary(api_key: str, health_data: dict[str, Any]) -> str:
    """Generate a health data summary based on WHOOP data.

    Args:
        api_key: Anthropic API key.
        health_data: Structured health data from data.fetch_health_data().

    Returns:
        The AI-generated summary as a string.
    """
    client = _create_client(api_key)
    days = health_data["period"]["days"]
    data_str = json.dumps(health_data, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(days=days, data=data_str),
            }
        ],
    )

    return response.content[0].text


def chat(api_key: str, health_data: dict[str, Any], conversation: list[dict]) -> str:
    """Chat with the AI health coach about your WHOOP data.

    Args:
        api_key: Anthropic API key.
        health_data: Structured health data from data.fetch_health_data().
        conversation: List of message dicts with 'role' and 'content'.

    Returns:
        The AI response as a string.
    """
    client = _create_client(api_key)
    data_str = json.dumps(health_data, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=CHAT_SYSTEM_PROMPT.format(data=data_str),
        messages=conversation,
    )

    return response.content[0].text
