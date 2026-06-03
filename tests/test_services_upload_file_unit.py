from unittest.mock import MagicMock, patch

from src.services.upload_file import UploadFileService


def test_upload_file_builds_cdn_url():
    with patch(
        "src.services.upload_file.cloudinary.uploader.upload",
        return_value={"version": "v123"},
    ) as mock_upload, patch(
        "src.services.upload_file.cloudinary.CloudinaryImage"
    ) as mock_image:
        mock_image.return_value.build_url.return_value = "http://cdn/avatar.png"

        file = MagicMock()
        service = UploadFileService("cloud", "key", "secret")
        url = service.upload_file(file, "tony")

        assert url == "http://cdn/avatar.png"
        mock_upload.assert_called_once()
        mock_image.return_value.build_url.assert_called_once()
