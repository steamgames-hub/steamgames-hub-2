import logging
import os

from dotenv import load_dotenv
from flask_login import current_user

from app.modules.dataset.models import DataSet
from app.modules.fakenodo.repositories import FakenodoRepository
from app.modules.featuremodel.models import FeatureModel
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService

logger = logging.getLogger(__name__)

load_dotenv()


class FakenodoService(BaseService):

    def __init__(self):
        super().__init__(FakenodoRepository())

    def generate_doi(self, id: int) -> str:
        return "10.1234" + "/" + str(id)

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
            fakenodo_element.dataset_id, associated_doi=self.generate_doi(fakenodo_element.dataset_id)
        )

        return fake_response

    def upload_file(self, dataset: DataSet, deposition_id: int, feature_model: FeatureModel, user=None) -> dict:
        """
        Upload a file to a deposition in Fakenodo.

        Args:
            deposition_id (int): The ID of the deposition in Fakenodo.
            feature_model (FeatureModel): The FeatureModel object representing the feature model.
            user (FeatureModel): The User object representing the file owner.

        Returns:
            dict: The response in JSON format with the details of the uploaded file.
        """
        csv_filename = feature_model.fm_meta_data.csv_filename
        data = {"name": csv_filename}
        user_id = current_user.id if user is None else user.id
        file_path = os.path.join(uploads_folder_name(), f"user_{str(user_id)}", f"dataset_{dataset.id}/", csv_filename)
        files = {"file": open(file_path, "rb")}

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
