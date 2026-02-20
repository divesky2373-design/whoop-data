"""Fetch and format WHOOP health data for AI analysis."""

from datetime import datetime, timedelta, timezone
from typing import Any

from whoopy import WhoopClient


def _ms_to_hours(ms: int) -> float:
    """Convert milliseconds to hours, rounded to 2 decimal places."""
    return round(ms / 3_600_000, 2)


def _format_recovery(recovery_list: list) -> list[dict[str, Any]]:
    """Format recovery data into a clean summary."""
    results = []
    for r in recovery_list:
        if r.score is None:
            continue
        results.append({
            "date": r.created_at.strftime("%Y-%m-%d"),
            "recovery_score": r.score.recovery_score,
            "resting_heart_rate": r.score.resting_heart_rate,
            "hrv_rmssd_milli": r.score.hrv_rmssd_milli,
            "spo2_percentage": r.score.spo2_percentage,
            "skin_temp_celsius": r.score.skin_temp_celsius,
        })
    return results


def _format_sleep(sleep_list: list) -> list[dict[str, Any]]:
    """Format sleep data into a clean summary."""
    results = []
    for s in sleep_list:
        if s.score is None:
            continue
        entry: dict[str, Any] = {
            "date": s.start.strftime("%Y-%m-%d"),
            "start": s.start.strftime("%H:%M"),
            "end": s.end.strftime("%H:%M"),
            "duration_hours": s.duration_hours,
            "is_nap": s.nap,
            "performance_pct": s.score.sleep_performance_percentage,
            "efficiency_pct": s.score.sleep_efficiency_percentage,
            "consistency_pct": s.score.sleep_consistency_percentage,
            "respiratory_rate": s.score.respiratory_rate,
        }
        stage = s.score.stage_summary
        entry["stages"] = {
            "light_hours": _ms_to_hours(stage.total_light_sleep_time_milli),
            "deep_hours": _ms_to_hours(stage.total_slow_wave_sleep_time_milli),
            "rem_hours": _ms_to_hours(stage.total_rem_sleep_time_milli),
            "awake_hours": _ms_to_hours(stage.total_awake_time_milli),
            "disturbances": stage.disturbance_count,
            "sleep_cycles": stage.sleep_cycle_count,
        }
        need = s.score.sleep_needed
        entry["sleep_needed"] = {
            "baseline_hours": _ms_to_hours(need.baseline_milli),
            "debt_hours": _ms_to_hours(need.need_from_sleep_debt_milli),
            "strain_hours": _ms_to_hours(need.need_from_recent_strain_milli),
            "total_needed_hours": _ms_to_hours(need.total_need_milli),
        }
        results.append(entry)
    return results


def _format_workouts(workout_list: list) -> list[dict[str, Any]]:
    """Format workout data into a clean summary."""
    results = []
    for w in workout_list:
        entry: dict[str, Any] = {
            "date": w.start.strftime("%Y-%m-%d"),
            "start": w.start.strftime("%H:%M"),
            "sport": w.sport_name,
            "duration_hours": w.duration_hours,
        }
        if w.score:
            entry.update({
                "strain": w.score.strain,
                "avg_heart_rate": w.score.average_heart_rate,
                "max_heart_rate": w.score.max_heart_rate,
                "calories": round(w.score.calories, 0),
                "distance_meters": w.score.distance_meter,
            })
            zones = w.score.zone_durations.to_dict_percentage()
            entry["hr_zone_pct"] = {
                k: round(v, 1) for k, v in zones.items()
            }
        results.append(entry)
    return results


def _format_cycles(cycle_list: list) -> list[dict[str, Any]]:
    """Format cycle data into a clean summary."""
    results = []
    for c in cycle_list:
        entry: dict[str, Any] = {
            "date": c.start.strftime("%Y-%m-%d"),
            "duration_hours": c.duration_hours,
            "is_complete": c.is_complete,
        }
        if c.score:
            entry.update({
                "day_strain": c.score.strain,
                "avg_heart_rate": c.score.average_heart_rate,
                "max_heart_rate": c.score.max_heart_rate,
                "calories": round(c.score.calories, 0),
            })
        results.append(entry)
    return results


def fetch_health_data(client: WhoopClient, days: int = 14) -> dict[str, Any]:
    """Fetch recent WHOOP health data and return a structured summary.

    Args:
        client: Authenticated WHOOP client.
        days: Number of days of data to fetch (default 14).

    Returns:
        Dictionary with recovery, sleep, workouts, and cycles data.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    recovery_data = client.recovery.get_all(start=start, end=end)
    sleep_data = client.sleep.get_all(start=start, end=end)
    workout_data = client.workouts.get_all(start=start, end=end)
    cycle_data = client.cycles.get_all(start=start, end=end)

    # Get user profile for context
    profile = client.user.get_profile()

    return {
        "period": {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "days": days,
        },
        "user": {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
        },
        "recovery": _format_recovery(recovery_data),
        "sleep": _format_sleep(sleep_data),
        "workouts": _format_workouts(workout_data),
        "cycles": _format_cycles(cycle_data),
    }
