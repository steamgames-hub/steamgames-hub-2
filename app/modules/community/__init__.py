from flask_restful import Api

from core.blueprints.base_blueprint import BaseBlueprint

community_bp = BaseBlueprint("community", __name__, template_folder="templates")


api = Api(community_bp)
