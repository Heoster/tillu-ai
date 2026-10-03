from app import database as db
from app.main import infer_natural_action

def test_media_favorite_and_yesterday_requests_use_real_memory(tmp_path):
    db.DB_PATH=tmp_path/'media.db';db.init_db();n=db.new_now();uid='owner'
    db.save_media_track({'id':'t1','user_id':uid,'provider':'youtube_music','title':'Favorite Track','artist':'Artist','url':'https://music.youtube.com/watch?v=abc','is_favorite':True,'created_at':n,'updated_at':n})
    proposal=infer_natural_action('play my favorite song',uid);assert proposal['kind']=='media_play' and proposal['payload']['track_id']=='t1'

def test_new_song_uses_youtube_music_search_and_approval(tmp_path):
    db.DB_PATH=tmp_path/'media2.db';db.init_db();proposal=infer_natural_action('play Blinding Lights', 'owner')
    assert proposal['kind']=='media_play'
    assert proposal['payload']['url'].startswith('https://music.youtube.com/search?q=')
    assert db.get_action_proposal(proposal['id'],'owner')['status']=='pending'
