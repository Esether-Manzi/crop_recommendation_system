from datetime import date

# Assume 14 weeks is full crop maturity
FULL_MATURITY_WEEKS = 14


def compute_season_progress(tracker):
    """Compute elapsed weeks/days, current advisory stages, and growth-stage
    tracker progress for a SeasonTracker, relative to today.

    Shared by advisory.views.season_tracker (full detail view) and
    dashboard.views.dashboard_home (compact summary) so both render the
    same growth-week/progress numbers instead of duplicating the thresholds.
    """
    today = date.today()
    elapsed_days = (today - tracker.start_date).days
    elapsed_weeks = max(1, (elapsed_days // 7) + 1)

    # Map growth week to actionable advisory stages, and to one of 4 broad
    # milestones for the visual growth-stage tracker (Planting -> Growing ->
    # Maturing -> Harvest).
    if elapsed_weeks <= 2:
        stages = ["Preparation", "Planting"]
        milestone_index = 0
    elif elapsed_weeks <= 5:
        stages = ["Weeding", "Fertilizer"]
        milestone_index = 1
    elif elapsed_weeks <= 9:
        stages = ["Pests", "Diseases"]
        milestone_index = 2
    else:
        stages = ["Harvest", "Storage"]
        milestone_index = 3

    progress = min(100, int((elapsed_weeks / FULL_MATURITY_WEEKS) * 100))

    return {
        "weeks": elapsed_weeks,
        "days": elapsed_days,
        "stages": stages,
        "progress": progress,
        "milestone_index": milestone_index,
    }
