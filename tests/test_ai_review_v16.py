import json

import httpx
import pytest
from PIL import Image

from challenger.ai_review import review_images, evaluate_review, validate_annotation

ANNOTATION = {'content_type': 'campaign', 'decision': 'accept', 'color_role': 'deliberate background',
              'reason': 'Substantial creative image', 'suggested_region': [0, 0, 1, 1],
              'date_evidence': None, 'creator_evidence': None}


def package(tmp_path):
    work = tmp_path / '2026-09-11'; work.mkdir()
    image = work / 'image.png'; Image.new('RGB', (100, 100), '#A5C84A').save(image)
    (work / 'collection-progress.json').write_text(json.dumps([{'source_id': 'one', 'regions': [
        {'region_id': 'one-r1', 'screenshot_path': '/another-machine/image.png', 'metadata': {'artifact_path': 'image.png'}}]}]))
    return work


def test_dry_run_never_calls_api_and_works_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    work = package(tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('Unexpected network call')))
    report = review_images(work, client=client)
    assert report['requests'] == 0 and report['mode'] == 'dry_run'
    assert report['rows'][0]['status'] == 'would_review'
    assert (work / 'human-labels-template.csv').exists()


def test_structured_api_review_is_cached_and_cannot_change_rankings(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    work = package(tmp_path)
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        assert request.url.host == 'api.openai.com'
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(ANNOTATION)}]}], 'usage': {'input_tokens': 100}})
    client = httpx.Client(transport=httpx.MockTransport(respond))
    first = review_images(work, execute=True, client=client)
    second = review_images(work, execute=True, client=client)
    assert len(calls) == 1 and calls[0]['store'] is False
    assert first['rows'][0]['status'] == 'reviewed'
    assert second['rows'][0]['status'] == 'cached'
    assert first['ranking_influenced'] is False
    assert not (work / 'result.json').exists()


def test_failed_api_is_review_needed_and_does_not_leak_response(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    work = package(tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text='sensitive fake server text')))
    report = review_images(work, execute=True, client=client)
    assert report['rows'][0]['status'] == 'review_needed'
    assert 'sensitive fake' not in (work / 'ai-review.json').read_text()


def test_request_limit_and_budget_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    report = review_images(package(tmp_path), execute=True, budget_seconds=0)
    assert report['requests'] == 0
    assert report['rows'][0]['status'] == 'budget_exhausted'


def test_invalid_box_and_extra_fields_are_rejected():
    with pytest.raises(ValueError):
        validate_annotation({**ANNOTATION, 'suggested_region': [0, 0, 1.5, 1]})
    with pytest.raises(ValueError):
        validate_annotation({**ANNOTATION, 'winner': '#A5C84A'})


def test_evaluation_uses_only_labelled_test_split(tmp_path):
    predictions = tmp_path / 'pred.json'
    predictions.write_text(json.dumps({'rows': [{'review_id': 'a', 'annotation': {'decision': 'accept'}}, {'review_id': 'b', 'annotation': {'decision': 'accept'}}]}))
    labels = tmp_path / 'labels.csv'
    labels.write_text('review_id,expected_decision,split\na,accept,test\nb,reject,train\n')
    report = evaluate_review(predictions, labels)
    assert report['evaluated'] == 1 and report['accept_precision'] == 1.0
