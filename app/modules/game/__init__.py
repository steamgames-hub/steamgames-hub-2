from core.blueprints.base_blueprint import BaseBlueprint

# Expose a blueprint so the ModuleManager can register this module without errors
game_bp = BaseBlueprint("game", __name__, template_folder="templates")
