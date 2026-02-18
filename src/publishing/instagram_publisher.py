"""
Instagram publisher for posting newsletters as carousel posts.
Uses Instagram Graph API with text-on-image approach.
"""

from pathlib import Path

import httpx

from src.config.settings import settings
from src.models.newsletter import Newsletter
from src.publishing.base import BasePublisher, PublishResult
from src.publishing.formatters.instagram_formatter import InstagramFormatter


class InstagramPublisher(BasePublisher):
    """Publish newsletters to Instagram as carousel posts."""

    GRAPH_API_URL = "https://graph.facebook.com/v18.0"

    def __init__(self):
        """Initialize Instagram publisher."""
        super().__init__("instagram")
        self.formatter = InstagramFormatter()
        self.access_token = settings.instagram_access_token
        self.business_account_id = settings.instagram_business_account_id

    def validate_credentials(self) -> bool:
        """
        Check if Instagram credentials are configured.

        Returns:
            True if credentials are present, False otherwise
        """
        return bool(self.access_token and self.business_account_id)

    async def format_content(self, newsletter: Newsletter) -> tuple[list[Path], str]:
        """
        Format newsletter as Instagram carousel.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Tuple of (list of image paths, caption text)
        """
        return self.formatter.format(newsletter)

    async def publish(self, content: tuple[list[Path], str]) -> PublishResult:
        """
        Post carousel to Instagram.

        Args:
            content: Tuple of (image paths, caption)

        Returns:
            PublishResult with success/failure info
        """
        if not self.validate_credentials():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error="Instagram credentials not configured",
            )

        image_paths, caption = content

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Step 1: Create media containers for each image
                self.logger.info("uploading_images", image_count=len(image_paths))

                container_ids = []
                for i, image_path in enumerate(image_paths):
                    self.logger.info(
                        "uploading_image",
                        image_number=i + 1,
                        total=len(image_paths),
                        path=str(image_path),
                    )

                    container_id = await self._create_image_container(
                        client, image_path, is_carousel_item=True
                    )
                    container_ids.append(container_id)

                self.logger.info("images_uploaded", container_count=len(container_ids))

                # Step 2: Create carousel container
                self.logger.info("creating_carousel")

                carousel_id = await self._create_carousel_container(client, container_ids, caption)

                # Step 3: Publish carousel
                self.logger.info("publishing_carousel", carousel_id=carousel_id)

                post_id = await self._publish_container(client, carousel_id)

                self.logger.info("carousel_published", post_id=post_id)

                # Build post URL
                post_url = f"https://www.instagram.com/p/{post_id}/"

                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    message=f"Published carousel with {len(image_paths)} images",
                    metadata={
                        "post_id": post_id,
                        "post_url": post_url,
                        "image_count": len(image_paths),
                    },
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            self.logger.error("instagram_http_error", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error("instagram_publish_failed", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

    async def _create_image_container(
        self, client: httpx.AsyncClient, image_path: Path, is_carousel_item: bool = False
    ) -> str:
        """
        Upload image and create media container.

        Args:
            client: HTTP client
            image_path: Path to image file
            is_carousel_item: Whether this is part of a carousel

        Returns:
            Container ID
        """
        # Read image file
        with open(image_path, "rb") as f:
            image_data = f.read()

        # First, upload image to get URL (using multipart form)
        # Note: For Instagram Graph API, we need to upload to a hosting service
        # or use image_url parameter with a publicly accessible URL
        # For simplicity, we'll use the container creation with local upload

        url = f"{self.GRAPH_API_URL}/{self.business_account_id}/media"

        # Create form data
        files = {"image": ("image.jpg", image_data, "image/jpeg")}

        data = {
            "access_token": self.access_token,
        }

        if is_carousel_item:
            data["is_carousel_item"] = "true"

        response = await client.post(url, files=files, data=data)
        response.raise_for_status()

        result = response.json()
        return result["id"]

    async def _create_carousel_container(
        self, client: httpx.AsyncClient, container_ids: list[str], caption: str
    ) -> str:
        """
        Create carousel container from media containers.

        Args:
            client: HTTP client
            container_ids: List of media container IDs
            caption: Post caption

        Returns:
            Carousel container ID
        """
        url = f"{self.GRAPH_API_URL}/{self.business_account_id}/media"

        data = {
            "media_type": "CAROUSEL",
            "children": ",".join(container_ids),
            "caption": caption,
            "access_token": self.access_token,
        }

        response = await client.post(url, data=data)
        response.raise_for_status()

        result = response.json()
        return result["id"]

    async def _publish_container(self, client: httpx.AsyncClient, container_id: str) -> str:
        """
        Publish media container to Instagram.

        Args:
            client: HTTP client
            container_id: Container ID to publish

        Returns:
            Published post ID
        """
        url = f"{self.GRAPH_API_URL}/{self.business_account_id}/media_publish"

        data = {"creation_id": container_id, "access_token": self.access_token}

        response = await client.post(url, data=data)
        response.raise_for_status()

        result = response.json()
        return result["id"]
