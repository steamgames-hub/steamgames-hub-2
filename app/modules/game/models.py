from app import db


class GameData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_set_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False, unique=True)

    # Core game fields
    game_name = db.Column(db.String(200), nullable=False)
    release_date = db.Column(db.String(50))
    developer = db.Column(db.String(200))
    publisher = db.Column(db.String(200))
    platforms = db.Column(db.String(200))  # comma-separated list
    required_age = db.Column(db.String(10))
    categories = db.Column(db.Text)  # comma-separated list or JSON string
    genres = db.Column(db.Text)  # comma-separated list or JSON string

    dataset = db.relationship("DataSet", backref=db.backref("game", uselist=False, cascade="all, delete"))

    def to_dict(self):
        return {
            "game_name": self.game_name,
            "release_date": self.release_date,
            "developer": self.developer,
            "publisher": self.publisher,
            "platforms": self.platforms,
            "required_age": self.required_age,
            "categories": (self.categories or "").split(",") if self.categories else [],
            "genres": (self.genres or "").split(",") if self.genres else [],
        }
