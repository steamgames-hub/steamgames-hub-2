import logging

from dotenv import load_dotenv
from flask_login import current_user

from app.modules.dataset.models import DataSet
from app.modules.datasetfile.models import DatasetFile
from app.modules.fakenodo.repositories import FakenodoRepository
from core.services.BaseService import BaseService
from core.storage import storage_service

logger = logging.getLogger(__name__)

load_dotenv()


class FakenodoService(BaseService):

    def __init__(self):
        super().__init__(FakenodoRepository())

    def generate_doi(self, record_id: int) -> str:
        return f"10.1234/{record_id}"

    def create_new_deposition(self, dataset: DataSet) -> dict:
        """
        Create a new deposition in Fakenodo.

        Args:
            dataset (DataSet): The DataSet object containing the metadata of the deposition.

        Returns:
            dict: The response in JSON format with the details of the created deposition.
        """

        logger.info("Dataset sending to Fakenodo...")

        fakenodo_element = self.repository.create(commit=True)

        fake_response = {"conceptrecid": 1234, "id": fakenodo_element.dataset_id}

        self.repository.update(
            fakenodo_element.dataset_id,
            associated_doi=self.generate_doi(fakenodo_element.dataset_id),
        )

        return fake_response

    def upload_file(
        self,
        dataset: DataSet,
        deposition_id: int,
        dataset_file: DatasetFile,
        user=None,
    ) -> dict:
        """
        Upload a file to a deposition in Fakenodo.

        Args:
            deposition_id (int): The ID of the deposition in Fakenodo.
            dataset_file (DatasetFile): The DatasetFile object representing the CSV entry.
            user (User): The optional owner overriding the authenticated user.

        Returns:
            dict: The response in JSON format with the details of the uploaded file.
        """
        csv_filename = dataset_file.metadata.csv_filename
        user_id = current_user.id if user is None else user.id
        relative_path = storage_service.dataset_file_path(
            user_id,
            dataset.id,
            csv_filename,
        )
        file_path = storage_service.ensure_local_copy(relative_path)
        return {
            "name": csv_filename,
            "local_path": file_path,
            "deposition_id": deposition_id,
        }

    def get_deposition(self, deposition_id: int) -> dict:
        """
        Get a deposition from Zenodo.

        Args:
            deposition_id (int): The ID of the deposition in Zenodo.

        Returns:
            dict: The response in JSON format with the details of the deposition.
        """
        deposition = self.repository.get_by_id(deposition_id)
        return deposition

    def get_doi(self, deposition_id: int) -> str:
        """
        Get the DOI of a deposition from Fakenodo.

        Args:
            deposition_id (int): The ID of the deposition in Fakenodo.

        Returns:
            str: The DOI of the deposition.
        """

        return self.get_deposition(deposition_id).associated_doi
