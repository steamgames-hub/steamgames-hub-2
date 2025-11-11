from app.modules.profile.repositories import UserProfileRepository
from core.services.BaseService import BaseService


class UserProfileService(BaseService):
    def __init__(self):
        super().__init__(UserProfileRepository())

    def update_profile(self, user_profile_id, form):
        if form.validate():
            data = dict(form.data)
            # Forzar affiliation a string vacío si es None
            if data.get("affiliation") is None:
                data["affiliation"] = ""
            updated_instance = self.update(user_profile_id, **data)
            return updated_instance, None

        return None, form.errors

    def change_save_drafts(self, user_profile_id):
        current_user = self.get_by_id(user_profile_id)
        preference = current_user.save_drafts
        return self.update(user_profile_id, **{"save_drafts": not preference})
