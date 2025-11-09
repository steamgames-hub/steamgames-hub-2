import re

import unidecode
from sqlalchemy import any_, or_, func
from app import db

from app.modules.dataset.models import DataSet, DSMetaData, Author, DSDownloadRecord, DSViewRecord
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from core.repositories.BaseRepository import BaseRepository


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def filter(self, query="", sorting="newest", publication_type="any",
               author=None, tags=None, uvl=None, community=None,
               date_from=None, date_to=None, min_downloads=None, min_views=None,
               limit=50, offset=0, **kwargs):

        q = self.model.query.join(DataSet.ds_meta_data).outerjoin(DSMetaData.authors).outerjoin(DataSet.feature_models).outerjoin(FeatureModel.fm_meta_data)
        
        if query:
            q = q.filter(or_(DSMetaData.title.ilike(f"%{query}%"), DSMetaData.description.ilike(f"%{query}%")))

        if author:
            a = f"%{author}%"
            q = q.filter(or_(Author.name.ilike(a), Author.affiliation.ilike(a), Author.orcid.ilike(a)))

        if tags:
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            tag_conds = [DSMetaData.tags.ilike(f"%{t}%") for t in tags] + [FMMetaData.tags.ilike(f"%{t}%") for t in tags]
            if tag_conds:
                q = q.filter(or_(*tag_conds))

        if date_from:
            q = q.filter(DataSet.created_at >= date_from)
        if date_to:
            q = q.filter(DataSet.created_at <= date_to)

        # downloads/views aggregates
        if min_downloads is not None:
            dl_sub = db.session.query(DSDownloadRecord.dataset_id.label('dsid'), func.count(DSDownloadRecord.id).label('dlc')).group_by(DSDownloadRecord.dataset_id).subquery()
            q = q.outerjoin(dl_sub, dl_sub.c.dsid == DataSet.id).filter(dl_sub.c.dlc >= int(min_downloads))

        if min_views is not None:
            v_sub = db.session.query(DSViewRecord.dataset_id.label('dsid'), func.count(DSViewRecord.id).label('vc')).group_by(DSViewRecord.dataset_id).subquery()
            q = q.outerjoin(v_sub, v_sub.c.dsid == DataSet.id).filter(v_sub.c.vc >= int(min_views))

        # sorting/pagination
        if sorting == "newest":
            q = q.order_by(DataSet.created_at.desc())
        elif sorting == "oldest":
            q = q.order_by(DataSet.created_at.asc())

        return q.distinct().limit(limit).offset(offset).all()
