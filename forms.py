from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Length

class CreatePollForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Length(max=2000)])
    category = SelectField("Category", choices=[
        ("Politics", "Politics"),
        ("Sports", "Sports"),
        ("Celebrity", "Celebrity"),
        ("Tech", "Tech"),
        ("Markets", "Markets"),
        ("Science", "Science"),
        ("Entertainment", "Entertainment"),
        ("Other", "Other"),
    ], validators=[DataRequired()])
    image = FileField("Image", validators=[FileAllowed(["jpg", "png", "jpeg", "gif"], "Images only!")])
    submit = SubmitField("Create Poll")
