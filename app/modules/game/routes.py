from app.modules.game import game_bp

# Optional: add routes in the future. For now, exposing the blueprint allows ModuleManager to register the module.
# Touch the symbol so linters don't flag it as unused.
assert game_bp is not None
