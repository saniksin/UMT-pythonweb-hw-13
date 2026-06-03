import cloudinary
import cloudinary.uploader


class UploadFileService:
    """Wrap Cloudinary's SDK behind a single ``upload_file`` method."""

    def __init__(self, cloud_name: str, api_key: str, api_secret: str) -> None:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    @staticmethod
    def upload_file(file, username: str) -> str:
        """Upload ``file`` to Cloudinary under a per-user public id and
        return a 250×250 cropped CDN URL.
        """
        public_id = f"ContactsApp/{username}"
        result = cloudinary.uploader.upload(
            file.file, public_id=public_id, overwrite=True
        )
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=250, height=250, crop="fill", version=result.get("version")
        )
