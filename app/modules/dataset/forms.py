from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import URL, DataRequired, Optional, Regexp

from app.modules.dataset.models import DataCategory


class AuthorForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    affiliation = StringField("Affiliation")
    orcid = StringField("ORCID")
    gnd = StringField("GND")

    class Meta:
        csrf = False  # disable CSRF because is subform

    def get_author(self):
        return {
            "name": self.name.data,
            "affiliation": self.affiliation.data,
            "orcid": self.orcid.data,
        }


class DatasetFileForm(FlaskForm):
    csv_filename = StringField("CSV Filename", validators=[DataRequired()])
    title = StringField("Title", validators=[Optional()])
    desc = TextAreaField("Description", validators=[Optional()])
    data_category = SelectField(
        "Data category",
        choices=[(pt.value, pt.name.replace("_", " ").title()) for pt in DataCategory],
        validators=[Optional()],
    )
    publication_doi = StringField("Publication DOI", validators=[Optional(), URL()])
    tags = StringField("Tags (separated by commas)")
    version = StringField(
        "CSV Version",
        validators=[Optional(), Regexp(r"^\d+\.\d+\.\d+$", message="Version must follow x.y.z format (e.g., 1.2.3)")],
    )
    authors = FieldList(FormField(AuthorForm))

    class Meta:
        csrf = False  # disable CSRF because is subform

    def get_authors(self):
        return [author.get_author() for author in self.authors]

    def get_file_metadata(self):
        return {
            "csv_filename": self.csv_filename.data,
            "title": self.title.data,
            "description": self.desc.data,
            "data_category": self.data_category.data,
            "publication_doi": self.publication_doi.data,
            "tags": self.tags.data,
            "csv_version": self.version.data,
        }


class DataSetForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    desc = TextAreaField("Description", validators=[DataRequired()])
    data_category = SelectField(
        "Data category",
        choices=[(pt.value, pt.name.replace("_", " ").title()) for pt in DataCategory],
        validators=[DataRequired()],
    )
    publication_doi = StringField("Publication DOI", validators=[Optional(), URL()])
    dataset_doi = StringField("Dataset DOI", validators=[Optional(), URL()])
    tags = StringField("Tags (separated by commas)")
    authors = FieldList(FormField(AuthorForm))
    dataset_files = FieldList(FormField(DatasetFileForm), min_entries=1)

    submit = SubmitField("Submit")

    def get_dsmetadata(self):

        data_category_converted = self.convert_data_category(self.data_category.data)

        return {
            "title": self.title.data,
            "description": self.desc.data,
            "data_category": data_category_converted,
            "publication_doi": self.publication_doi.data,
            "dataset_doi": self.dataset_doi.data,
            "tags": self.tags.data,
        }

    def convert_data_category(self, value):
        for pt in DataCategory:
            if pt.value == value:
                return pt.name
        return "NONE"

    def get_authors(self):
        return [author.get_author() for author in self.authors]

    def get_dataset_files(self):
        return [df.get_file_metadata() for df in self.dataset_files]
