import io
import os
import threading
from unittest.mock import Mock

import app as vf


def setup_function():
    with vf.VIDEO_JOBS_LOCK:
        vf.VIDEO_JOBS.clear()


def _voice(monkeypatch):
    monkeypatch.setattr(vf, "load_voices", lambda: [{"id": "local1", "name": "Test", "voice_id": "vv_" + "testvoice", "created_at": 1}])
    monkeypatch.setattr(vf, "capabilities", lambda: {"lipsync": True, "hq": True})


def test_create_job_is_async_and_private(monkeypatch, tmp_path):
    _voice(monkeypatch)
    submitted=[]
    monkeypatch.setattr(vf.VIDEO_EXECUTOR, "submit", lambda fn, *args: submitted.append((fn,args)))
    client=vf.app.test_client()
    response=client.post('/api/video/jobs', data={"voice_id":"local1","text":"private narration","speed":"1"})
    assert response.status_code==202
    body=response.get_json()
    assert len(body["id"])==32 and body["state"]=="queued"
    assert "private narration" not in response.get_data(as_text=True)
    assert ("vv_" + "testvoice") not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"]=="no-store"
    assert len(submitted)==1


def test_unknown_job_routes():
    client=vf.app.test_client()
    assert client.get('/api/video/jobs/nope').status_code==404
    assert client.post('/api/video/jobs/nope/cancel').status_code==404
    assert client.get('/api/video/jobs/nope/result').status_code==404


def test_result_is_gated_then_downloadable(tmp_path):
    result=tmp_path/'result.mp4';result.write_bytes(b'video')
    job={"id":"j1","state":"running","stage":"encode","message":"Encoding","progress":50,
         "created_at":1,"updated_at":1,"cancel":threading.Event(),"process":None,"work_dir":str(tmp_path),"result_path":str(result)}
    with vf.VIDEO_JOBS_LOCK:vf.VIDEO_JOBS["j1"]=job
    client=vf.app.test_client()
    assert client.get('/api/video/jobs/j1/result').status_code==409
    job["state"]="completed"
    response=client.get('/api/video/jobs/j1/result')
    assert response.status_code==200 and response.data==b'video'
    assert response.headers["Cache-Control"]=="no-store"


def test_cancel_is_idempotent_and_sets_event(monkeypatch, tmp_path):
    process=Mock();process.poll.return_value=None
    killed=[];monkeypatch.setattr(vf,"_cancel_process_tree",lambda p:killed.append(p))
    job={"id":"j2","state":"running","stage":"lipsync","message":"Working","progress":40,
         "created_at":1,"updated_at":1,"cancel":threading.Event(),"process":process,"work_dir":str(tmp_path),"result_path":None}
    with vf.VIDEO_JOBS_LOCK:vf.VIDEO_JOBS["j2"]=job
    client=vf.app.test_client()
    first=client.post('/api/video/jobs/j2/cancel')
    assert first.status_code==202 and job["cancel"].is_set() and job["state"]=="cancelling"
    second=client.post('/api/video/jobs/j2/cancel')
    assert second.status_code==202
    assert killed==[process]


def test_capacity_rejects_second_job(monkeypatch, tmp_path):
    _voice(monkeypatch)
    with vf.VIDEO_JOBS_LOCK:
        vf.VIDEO_JOBS["active"]={"state":"running"}
    response=vf.app.test_client().post('/api/video/jobs',data={"voice_id":"local1","text":"hello"})
    assert response.status_code==409


def test_windows_tree_kill_uses_argument_list(monkeypatch):
    process=Mock();process.pid=123;process.poll.return_value=None
    calls=[]
    monkeypatch.setattr(vf.os,"name","nt")
    monkeypatch.setattr(vf.subprocess,"run",lambda cmd,**kw:calls.append((cmd,kw)))
    vf._cancel_process_tree(process)
    assert calls[0][0]==["taskkill","/PID","123","/T","/F"]
    assert calls[0][1]["shell"] is False



def test_expired_terminal_job_media_is_removed(monkeypatch, tmp_path):
    work=tmp_path/'private';work.mkdir();(work/'result.mp4').write_bytes(b'private')
    job={"id":"old","state":"completed","updated_at":1,"work_dir":str(work)}
    with vf.VIDEO_JOBS_LOCK:vf.VIDEO_JOBS["old"]=job
    monkeypatch.setattr(vf.time,"time",lambda: vf.VIDEO_RESULT_TTL+100)
    vf._cleanup_video_jobs()
    assert "old" not in vf.VIDEO_JOBS and not work.exists()


def test_local_command_error_does_not_expose_stderr(monkeypatch):
    secret="private narration and secret token"
    monkeypatch.setattr(vf.subprocess,"run",lambda *a,**k: vf.subprocess.CompletedProcess([],1,"",secret))
    try:
        vf.run(["tool","--secret",secret])
    except RuntimeError as exc:
        assert secret not in str(exc)
    else:
        raise AssertionError("expected RuntimeError")



def test_video_rejects_non_image_upload(monkeypatch):
    _voice(monkeypatch)
    response=vf.app.test_client().post('/api/video/jobs',data={
        "voice_id":"local1","text":"hello","image":(io.BytesIO(b"not an image"),"face.txt","text/plain")
    })
    assert response.status_code==400
    assert "JPEG, PNG, or WebP" in response.get_json()["error"]


def test_video_rejects_undecodable_image(monkeypatch):
    _voice(monkeypatch)
    monkeypatch.setattr(vf,"run",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("decoder detail")))
    response=vf.app.test_client().post('/api/video/jobs',data={
        "voice_id":"local1","text":"hello","image":(io.BytesIO(b"bad png"),"face.png","image/png")
    })
    assert response.status_code==400
    assert response.get_json()["error"]=="Face image could not be decoded."

def test_python_tool_uses_console_sibling_for_pythonw(monkeypatch, tmp_path):
    pythonw=tmp_path/"pythonw.exe";pythonw.write_bytes(b"")
    python=tmp_path/"python.exe";python.write_bytes(b"")
    monkeypatch.setattr(vf.os,"name","nt")
    monkeypatch.setattr(vf.sys,"executable",str(pythonw))
    monkeypatch.delattr(vf.sys,"frozen",raising=False)
    assert vf._python_tool_executable()==str(python)


def test_python_tool_keeps_current_executable_without_console_sibling(monkeypatch, tmp_path):
    pythonw=tmp_path/"PythonW.EXE";pythonw.write_bytes(b"")
    monkeypatch.setattr(vf.os,"name","nt")
    monkeypatch.setattr(vf.sys,"executable",str(pythonw))
    monkeypatch.delattr(vf.sys,"frozen",raising=False)
    assert vf._python_tool_executable()==str(pythonw)


def test_python_tool_is_unchanged_off_windows(monkeypatch):
    monkeypatch.setattr(vf.os,"name","posix")
    monkeypatch.setattr(vf.sys,"executable","/usr/bin/python3")
    assert vf._python_tool_executable()=="/usr/bin/python3"



def test_python_tool_does_not_rewrite_frozen_executable(monkeypatch, tmp_path):
    pythonw=tmp_path/"pythonw.exe";pythonw.write_bytes(b"")
    (tmp_path/"python.exe").write_bytes(b"")
    monkeypatch.setattr(vf.os,"name","nt")
    monkeypatch.setattr(vf.sys,"executable",str(pythonw))
    monkeypatch.setattr(vf.sys,"frozen",True,raising=False)
    assert vf._python_tool_executable()==str(pythonw)


def test_lipsync_launch_uses_resolved_python(monkeypatch, tmp_path):
    image=tmp_path/"upload.png";image.write_bytes(b"image")
    calls=[]
    monkeypatch.setattr(vf,"_python_tool_executable",lambda:"console-python.exe")
    monkeypatch.setattr(vf,"venice_speech",lambda *a:b"wave")
    monkeypatch.setattr(vf,"tool",lambda name:name)
    monkeypatch.setattr(vf,"run",lambda cmd,**kw:calls.append((cmd,kw)) or vf.subprocess.CompletedProcess(cmd,0,"",""))
    monkeypatch.setattr(vf.os.path,"isfile",lambda path: path.endswith("out.mp4") or os.path.isfile(path))
    monkeypatch.setattr(vf.os.path,"getsize",lambda path: 1)
    row={"voice_id":"voice"}
    vf._render_video(row,"hello","1",True,False,str(image),str(tmp_path))
    lipsync=[call for call in calls if "inference.py" in call[0][1]][0]
    assert lipsync[0][0]=="console-python.exe"
    assert lipsync[1]["cwd"]==vf.LS_REPO
