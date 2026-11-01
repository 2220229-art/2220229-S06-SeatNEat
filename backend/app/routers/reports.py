from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Security

from app.deps import SessionDep, get_current_user
from app.models import User
from app.schemas import SummaryRead
from app.services import summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryRead)
def get_summary(
    session: SessionDep,
    _user: Annotated[User, Security(get_current_user, scopes=["reports:read"])],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
) -> SummaryRead:
    return summary(session, date_from, date_to)
