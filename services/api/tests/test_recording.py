import subprocess
import imageio_ffmpeg
from conftest import auth

def test_browser_recording_normalized_to_mp3(setup,tmp_path):
    c,db,t=setup;source=tmp_path/'synthetic.webm'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=0.2','-c:a','libopus',str(source)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    result=c.post('/v1/staff/files',headers=auth(t,'test-teacher'),files={'file':('synthetic.webm',source.read_bytes(),'audio/webm')})
    assert result.status_code==200
    data=result.json();assert data['kind']=='audio' and data['mime']=='audio/mpeg' and data['name'].endswith('.mp3')
    assert c.post('/v1/staff/files/'+data['id']+'/tickets',headers=auth(t,'test-teacher'),json={'purpose':'preview'}).status_code==200
