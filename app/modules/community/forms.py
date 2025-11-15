from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class CommunityForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Create community")


class ProposalForm(FlaskForm):
    submit = SubmitField("Propose")
