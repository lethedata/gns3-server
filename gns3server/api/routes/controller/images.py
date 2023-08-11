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

"""
API routes for images.
"""

import os
import logging
import urllib.parse

from fastapi import APIRouter, Request, Response, Depends, status
from starlette.requests import ClientDisconnect
from sqlalchemy.orm.exc import MultipleResultsFound
from typing import List, Optional
from gns3server import schemas

from gns3server.config import Config
from gns3server.utils.images import InvalidImageError, write_image
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerForbiddenError,
    ControllerBadRequestError
)

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.Image])
async def get_images(
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
        image_type: Optional[schemas.ImageType] = None
) -> List[schemas.Image]:
    """
    Return all images.
    """

    return await images_repo.get_images(image_type)


@router.post("/upload/{image_path:path}", response_model=schemas.Image, status_code=status.HTTP_201_CREATED)
async def upload_image(
        image_path: str,
        request: Request,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
        install_appliances: Optional[bool] = False,
) -> schemas.Image:
    """
    Upload an image.

    Example: curl -X POST http://host:port/v3/images/upload/my_image_name.qcow2 \
    -H 'Authorization: Bearer <token>' --data-binary @"/path/to/image.qcow2"
    """

    image_path = urllib.parse.unquote(image_path)
    image_dir, image_name = os.path.split(image_path)
    # check if the path is within the default images directory
    base_images_directory = os.path.expanduser(Config.instance().settings.Server.images_path)
    full_path = os.path.abspath(os.path.join(base_images_directory, image_dir, image_name))
    if os.path.commonprefix([base_images_directory, full_path]) != base_images_directory:
        raise ControllerForbiddenError(f"Cannot write image, '{image_path}' is forbidden")

    if await images_repo.get_image(image_path):
        raise ControllerBadRequestError(f"Image '{image_path}' already exists")

    try:
        allow_raw_image = Config.instance().settings.Server.allow_raw_images
        image = await write_image(image_path, full_path, request.stream(), images_repo, allow_raw_image=allow_raw_image)
    except (OSError, InvalidImageError, ClientDisconnect) as e:
        raise ControllerError(f"Could not save image '{image_path}': {e}")

    if install_appliances:
        # attempt to automatically create templates based on image checksum
        await Controller.instance().appliance_manager.install_appliances_from_image(
            image_path,
            image.checksum,
            images_repo,
            templates_repo,
            rbac_repo,
            current_user,
            os.path.dirname(image.path)
        )

    return image


@router.get("/{image_path:path}", response_model=schemas.Image)
async def get_image(
        image_path: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> schemas.Image:
    """
    Return an image.
    """

    image_path = urllib.parse.unquote(image_path)
    image = await images_repo.get_image(image_path)
    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")
    return image


@router.delete("/{image_path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
        image_path: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Delete an image.
    """

    image_path = urllib.parse.unquote(image_path)

    try:
        image = await images_repo.get_image(image_path)
    except MultipleResultsFound:
        raise ControllerBadRequestError(f"Image '{image_path}' matches multiple images. "
                                        f"Please include the relative path of the image")

    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")

    templates = await images_repo.get_image_templates(image.image_id)
    if templates:
        template_names = ", ".join([template.name for template in templates])
        raise ControllerError(f"Image '{image_path}' is used by one or more templates: {template_names}")

    try:
        os.remove(image.path)
    except OSError:
        log.warning(f"Could not delete image file {image.path}")

    success = await images_repo.delete_image(image_path)
    if not success:
        raise ControllerError(f"Image '{image_path}' could not be deleted")


@router.post("/prune", status_code=status.HTTP_204_NO_CONTENT)
async def prune_images(
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Prune images not attached to any template.
    """

    await images_repo.prune_images()