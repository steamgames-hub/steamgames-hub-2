import hashlib
import os
import shutil
from datetime import datetime, timezone

import click
from dotenv import load_dotenv
from flask.cli import with_appcontext

from app import create_app, db
from app.modules.auth.models import User
from app.modules.dataset.models import (
    DataSet,
    DSMetaData,
    DSMetrics,
    DataSet,
    DataCategory,
)
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@click.command(
    "datasets:import",
    help=(
        "Create a new dataset for a user and attach all CSV files "
        "from the given directory (copies files to uploads/)."
    ),
)
@click.option(
    "--user-email",
    required=True,
    help="Email of the dataset owner (must exist)",
)
@click.option(
    "--csv-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory with CSVs",
)
@click.option("--title", required=True, help="Dataset title")
@click.option(
    "--description",
    default="Imported CSV dataset",
    help="Dataset description",
)
@click.option(
    "--tags",
    default="",
    help="Comma-separated tags for dataset and files",
)
@click.option(
    "--dataset-publication",
    type=click.Choice([t.name for t in DataCategory]),
    default=DataCategory.SALES.name,
    show_default=True,
    help="Publication type for the dataset metadata",
)
@click.option(
    "--file-publication",
    type=click.Choice([t.name for t in DataCategory]),
    default=DataCategory.USER_REVIEWS.name,
    show_default=True,
    help="Publication type for each CSV file metadata",
)
@click.option(
    "--version",
    default="",
    help="Optional csv_version to assign to each file",
)
def _collect_csv_files(csv_dir: str) -> list[str]:
    return [f for f in os.listdir(csv_dir) if f.lower().endswith(".csv")]


def _ensure_dest_folder(user_id: int, dataset_id: int) -> str:
    working_dir = os.getenv("WORKING_DIR", "")
    dest_folder = os.path.join(working_dir, "uploads", f"user_{user_id}", f"dataset_{dataset_id}")
    os.makedirs(dest_folder, exist_ok=True)
    return dest_folder


def _create_dataset(
    user: User,
    title: str,
    description: str,
    tags: str,
    dataset_publication: str,
    csv_count: int,
) -> DataSet:
    ds_metrics = DSMetrics(number_of_models=str(csv_count), number_of_features="")
    db.session.add(ds_metrics)
    db.session.flush()

    ds_md = DSMetaData(
        deposition_id=None,
        title=title,
        description=description,
        data_category=DataCategory[dataset_publication],
        publication_doi=None,
        dataset_doi=None,
        tags=tags,
        ds_metrics_id=ds_metrics.id,
    )
    db.session.add(ds_md)
    db.session.flush()

    dataset = DataSet(
        user_id=user.id,
        ds_meta_data_id=ds_md.id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(dataset)
    db.session.flush()
    return dataset


def _attach_csv_files(
    dataset: DataSet,
    user: User,
    csv_dir: str,
    csv_files: list[str],
    tags: str,
    file_publication: str,
    version: str,
) -> int:
    dest_folder = _ensure_dest_folder(user.id, dataset.id)
    created = 0
    for name in sorted(csv_files):
        src_path = os.path.join(csv_dir, name)

        fm_md = FMMetaData(
            csv_filename=name,
            title=os.path.splitext(name)[0],
            description=f"CSV file {name}",
            data_category=DataCategory[file_publication],
            publication_doi=None,
            tags=tags,
            csv_version=(version or None),
        )
        db.session.add(fm_md)
        db.session.flush()

        feature_model = FeatureModel(data_set_id=dataset.id, fm_meta_data_id=fm_md.id)
        db.session.add(feature_model)
        db.session.flush()

        dst_path = os.path.join(dest_folder, name)
        shutil.copy2(src_path, dst_path)

        hubfile = Hubfile(
            name=name,
            checksum=sha256_of_file(dst_path),
            size=os.path.getsize(dst_path),
            feature_model_id=feature_model.id,
        )
        db.session.add(hubfile)
        created += 1

    return created


def _import_for_user(
    user: User,
    csv_dir: str,
    title: str,
    description: str,
    tags: str,
    dataset_publication: str,
    file_publication: str,
    version: str,
) -> tuple[DataSet, int]:
    csv_files = _collect_csv_files(csv_dir)
    if not csv_files:
        raise click.ClickException("No .csv files found in the provided directory")

    dataset = _create_dataset(
        user,
        title,
        description,
        tags,
        dataset_publication,
        len(csv_files),
    )

    created = _attach_csv_files(
        dataset,
        user,
        csv_dir,
        csv_files,
        tags,
        file_publication,
        version,
    )

    db.session.commit()
    return dataset, created


@with_appcontext
def datasets_import(
    user_email,
    csv_dir,
    title,
    description,
    tags,
    dataset_publication,
    file_publication,
    version,
):
    """Import CSVs from a directory into a single dataset for the user."""
    app = create_app()
    with app.app_context():
        load_dotenv()
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise click.ClickException(f"User with email '{user_email}' not found")

        _, count = _import_for_user(
            user,
            csv_dir,
            title,
            description,
            tags,
            dataset_publication,
            file_publication,
            version,
        )

        msg = f"Imported dataset '{title}' for {user.email} with {count} CSVs."
        click.echo(click.style(msg, fg="green"))
