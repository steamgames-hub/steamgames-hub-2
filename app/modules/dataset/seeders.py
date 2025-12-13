import os
import shutil
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataCategory, DataSet, DSMetaData, DSMetrics
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder


class DataSetSeeder(BaseSeeder):

    priority = 2  # Lower priority

    def run(self):
        # Retrieve users
        user1 = User.query.filter_by(email="user1@yopmail.com").first()
        user2 = User.query.filter_by(email="user2@yopmail.com").first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        # Create DSMetrics instance
        ds_metrics = DSMetrics(number_of_models="5", number_of_features="50")
        seeded_ds_metrics = self.seed([ds_metrics])[0]

        # Create DSMetaData instances (the 4th metadata has 2 versions)
        ds_meta_data_list = [
            DSMetaData(
                deposition_id=1 + i,
                title=f"Sample dataset {i+1}",
                description=f"Description for dataset {i+1}",
                data_category=DataCategory.SALES,
                publication_doi=f"10.1234/dataset{i+1}",
                dataset_doi=f"10.1234/dataset{i+1}",
                tags="tag1, tag2",
                ds_metrics_id=seeded_ds_metrics.id,
                is_latest=i != 3,
            )
            for i in range(3)
        ]

        ds_meta_data_list.append(
            DSMetaData(
                deposition_id=4,
                title="Sample dataset 4",
                description="Description for dataset 4 v1.0",
                data_category=DataCategory.SALES,
                publication_doi="10.1234/dataset4/v1.0",
                dataset_doi="10.1234/dataset4/v1.0",
                tags="tag1, tag2",
                ds_metrics_id=seeded_ds_metrics.id,
                version=1.0,
                is_latest=False,
            )
        )

        ds_meta_data_list.append(
            DSMetaData(
                deposition_id=4,
                title="New version of sample dataset 4",
                description="Description for dataset 4 v2.0",
                data_category=DataCategory.GENERAL,
                publication_doi="10.1234/dataset4",
                dataset_doi="10.1234/dataset4",
                tags="tag1, tag3, tag5",
                ds_metrics_id=seeded_ds_metrics.id,
                version=2.0,
                is_latest=True,
            )
        )
        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # Create Author instances and associate with DSMetaData
        authors = [
            Author(
                name=f"Author {i+1}",
                affiliation=f"Affiliation {i+1}",
                orcid=f"0000-0000-0000-000{i}",
                ds_meta_data_id=seeded_ds_meta_data[i % 5].id,
            )
            for i in range(5)
        ]
        self.seed(authors)

        # Create DataSet instances
        datasets = [
            DataSet(
                user_id=user1.id if (i % 2 == 0 and i < 3) else user2.id,
                ds_meta_data_id=seeded_ds_meta_data[i].id,
                created_at=datetime.now(timezone.utc),
                draft_mode=False,
            )
            for i in range(5)
        ]
        seeded_datasets = self.seed(datasets)

        # Assume there are 12 CSV files, create corresponding FMMetaData and FeatureModel
        fm_meta_data_list = [
            FMMetaData(
                csv_filename=f"file{i+1}.csv",
                title=f"Feature Model {i+1}",
                description=f"Description for feature model {i+1}",
                data_category=DataCategory.USER_REVIEWS,
                publication_doi=f"10.1234/fm{i+1}",
                tags="tag1, tag2",
                csv_version="1.0",
            )
            for i in range(12)
        ]
        seeded_fm_meta_data = self.seed(fm_meta_data_list)

        # Create Author instances and associate with FMMetaData
        fm_authors = [
            Author(
                name=f"Author {i+6}",
                affiliation=f"Affiliation {i+6}",
                orcid=f"0000-0000-0000-000{i+6}",
                fm_meta_data_id=seeded_fm_meta_data[i].id,
            )
            for i in range(12)
        ]
        self.seed(fm_authors)

        feature_models = [
            FeatureModel(data_set_id=seeded_datasets[i // 3].id, fm_meta_data_id=seeded_fm_meta_data[i].id)
            for i in range(11)
        ]

        feature_models += [FeatureModel(data_set_id=seeded_datasets[4].id, fm_meta_data_id=seeded_fm_meta_data[11].id)]

        seeded_feature_models = self.seed(feature_models)

        # Create files, associate them with FeatureModels and copy files
        load_dotenv()
        working_dir = os.getenv("WORKING_DIR", "")
        src_folder = os.path.join(working_dir, "app", "modules", "dataset", "csv_examples")
        for i in range(12):
            file_name = f"file{i+1}.csv"
            feature_model = seeded_feature_models[i]
            dataset = next(ds for ds in seeded_datasets if ds.id == feature_model.data_set_id)
            user_id = dataset.user_id

            dest_folder = os.path.join(working_dir, "uploads", f"user_{user_id}", f"dataset_{dataset.id}")
            os.makedirs(dest_folder, exist_ok=True)
            shutil.copy(os.path.join(src_folder, file_name), dest_folder)

            file_path = os.path.join(dest_folder, file_name)

            csv_file = Hubfile(
                name=file_name,
                checksum=f"checksum{i+1}",
                size=os.path.getsize(file_path),
                feature_model_id=feature_model.id,
            )
            self.seed([csv_file])
