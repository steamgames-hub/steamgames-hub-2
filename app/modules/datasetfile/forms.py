from flask_wtf import FlaskForm
from wtforms import SubmitField


class DatasetFileForm(FlaskForm):
    submit = SubmitField("Save dataset file")
