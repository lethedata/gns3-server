#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from uuid import UUID
from typing import List, Union
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.session import make_transient

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas

TEMPLATE_TYPE_TO_MODEL = {
    "cloud": models.CloudTemplate,
    "docker": models.DockerTemplate,
    "dynamips": models.DynamipsTemplate,
    "ethernet_hub": models.EthernetHubTemplate,
    "ethernet_switch": models.EthernetSwitchTemplate,
    "iou": models.IOUTemplate,
    "qemu": models.QemuTemplate,
    "virtualbox": models.VirtualBoxTemplate,
    "vmware": models.VMwareTemplate,
    "vpcs": models.VPCSTemplate,
}


class TemplatesRepository(BaseRepository):
    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_template(self, template_id: UUID) -> Union[None, models.Template]:

        query = select(models.Template).where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_templates(self) -> List[models.Template]:

        query = select(models.Template)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def create_template(self, template_type: str, template_settings: dict) -> models.Template:

        model = TEMPLATE_TYPE_TO_MODEL[template_type]
        db_template = model(**template_settings)
        self._db_session.add(db_template)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)
        return db_template

    async def update_template(self, template_id: UUID, template_update: schemas.TemplateUpdate) -> schemas.Template:

        update_values = template_update.dict(exclude_unset=True)

        query = update(models.Template). \
            where(models.Template.template_id == template_id). \
            values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        template_db = await self.get_template(template_id)
        if template_db:
            await self._db_session.refresh(template_db)  # force refresh of updated_at value
        return template_db

    async def delete_template(self, template_id: UUID) -> bool:

        query = delete(models.Template).where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return result.rowcount > 0

    async def duplicate_template(self, template_id: UUID) -> schemas.Template:

        query = select(models.Template).where(models.Template.template_id == template_id)
        db_template = (await self._db_session.execute(query)).scalars().first()
        if not db_template:
            return db_template

        # duplicate db object with new primary key (template_id)
        self._db_session.expunge(db_template)
        make_transient(db_template)
        db_template.template_id = None
        self._db_session.add(db_template)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)
        return db_template