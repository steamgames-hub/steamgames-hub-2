from types import SimpleNamespace

from app.modules.dataset.models import DataSet
from app.modules.fakenodo.models import Fakenodo
from app.modules.fakenodo.services import FakenodoService


def test_fakenodo_create_deposition():
    """
    Test create new deposition via service
    """

    fk = FakenodoService()

    def create(**kwargs):
        fakenodo = Fakenodo()
        fakenodo.conceptrecid = 1234
        fakenodo.id = 1234

        return fakenodo

    def update(id, **kwargs):
        return None

    fk.repository = SimpleNamespace(create=create, update=update)

    empty_dataset = DataSet()

    response = fk.create_new_deposition(empty_dataset)

    assert "conceptrecid" in response, "The expected response should have a conceptrecid"
    assert response["conceptrecid"] == 1234, "Conceptrecid should be 1234 (default placeholder)"

    assert "id" in response, "The expected response should have an id"
