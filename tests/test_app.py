import app as m
import pytest
@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(m,'DATA_DIR',str(tmp_path));monkeypatch.setattr(m,'VOICES_PATH',str(tmp_path/'voices.json'));m.app.config['TESTING']=True;return m.app.test_client()
def test_home(client):assert client.get('/').status_code==200
def test_no_key(client,monkeypatch):monkeypatch.setattr(m,'venice_key',lambda:None);assert client.get('/api/settings/status').get_json()=={'has_key':False}
def test_voice_crud(client):
 r=client.post('/api/voices',json={'name':'Demo','voice_id':'vv_test'});assert r.status_code==200
 v=r.get_json()['voices'][0];assert client.patch('/api/voices/'+v['id'],json={'name':'New'}).status_code==200
 assert client.delete('/api/voices/'+v['id']).status_code==200


def test_youtube_url_validation():
 assert m.valid_youtube_url('https://www.youtube.com/watch?v=test')
 assert m.valid_youtube_url('https://youtu.be/test')
 assert not m.valid_youtube_url('file:///etc/passwd')
 assert not m.valid_youtube_url('https://evil.example/video')

def test_lipsync_missing_returns_503(client, monkeypatch):
 m.save_voices([{'id':'local','name':'Demo','voice_id':'vv_test','created_at':1}])
 monkeypatch.setattr(m,'capabilities',lambda:{'lipsync':False,'hq':False})
 result=client.post('/api/video',data={'voice_id':'local','text':'Hello','lipsync':'1'})
 assert result.status_code==503

def test_corrupt_voice_file_is_preserved(client):
 from pathlib import Path
 Path(m.VOICES_PATH).write_text('not-json',encoding='utf-8')
 result=client.get('/api/voices')
 assert result.status_code==500
 assert Path(m.VOICES_PATH).read_text(encoding='utf-8')=='not-json'


def test_cross_origin_mutation_rejected(client):
 result=client.post('/api/settings/key',json={'api_key':'x'*30},headers={'Origin':'https://evil.example'})
 assert result.status_code==403
