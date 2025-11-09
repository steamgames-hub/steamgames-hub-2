import re

import unidecode
from sqlalchemy import or_, and_, func
from app import db

from app.modules.dataset.models import DataSet, DSMetaData, Author, DSDownloadRecord, DSViewRecord
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from core.repositories.BaseRepository import BaseRepository


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def filter(self, query="", sorting="newest",
               author=None, tags=None, filenames=None, community=None,
               date_from=None, date_to=None, min_downloads=None, min_views=None,
               limit=50, offset=0, **kwargs):

        q = self.model.query.join(DataSet.ds_meta_data).outerjoin(DSMetaData.authors).outerjoin(DataSet.feature_models).outerjoin(FeatureModel.fm_meta_data)

        if query:
            normalized_query = unidecode.unidecode(query).lower()
            cleaned_query = re.sub(r'[,.":\'()\[\]^;!¡¿?]', "", normalized_query)
            filters = []
            for word in cleaned_query.split():
                like = f"%{word}%"
                filters.append(DSMetaData.title.ilike(like))
                filters.append(DSMetaData.description.ilike(like))
                filters.append(Author.name.ilike(like))
                filters.append(Author.affiliation.ilike(like))
                filters.append(Author.orcid.ilike(like))
                filters.append(FMMetaData.csv_filename.ilike(like))
                filters.append(FMMetaData.title.ilike(like))
                filters.append(FMMetaData.description.ilike(like))
                filters.append(FMMetaData.publication_doi.ilike(like))
                filters.append(FMMetaData.tags.ilike(like))
                filters.append(DSMetaData.tags.ilike(like))
            if filters:
                q = q.filter(or_(*filters))
              
        if author:
            a = f"%{author}%"
            q = q.filter(or_(Author.name.ilike(a), Author.affiliation.ilike(a), Author.orcid.ilike(a)))

        if tags:
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            for t in tags:
                tag_cond = or_(DSMetaData.tags.ilike(f"%{t}%"), FMMetaData.tags.ilike(f"%{t}%"))
                q = q.filter(tag_cond)

        if filenames:
            if isinstance(filenames, str):
                names = [name.strip() for name in filenames.split(",") if name.strip()]

            clean_names = [name.strip() for name in names]

            filters = [FMMetaData.csv_filename.ilike(f"%{n}%") for n in clean_names]

            fm_sub = (
                db.session.query(FeatureModel.data_set_id)
                .join(FMMetaData)
                .filter(and_(*filters))
                .group_by(FeatureModel.data_set_id)
                .having(func.count(FMMetaData.id) >= len(clean_names))
                .subquery()
            )

            q = q.join(fm_sub, fm_sub.c.data_set_id == DataSet.id)

        if date_from:
            q = q.filter(DataSet.created_at >= date_from)
        if date_to:
            q = q.filter(DataSet.created_at <= date_to)

        # downloads/views aggregates
        if min_downloads is not None:
            dl_sub = db.session.query(DSDownloadRecord.dataset_id.label('dsid'), func.count(DSDownloadRecord.id)
                                      .label('dlc')).group_by(DSDownloadRecord.dataset_id).subquery()
            q = q.outerjoin(dl_sub, dl_sub.c.dsid == DataSet.id).filter(dl_sub.c.dlc >= int(min_downloads))

        if min_views is not None:
            v_sub = db.session.query(DSViewRecord.dataset_id.label('dsid'),
                                     func.count(DSViewRecord.id).label('vc')).group_by(DSViewRecord.dataset_id).subquery()
            q = q.outerjoin(v_sub, v_sub.c.dsid == DataSet.id).filter(v_sub.c.vc >= int(min_views))

        # sorting/pagination
        if sorting == "newest":
            q = q.order_by(DataSet.created_at.desc())
        elif sorting == "oldest":
            q = q.order_by(DataSet.created_at.asc())

        return q.distinct().limit(limit).offset(offset).all()
