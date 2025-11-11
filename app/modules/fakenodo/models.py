from app import db


class Fakenodo(db.Model):
    dataset_id = db.Column(db.Integer, primary_key=True)
    associated_doi = db.Column(db.String(50))
