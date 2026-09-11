"""User HTTP API (preferences).

Currently exposes ``GET/PUT /api/users/me/preferences`` for the user's
``language_mode``. Both routes are gated by ``get_current_user`` (any
authenticated user may read/update their own preferences).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user
from app.schemas.auth import PreferencesIn, PreferencesOut
from app.services import preferences as svc

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me/preferences", response_model=PreferencesOut)
def get_prefs(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> PreferencesOut:
    return svc.get_preferences(session, current.user)


@router.put("/me/preferences", response_model=PreferencesOut)
def put_prefs(
    body: PreferencesIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> PreferencesOut:
    # model_fields_set distinguishes "field absent" (leave unchanged) from
    # "field explicitly null" (clear the goal) for the nullable goal fields.
    sent = body.model_fields_set
    goal_date = body.exam_target_date if "exam_target_date" in sent else ...
    goal_count = body.daily_goal_answers if "daily_goal_answers" in sent else ...
    if (
        body.language_mode is None
        and body.interface_language is None
        and goal_date is ...
        and goal_count is ...
    ):
        raise HTTPException(status_code=422, detail="no preferences provided")
    try:
        out = svc.set_preferences(
            session,
            current.user,
            language_mode=body.language_mode,
            interface_language=body.interface_language,
            exam_target_date=goal_date,
            daily_goal_answers=goal_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    return out
