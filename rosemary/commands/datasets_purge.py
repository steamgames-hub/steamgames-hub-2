import click
from flask.cli import with_appcontext

from app import create_app, db
from app.modules.dataset.models import (
    DataSet,
    DSDownloadRecord,
    DSViewRecord,
    DOIMapping,
)
from app.modules.hubfile.models import Hubfile, HubfileDownloadRecord, HubfileViewRecord
from app.modules.featuremodel.models import FeatureModel, FMMetaData, FMMetrics
from app.modules.dataset.models import DSMetaData, DSMetrics, Author
from rosemary.commands.clear_uploads import clear_uploads


@click.command(
    "datasets:purge",
    help=(
        "Delete ALL datasets and related records "
        "(views/downloads/files/metadata) and clear the uploads directory."
    ),
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Confirm the operation without prompting.",
)
@with_appcontext
def datasets_purge(yes):
    app = create_app()
    with app.app_context():
        if not yes and not click.confirm(
            click.style(
                "This will delete ALL datasets and files. Continue?",
                fg="red",
            ),
            abort=True,
        ):
            return

        # Remove view/download records first (FKs to files/datasets)
        file_dl = db.session.query(HubfileDownloadRecord).delete(
            synchronize_session=False
        )
        file_view = db.session.query(HubfileViewRecord).delete(
            synchronize_session=False
        )
        ds_dl = db.session.query(DSDownloadRecord).delete(
            synchronize_session=False
        )
        ds_view = db.session.query(DSViewRecord).delete(
            synchronize_session=False
        )
        doi = db.session.query(DOIMapping).delete(synchronize_session=False)

        # Now remove dependent tables in FK-safe order using bulk deletes
        files_deleted = db.session.query(Hubfile).delete(synchronize_session=False)
        fms_deleted = db.session.query(FeatureModel).delete(synchronize_session=False)
        authors_deleted = db.session.query(Author).delete(synchronize_session=False)
        fmmd_deleted = db.session.query(FMMetaData).delete(synchronize_session=False)
        fmm_deleted = db.session.query(FMMetrics).delete(synchronize_session=False)
        datasets_deleted = db.session.query(DataSet).delete(synchronize_session=False)
        dsmd_deleted = db.session.query(DSMetaData).delete(synchronize_session=False)
        dsm_deleted = db.session.query(DSMetrics).delete(synchronize_session=False)

        db.session.commit()

        click.echo(
            click.style(
                "Purge summary: "
                f"file_dl={file_dl}, file_view={file_view}, ds_dl={ds_dl}, ds_view={ds_view}, doi={doi}. "
                f"files={files_deleted}, feature_models={fms_deleted}, authors={authors_deleted}, "
                f"fm_meta_data={fmmd_deleted}, fm_metrics={fmm_deleted}, datasets={datasets_deleted}, "
                f"ds_meta_data={dsmd_deleted}, ds_metrics={dsm_deleted}.",
                fg="green",
            )
        )

        # Clear uploads folder contents
        ctx = click.get_current_context()
        ctx.invoke(clear_uploads)

        click.echo(click.style("Datasets and uploads cleared.", fg="green"))
