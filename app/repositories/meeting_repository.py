from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.database.schema import Meeting
from app.models.meeting import MeetingModel


class MeetingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, model: MeetingModel) -> MeetingModel:
        entity = Meeting(
            title=model.title,
            description=model.description,
            start_time=model.start_time,
            end_time=model.end_time,
            location=model.location,
            color_gradient=getattr(model, "color_gradient", None),
            user_id=model.user_id,
        )
        self._session.add(entity)
        self._session.commit()
        self._session.refresh(entity)
        model.id = entity.id
        return model

    def get(self, meeting_id: int) -> Optional[MeetingModel]:
        entity = self._session.get(Meeting, meeting_id)
        if not entity:
            return None
        return MeetingModel(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            start_time=entity.start_time,
            end_time=entity.end_time,
            location=entity.location,
            color_gradient=getattr(entity, "color_gradient", None),
            user_id=entity.user_id,
        )

    def list_all(self) -> Iterable[MeetingModel]:
        for entity in self._session.query(Meeting).all():
            yield MeetingModel(
                id=entity.id,
                title=entity.title,
                description=entity.description,
                start_time=entity.start_time,
                end_time=entity.end_time,
                location=entity.location,
                color_gradient=getattr(entity, "color_gradient", None),
                user_id=entity.user_id,
            )

    def update(self, model: MeetingModel) -> Optional[MeetingModel]:
        if model.id is None:
            return None
        entity = self._session.get(Meeting, model.id)
        if not entity:
            return None
        entity.title = model.title
        entity.description = model.description
        entity.start_time = model.start_time
        entity.end_time = model.end_time
        entity.location = model.location
        entity.color_gradient = getattr(model, "color_gradient", None)
        self._session.commit()
        self._session.refresh(entity)
        return model

    def delete(self, meeting_id: int) -> bool:
        entity = self._session.get(Meeting, meeting_id)
        if not entity:
            return False
        self._session.delete(entity)
        self._session.commit()
        return True

