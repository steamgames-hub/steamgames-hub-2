import logging
from typing import Optional
from app.modules.game.models import GameData
from app import db
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType, DataSetType, Author

logger = logging.getLogger(__name__)


class GameService:
    def create_game_dataset(
        self,
        user,
        title: str,
        description: str,
        game_name: str,
        release_date: Optional[str] = None,
        developer: Optional[str] = None,
        publisher: Optional[str] = None,
        platforms: Optional[str] = None,
        required_age: Optional[str] = None,
        categories: Optional[str] = None,
        genres: Optional[str] = None,
        authors: Optional[list] = None,
    ) -> DataSet:
        """
        Creates a Game dataset with minimal required fields.
        - Stores common dataset info in DSMetaData/DataSet
        - Stores game-specific info in GameData (1-1 with DataSet)
        """

        try:
            # Common metadata
            ds_meta = DSMetaData(
                title=title,
                description=description,
                publication_type=PublicationType.NONE,
                publication_doi=None,
                dataset_doi=None,
                tags=None,
            )
            db.session.add(ds_meta)
            db.session.flush()

            dataset = DataSet(user_id=user.id, ds_meta_data_id=ds_meta.id, dataset_type=DataSetType.GAME)
            db.session.add(dataset)
            db.session.flush()

            # Authors: include current user as main author; optionally append provided authors
            main_author = Author(
                name=f"{user.profile.surname}, {user.profile.name}",
                affiliation=user.profile.affiliation,
                orcid=user.profile.orcid,
                ds_meta_data_id=ds_meta.id,
            )
            db.session.add(main_author)

            if authors:
                for a in authors:
                    if not a:
                        continue
                    name = a.get("name")
                    if not name:
                        continue
                    db.session.add(
                        Author(
                            name=name,
                            affiliation=a.get("affiliation"),
                            orcid=a.get("orcid"),
                            ds_meta_data_id=ds_meta.id,
                        )
                    )

            # Game specific
            game = GameData(
                data_set_id=dataset.id,
                game_name=game_name,
                release_date=release_date,
                developer=developer,
                publisher=publisher,
                platforms=platforms,
                required_age=required_age,
                categories=categories,
                genres=genres,
            )
            db.session.add(game)

            db.session.commit()
            return dataset
        except Exception as exc:
            logger.exception("Error creating game dataset: %s", exc)
            db.session.rollback()
            raise
