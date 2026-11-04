import pytest
from pydantic import ValidationError

from app.schemas.collaboration import ParticipantsChange
from app.schemas.feedback import FeedbackConvertRequest
from app.schemas.requirement import RequirementCreate


@pytest.mark.parametrize(
    "model,base",
    [
        (ParticipantsChange, {"revision": 1}),
        (
            RequirementCreate,
            {"title": "多人验收", "requirement_type": "FEATURE", "description": "范围"},
        ),
        (
            FeedbackConvertRequest,
            {
                "type": "CREATE_NEW",
                "revision": 1,
                "requirement_title": "多人验收",
                "requirement_type": "FEATURE",
                "description": "验收范围",
            },
        ),
    ],
)
def test_multiple_acceptance_preserves_other_assignment_constraints(model, base):
    people = [
        {"user_id": 1, "role": "CONFIRM"},
        {"user_id": 2, "role": "ACCEPT"},
        {"user_id": 3, "role": "ACCEPT"},
    ]
    result = model.model_validate({**base, "participants": people})
    assert len(result.participants) == 3
    with pytest.raises(ValidationError, match="人员与环节不能重复"):
        model.model_validate({**base, "participants": [*people, people[-1]]})
    assert (
        len(
            model.model_validate(
                {**base, "participants": [*people, {"user_id": 4, "role": "CONFIRM"}]}
            ).participants
        )
        == 4
    )
    assert len(model.model_validate({**base, "participants": people[:2]}).participants) == 2
