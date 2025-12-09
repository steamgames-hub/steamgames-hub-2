import os
import shutil
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataSet, DSMetaData, DSMetrics, DataCategory, DSDownloadRecord
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder


DATASET_BLUEPRINTS = [
    {
        "title": "Steam Engagement Insights",
        "description": "Aggregated weekly engagement indicators across the top 1,000 Steam games.",
        "data_category": DataCategory.SALES,
        "tags": ["steam", "engagement", "analytics"],
        "authors": [
            {
                "name": "Alex Vega",
                "affiliation": "GameLab Research",
                "orcid": "0000-0000-0000-1001",
            },
            {
                "name": "Marina Chen",
                "affiliation": "Steam Labs",
                "orcid": "0000-0000-0000-1002",
            },
        ],
        "user_ref": "user1",
    },
    {
        "title": "Engagement Forecast Toolkit",
        "description": "Synthetic forecaster features for engagement prediction models.",
        "data_category": DataCategory.GENERAL,
        "tags": ["steam", "engagement", "forecasting"],
        "authors": [
            {
                "name": "Alex Vega",
                "affiliation": "GameLab Research",
                "orcid": "0000-0000-0000-1001",
            },
            {
                "name": "Priya Nayar",
                "affiliation": "Neural Metrics",
                "orcid": "0000-0000-0000-2001",
            },
        ],
        "user_ref": "user2",
    },
    {
        "title": "Community Health Dashboard",
        "description": "KPIs that summarize Steam community health across curated groups.",
        "data_category": DataCategory.OTHER,
        "tags": ["steam", "community", "health"],
        "authors": [
            {
                "name": "Daniel Okafor",
                "affiliation": "Social Play",
                "orcid": "0000-0000-0000-3001",
            },
            {
                "name": "Marina Chen",
                "affiliation": "Steam Labs",
                "orcid": "0000-0000-0000-1002",
            },
        ],
        "user_ref": "user1",
    },
    {
        "title": "Indie Discovery Atlas",
        "description": "Feature set highlighting discoverability drivers for indie launches.",
        "data_category": DataCategory.USER_REVIEWS,
        "tags": ["indie", "sales", "spotlight"],
        "authors": [
            {
                "name": "Sofia Alvarez",
                "affiliation": "IndiePulse",
                "orcid": "0000-0000-0000-4001",
            },
            {
                "name": "Liam Porter",
                "affiliation": "IndiePulse",
                "orcid": "0000-0000-0000-4002",
            },
        ],
        "user_ref": "user2",
    },
    {
        "title": "Indie Revenue Pulse",
        "description": "Weekly sales pulse for trending indie franchises.",
        "data_category": DataCategory.SALES,
        "tags": ["indie", "sales", "revenue"],
        "authors": [
            {
                "name": "Sofia Alvarez",
                "affiliation": "IndiePulse",
                "orcid": "0000-0000-0000-4001",
            },
            {
                "name": "Omar Malik",
                "affiliation": "Revenue R&D",
                "orcid": "0000-0000-0000-5001",
            },
        ],
        "user_ref": "user1",
    },
]


class DataSetSeeder(BaseSeeder):

    priority = 2  # Lower priority
    FILES_PER_DATASET = 2

    def run(self):
        user1 = User.query.filter_by(email="user1@yopmail.com").first()
        user2 = User.query.filter_by(email="user2@yopmail.com").first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        seeded_ds_metrics = self.seed([DSMetrics(number_of_models="5", number_of_features="50")])[0]

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
            for i in range(4)
        ]

        ds_meta_data_list.append(
            DSMetaData(
                deposition_id=4,
                title="New version of sample dataset 4",
                description="Description for dataset 4 v1.1",
                data_category=DataCategory.GENERAL,
                publication_doi="10.1234/dataset4/1.1",
                dataset_doi="10.1234/dataset4/1.1",
                tags="tag1, tag3, tag5",
                ds_metrics_id=seeded_ds_metrics.id,
                version=1.1,
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
        dataset_specs = self._build_dataset_specs(user1.id, user2.id)
        seeded_ds_meta_data = self._seed_ds_metadata(dataset_specs, seeded_ds_metrics.id)
        self._seed_authors(dataset_specs, seeded_ds_meta_data)
        seeded_datasets = self._seed_datasets(dataset_specs, seeded_ds_meta_data)

        seeded_fm_meta_data, seeded_feature_models = self._seed_feature_models(dataset_specs, seeded_datasets)
        self._seed_hubfiles(seeded_fm_meta_data, seeded_feature_models, seeded_datasets)
        self._seed_download_records(seeded_datasets)

    def _build_dataset_specs(self, user1_id: int, user2_id: int):
        user_lookup = {"user1": user1_id, "user2": user2_id}
        specs = []
        for blueprint in DATASET_BLUEPRINTS:
            spec = {
                "title": blueprint["title"],
                "description": blueprint["description"],
                "data_category": blueprint["data_category"],
                "tags": list(blueprint["tags"]),
                "authors": deepcopy(blueprint["authors"]),
                "user_id": user_lookup[blueprint["user_ref"]],
            }
            specs.append(spec)
        return specs

    def _seed_ds_metadata(self, dataset_specs, ds_metrics_id):
        ds_meta_data_list = []
        for idx, spec in enumerate(dataset_specs, start=1):
            ds_meta_data_list.append(
                DSMetaData(
                    deposition_id=500 + idx,
                    title=spec["title"],
                    description=spec["description"],
                    data_category=spec["data_category"],
                    publication_doi=f"10.9999/dataset.{idx}",
                    dataset_doi=f"10.9999/dataset.{idx}",
                    tags=", ".join(spec["tags"]),
                    ds_metrics_id=ds_metrics_id,
                )
            )
        return self.seed(ds_meta_data_list)

    def _seed_authors(self, dataset_specs, seeded_ds_meta_data):
        author_records = []
        for meta, spec in zip(seeded_ds_meta_data, dataset_specs):
            for author in spec["authors"]:
                author_records.append(
                    Author(
                        name=author["name"],
                        affiliation=author["affiliation"],
                        orcid=author["orcid"],
                        ds_meta_data_id=meta.id,
                    )
                )
        if author_records:
            self.seed(author_records)

    def _seed_datasets(self, dataset_specs, seeded_ds_meta_data):
        dataset_records = []
        for meta, spec in zip(seeded_ds_meta_data, dataset_specs):
            dataset_records.append(
                DataSet(
                    user_id=spec["user_id"],
                    ds_meta_data_id=meta.id,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return self.seed(dataset_records)

    def _seed_feature_models(self, dataset_specs, seeded_datasets):
        total_fm = len(dataset_specs) * self.FILES_PER_DATASET
        fm_meta_data_list = []
        for idx in range(total_fm):
            ds_index = idx // self.FILES_PER_DATASET
            file_slot = idx % self.FILES_PER_DATASET + 1
            fm_meta_data_list.append(
                FMMetaData(
                    csv_filename=f"file{idx + 1}.csv",
                    title=f"{dataset_specs[ds_index]['title']} FM {file_slot}",
                    description=f"Feature model {file_slot} for {dataset_specs[ds_index]['title']}",
                    data_category=DataCategory.USER_REVIEWS,
                    publication_doi=f"10.9999/fm.{idx + 1}",
                    tags=", ".join(dataset_specs[ds_index]["tags"]),
                    csv_version="1.0",
                )
            )
        seeded_fm_meta_data = self.seed(fm_meta_data_list)

        # Create Author instances and associate with FMMetaData
        fm_authors = [
            Author(
                name=f"Author {i+6}",
                affiliation=f"Affiliation {i+6}",
                orcid=f"0000-0000-0000-000{i+6}",
                fm_meta_data_id=seeded_fm_meta_data[i].id,
        fm_author_records = []
        for idx, fm_meta in enumerate(seeded_fm_meta_data, start=1):
            fm_author_records.append(
                Author(
                    name=f"FM Author {idx}",
                    affiliation="Automated Seeder",
                    orcid=f"0000-0000-0000-9{idx:03d}",
                    fm_meta_data_id=fm_meta.id,
                )
            )
        self.seed(fm_author_records)

        feature_models = [
            FeatureModel(data_set_id=seeded_datasets[i // 3].id, fm_meta_data_id=seeded_fm_meta_data[i].id)
            for i in range(11)
        ]

        feature_models += [FeatureModel(data_set_id=seeded_datasets[4].id, fm_meta_data_id=seeded_fm_meta_data[11].id)]

        feature_models = []
        for ds_index, dataset in enumerate(seeded_datasets):
            for offset in range(self.FILES_PER_DATASET):
                fm_idx = ds_index * self.FILES_PER_DATASET + offset
                feature_models.append(
                    FeatureModel(data_set_id=dataset.id, fm_meta_data_id=seeded_fm_meta_data[fm_idx].id)
                )
        seeded_feature_models = self.seed(feature_models)
        return seeded_fm_meta_data, seeded_feature_models

    def _seed_hubfiles(self, seeded_fm_meta_data, seeded_feature_models, seeded_datasets):
        load_dotenv()
        working_dir = os.getenv("WORKING_DIR", "")
        src_folder = os.path.join(working_dir, "app", "modules", "dataset", "csv_examples")
        dataset_by_id = {ds.id: ds for ds in seeded_datasets}
        hubfile_records = []
        for idx, feature_model in enumerate(seeded_feature_models):
            file_name = seeded_fm_meta_data[idx].csv_filename
            dataset = dataset_by_id[feature_model.data_set_id]
            user_id = dataset.user_id

            dest_folder = os.path.join(working_dir, "uploads", f"user_{user_id}", f"dataset_{dataset.id}")
            os.makedirs(dest_folder, exist_ok=True)
            shutil.copy(os.path.join(src_folder, file_name), dest_folder)

            file_path = os.path.join(dest_folder, file_name)
            hubfile_records.append(
                Hubfile(
                    name=file_name,
                    checksum=f"checksum{idx + 1}",
                    size=os.path.getsize(file_path),
                    feature_model_id=feature_model.id,
                )
            )
        if hubfile_records:
            self.seed(hubfile_records)

    def _seed_download_records(self, seeded_datasets):
        download_scenarios = [
            (seeded_datasets[0], 5),
            (seeded_datasets[3], 3),
            (seeded_datasets[1], 1),
        ]
        download_records = []
        now = datetime.now(timezone.utc)
        for dataset, count in download_scenarios:
            for i in range(count):
                download_records.append(
                    DSDownloadRecord(
                        user_id=None,
                        dataset_id=dataset.id,
                        download_date=now - timedelta(days=i),
                        download_cookie=f"seed-cookie-{dataset.id}-{i}",
                    )
                )
        if download_records:
            self.seed(download_records)
