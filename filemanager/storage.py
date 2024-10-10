import os
from datetime import datetime
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
import tarfile
import zipfile
from io import BytesIO


class CustomStorage(FileSystemStorage):
    """
    Storage class to handle custom logic such as directory structuring, compression, etc.
    This can be extended in subclasses
    """

    def __init__(self, *args, **kwargs):
        super().__init__(location=settings.MEDIA_ROOT, *args, **kwargs)

    def get_directory_name(self, model_instance):
        """
        Get custom directory structure based on the model and current date
        Structure: media/{model}/{year}/{month}/{id}/
        """
        model_name = model_instance.__class__.__name__.lower()
        today = datetime.now()
        return f"{model_name}/{today.year}/{today.month}/{model_instance.id}"

    def compress(self, file, ostype):
        """
        Compress the provided file based on the OS type
        """
        buffer = BytesIO()

        if ostype in ["LIN", "MAC"]:
            with tarfile.open(fileobj=buffer, mode="w:gz") as tar_file:
                file_content = file.read()
                tarinfo = tarfile.TarInfo(name=file.name)
                tarinfo.size = len(file_content)
                tar_file.addfile(tarinfo, BytesIO(file_content))
            compressed_file = ContentFile(buffer.getvalue(), name=f"{os.path.splitext(file.name)[0]}.tar.gz")

        elif ostype == "WIN":
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                file_content = file.read()
                zip_file.writestr(file.name, file_content)
            compressed_file = ContentFile(buffer.getvalue(), name=f"{os.path.splitext(file.name)[0]}.zip")

        else:
            raise ValueError("Invalid operating system type. Expected 'LIN', 'MAC', or 'WIN'.")

        return compressed_file

    def _save(self, name, content, model_instance, ostype="LIN"):
        """
        Save the file and apply custom directory structure and compression
        """
        directory = self.get_directory_name(model_instance)
        name = os.path.join(directory, name)

        # Compress the file if necessary
        content = self.compress(content, ostype)

        return super()._save(name, content)
