import re

import unidecode
from sqlalchemy import and_, func, or_

from app import db
from app.modules.dataset.models import Author, DataCategory, DataSet, DSDownloadRecord, DSMetaData, DSViewRecord
from app.modules.datasetfile.models import DatasetFile, DatasetFileMetaData
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus
from core.repositories.BaseRepository import BaseRepository


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def filter(
        self,
        query="",
        data_category="any",
        sorting="newest",
        author=None,
        tags=None,
        filenames=None,
        community=None,
        date_from=None,
        date_to=None,
        min_downloads=None,
        min_views=None,
        limit=50,
        offset=0,
        **kwargs,
    ):

        q = (
            self.model.query.join(DataSet.ds_meta_data)
            .outerjoin(DSMetaData.authors)
            .outerjoin(DataSet.dataset_files)
            .outerjoin(DatasetFile.file_metadata)
        )

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
                filters.append(DatasetFileMetaData.csv_filename.ilike(like))
                filters.append(DatasetFileMetaData.title.ilike(like))
                filters.append(DatasetFileMetaData.description.ilike(like))
                filters.append(DatasetFileMetaData.publication_doi.ilike(like))
                filters.append(DatasetFileMetaData.tags.ilike(like))
                filters.append(DSMetaData.tags.ilike(like))
            if filters:
                q = q.filter(or_(*filters))

        if data_category != "any":
            matching_type = None
            for member in DataCategory:
                if member.value.lower() == data_category.lower():
                    matching_type = member
                    break

            if matching_type is not None:
                q = q.filter(DSMetaData.data_category == matching_type.value)

        if author:
            a = f"%{author}%"
            q = q.filter(or_(Author.name.ilike(a), Author.affiliation.ilike(a), Author.orcid.ilike(a)))

        if tags:
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            tag_conds = [DSMetaData.tags.ilike(f"%{t}%") for t in tags] + [
                DatasetFileMetaData.tags.ilike(f"%{t}%") for t in tags
            ]
            if tag_conds:
                q = q.filter(or_(*tag_conds))

        if community:
            if isinstance(community, str):
                communities = [value.strip() for value in community.split(",") if value.strip()]
            elif isinstance(community, (list, tuple, set)):
                communities = [str(value).strip() for value in community if str(value).strip()]
            else:
                communities = [str(community).strip()]

            if communities:
                name_filters = [Community.name.ilike(f"%{value}%") for value in communities]
                q = (
                    q.join(
                        CommunityDatasetProposal,
                        and_(
                            CommunityDatasetProposal.dataset_id == DataSet.id,
                            CommunityDatasetProposal.status == ProposalStatus.ACCEPTED,
                        ),
                    )
                    .join(Community, Community.id == CommunityDatasetProposal.community_id)
                    .filter(or_(*name_filters))
                )

        if filenames:
            if isinstance(filenames, str):
                names = [name.strip() for name in filenames.split(",") if name.strip()]

            filters = [DatasetFileMetaData.csv_filename.ilike(f"%{n}%") for n in names]

            dataset_file_sub = (
                db.session.query(DatasetFile.data_set_id)
                .join(DatasetFileMetaData)
                .filter(or_(*filters))
                .group_by(DatasetFile.data_set_id)
                .subquery()
            )

            q = q.join(dataset_file_sub, dataset_file_sub.c.data_set_id == DataSet.id)

        if date_from:
            q = q.filter(DataSet.created_at >= date_from)
        if date_to:
            q = q.filter(DataSet.created_at <= date_to)

        # downloads/views aggregates
        if min_downloads is not None:
            dl_sub = (
                db.session.query(
                    DSDownloadRecord.dataset_id.label("dsid"), func.count(DSDownloadRecord.id).label("dlc")
                )
                .group_by(DSDownloadRecord.dataset_id)
                .subquery()
            )
            q = q.outerjoin(dl_sub, dl_sub.c.dsid == DataSet.id).filter(dl_sub.c.dlc >= int(min_downloads))

        if min_views is not None:
            v_sub = (
                db.session.query(DSViewRecord.dataset_id.label("dsid"), func.count(DSViewRecord.id).label("vc"))
                .group_by(DSViewRecord.dataset_id)
                .subquery()
            )
            q = q.outerjoin(v_sub, v_sub.c.dsid == DataSet.id).filter(v_sub.c.vc >= int(min_views))

        # sorting/pagination
        if sorting == "newest":
            q = q.order_by(DataSet.created_at.desc())
        elif sorting == "oldest":
            q = q.order_by(DataSet.created_at.asc())

        return q.distinct().limit(limit).offset(offset).all()
