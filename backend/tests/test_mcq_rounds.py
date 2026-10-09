import pytest
from app.db import DB
from app.round_questions import select_questions, grade_mcq


@pytest.mark.parametrize('kind', ['aptitude', 'technical'])
def test_fifteen_distinct_mcqs(client, kind):
    with DB() as db:
        questions = select_questions(db, kind, 'junior')
    assert len(questions) == 15
    assert len({q['question'] for q in questions}) == 15
    for q in questions:
        assert q['source'] == 'bank_mcq' and q['question_type'] == 'mcq'
        assert len(q['options']) >= 3
        ids = {o['id'] for o in q['options']}
        correct = set(q['expected_points'][0].split(','))
        assert correct <= ids
        assert grade_mcq(q, q['expected_points'][0])['technical'] == 100
        assert grade_mcq(q, 'invalid')['technical'] == 0
