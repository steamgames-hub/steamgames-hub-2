import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    for module testing (por example, new users)
    """
    with test_client.application.app_context():
        user_test = User(email="user@example.com", password="test1234")
        db.session.add(user_test)
        db.session.commit()

        profile = UserProfile(user_id=user_test.id, name="Name", surname="Surname")
        db.session.add(profile)
        db.session.commit()

        user_id = user_test.id
        
    yield test_client, user_id


def test_edit_profile_page_get(test_client):
    """
    Tests access to the profile editing page via a GET request.
    """
    client, user_test_id = test_client

    login_response = login(client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = client.get(f"/profile/edit/{user_test_id}")
    assert response.status_code == 200, "The profile editing page could not be accessed."
    assert b"Edit profile" in response.data, "The expected content is not present on the page"

    logout(client)

def test_change_preference_save_drafts(test_client):
    """
    Tests to modify the profile attribute "save_drafts" via a PUT request.
    """
    client, _ = test_client

    login_response = login(client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = client.put("/profile/save_drafts")
    assert response.status_code == 200, "The preference was changed succesfully"

    logout(client)