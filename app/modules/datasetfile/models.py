from sqlalchemy import Enum as SQLAlchemyEnum

from app import db
from app.modules.dataset.models import Author, DataCategory


class DatasetFile(db.Model):
    __tablename__ = "feature_model"

    id = db.Column(db.Integer, primary_key=True)
    data_set_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False)
    metadata_id = db.Column("fm_meta_data_id", db.Integer, db.ForeignKey("fm_meta_data.id"))
    files = db.relationship("Hubfile", backref="dataset_file", lazy=True, cascade="all, delete")
    file_metadata = db.relationship(
        "DatasetFileMetaData", uselist=False, backref="dataset_file", cascade="all, delete"
    )

    def __repr__(self):
        return f"DatasetFile<{self.id}>"


class DatasetFileMetaData(db.Model):
    __tablename__ = "fm_meta_data"

    id = db.Column(db.Integer, primary_key=True)
    csv_filename = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    data_category = db.Column(SQLAlchemyEnum(DataCategory), nullable=False)
    publication_doi = db.Column(db.String(120))
    tags = db.Column(db.String(120))
    csv_version = db.Column(db.String(120))
    metrics_id = db.Column("fm_metrics_id", db.Integer, db.ForeignKey("fm_metrics.id"))
    metrics = db.relationship("DatasetFileMetrics", uselist=False, backref="dataset_file_metadata")
    authors = db.relationship(
        "Author",
        backref="dataset_file_metadata",
        lazy=True,
        cascade="all, delete",
        foreign_keys=[Author.fm_meta_data_id],
    )

    def __repr__(self):
        return f"DatasetFileMetaData<{self.title}>"


class DatasetFileMetrics(db.Model):
    __tablename__ = "fm_metrics"

    id = db.Column(db.Integer, primary_key=True)
    solver = db.Column(db.Text)
    not_solver = db.Column(db.Text)

    def __repr__(self):
        return f"DatasetFileMetrics<solver={self.solver}, not_solver={self.not_solver}>"
