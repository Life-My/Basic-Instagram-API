import requests
from urllib.parse import urlparse
import os
import sys
import json
import re
import pickle


class _Session:
    def session(username,password):
        sfilename="session.pkl"

        if not os.path.exists(sfilename): 
            session = requests.Session() 
            
            # session.proxies.update({"https":"https://172.28.80.1:1212"})
            # session.verify="burp.pem"
            url="https://www.instagram.com/"
            r=session.get(url)
            if not session.cookies.get_dict().get("csrftoken"):
                result=re.search(r"\"csrf_token\".\"(\w*)\"",r.text)
                if result:
                    session.cookies.set("csrftoken",result.group(1))

            headers ={
                "X-Csrftoken": session.cookies.get_dict().get("csrftoken")
            }

            data = {
                "enc_password": "#PWD_INSTAGRAM:0:0:%s" % password,
                "username": username,
                "queryParams": "{}",
                "optIntoOneTap": "false",
                "stopDeletionNonce": '',
                "trustedDeviceRecords": "{}"
            }
            session.headers.update(headers)
            r=session.post(url+"accounts/login/ajax/",data=data) # login request

            if r.status_code != 200 or r.json().get("errors"):
                sys.exit("[ERROR] Login failed")
                
            
            r=session.get(url)
            regex=r"\"X-IG-App-ID\".\"(\w*)\"" # get X-Ig-App-Id
            result=re.search(regex,r.text)
            if not result:
                sys.exit("[ERROR] Could not find X-Ig-App-Id \n\tStatus code: %s" % r.status_code)


            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.",
                "X-Csrftoken": session.cookies.get_dict().get("csrftoken"),
                "X-Ig-App-Id":result.groups(1)[0]
            }
            session.headers.update(headers)

            with open(sfilename, 'wb') as f: 
                pickle.dump(session, f) 
        else:
            with open(sfilename, 'rb') as f: 
                session = pickle.load(f) 
            
        return session

class _Download():
    def __init__(self,session):
        self.session = session
    def download(self, url:str,filename:str,path:str)->None:
        r=self.session.get(url)
        if r.status_code != 200:
            sys.stderr.write("[ERROR] Download failed %s" % url)
        ext = os.path.splitext(urlparse(url).path)[1]
        if ext in [".jpg", ".jpeg",".png",".webp"]:
            type="img"
        elif ext in [".gif", ".mp4", ".webm",".mpeg"]:
            type = "video" 
        else:
            sys.stderr.write("[ERROR] Unknown file extension: %s" % ext)
            return False
        path +=type+"/"

        if not os.path.exists(path):
            os.makedirs(path)
        filename=path+filename+ext
        with open(filename, 'wb') as imageFile:
            imageFile.write(r.content)

    def image_versions2(self,obj,userid,type:str):
        for o in obj:
            filename=f'{str(o.get("pk"))}-{o.get("width")}x{o.get("height")}'
            path=str(userid)+"/"+type+"/"
            self.download(o.get("url"),filename,path)
        return True
    
    def thumbnail_resources(self,obj,userid):
        for o in obj:
            filename=f'{str(o.get("id"))}-{o.get("config_width")}x{o.get("config_height")}'
            path=str(userid)+"/posts/"
            self.download(o.get("src"),filename,path)
        return True

class _Print:
    def printUserInfo(basicInfo):
        sys.stderr.write(f'+{"-"*100}+\n')
        for k, v in basicInfo.items():
            sys.stderr.write(f"{k}: {v}\n")
        sys.stderr.write(f'+{"-"*100}+\n')


class Instagram():
    def __init__(self,username:str,password:str)->None:
        self.userId=None
        self.username=None
        self.apiUrl="https://i.instagram.com/api/v1/"
        self.graphUrl="https://www.instagram.com/graphql/query/"
        self.session=_Session.session(username,password)
        self.d=_Download(self.session)

    def getReelsMedia(self)->list:
        max_id=""
        reels=list()
        while True:
            data=self.getReel(max_id).json()
            for item in data.get("items"):
                img=item.get("media").get("image_versions2")
                video=item.get("media").get("video_versions")
                pk={"pk":item.get("media").get("pk")}
                if img.get("candidates"):
                    for candidate in img.get("candidates"):
                        candidate.update(pk)
                        reels.append(candidate)
                if video:
                    for v in video:
                        v.update(pk)
                        reels.append(v)
                if img.get("additional_candidates"):
                    ac = img.get("additional_candidates")
                    iff = ac.get("igtv_first_frame")
                    iff.update(pk)
                    ff = ac.get("first_frame")
                    ff.update(pk)
                    reels.append(iff)
                    reels.append(ff)
            if not data.get("paging_info").get("more_available"):
                break
            
            max_id=data["paging_info"]["max_id"]

        return reels
    
    def getReel(self, max_id:str=None)->requests.Response:
        PATH ="clips/user/"
        params={
            "target_user_id": self.getUserId(), 
            "page_size": "12",
            "include_feed_video": "true"
        }
        if max_id:
            params.update({"max_id":max_id})
        r=self.session.post(self.apiUrl+PATH,data=params)

        if r.status_code != 200 and r.headers.get("Content-Type") != "application/json":
            sys.exit("[ERROR] Failed to request %s" % r.status_code)

        return r

    def downloadReelsMedia(self, obj=None):
        if obj is None:
            obj=self.getReelsMedia()
        self.d.image_versions2(obj,self.getUserId(),"reels")
        return 
    
    def getPostsMedia(self)->list:
        next=""
        posts=list()
        while True:
            data=self.getPosts(next).json()
            media=data.get("data").get("user").get("edge_owner_to_timeline_media")
            for edge in media.get("edges"):
                resources=edge.get("node").get("thumbnail_resources")
                for resource in resources:
                    resource.update({"id":edge.get("node").get("id")})
                    posts.append(resource)

            if not media.get("page_info").get("has_next_page"):
                break
            next=media.get("page_info").get("end_cursor")
                
        return posts

    def getPosts(self,cursor:str=None)->requests.Response:
        hash="69cba40317214236af40e7efa697781d"
        variables={
            "id":self.getUserId(),
            "first":12
        }
        if cursor:
            variables.update({"after":cursor})
        
        variables =json.dumps(variables)
        return self.session.get(self.graphUrl,params={
            "query_hash":hash,
            "variables":variables
        })
        
    def downloadPosts(self,obj=None):
        if obj is None:
            obj=self.getPostsMedia()
        self.d.thumbnail_resources(obj,self.getUserId())
        return

    def getHighlightsMedia(self)-> list:
        ids = list()
        highligts=list()

        data=self.getHighligts().json()
        reels=data.get("reels")
        for key in reels.keys():
            if key.startswith("highlight"):
                ids.append(key)
        for id in ids:
            for item in reels.get(id).get("items"):
                candidates=item.get("image_versions2").get("candidates")
                videos=item.get("video_versions")
                for candidate in candidates:
                    candidate.update({"pk":item.get("pk")})
                    highligts.append(candidate)
                if videos:
                    for video in videos:
                        video.update({"pk":item.get("pk")})
                        highligts.append(video)
        
        return highligts
    
    def getHighlightIds(self)->requests.Response:
        hash="d4d88dc1500312af6f937f7b804c68c3"
        variables= {
            "user_id":self.getUserId(),
            "include_chaining":True,
            "include_reel":True,
            "include_suggested_users":False,
            "include_logged_out_extras":False,
            "include_highlight_reels":True,
            "include_live_status":True
        }
        variables=json.dumps(variables)
        return self.session.get(self.graphUrl,params={
            "query_hash":hash,
            "variables":variables
        })

    def getHighligts(self)->requests.Response:
        data=self.getHighlightIds().json()
        edges=data.get("data").get("user").get("edge_highlight_reels").get("edges")
        ids=list()
        for edge in edges:
            ids.append(f'highlight:{edge.get("node").get("id")}')
        params="?"
        params+='&'.join(["reel_ids="+id for id in ids]).strip("&")

        return self.session.get(self.apiUrl+"feed/reels_media/"+params)

    def downloadHighlights(self,obj=None):
        if obj is None:
            obj=self.getHighlightsMedia()
        self.d.image_versions2(obj,self.getUserId(),"highligts")
        return

    def getStoriesMedia(self)->list:
        stories= list()
        data=self.getStories().json()
        items=data.get("reels").get(self.getUserId()).get("items")
        for item in items:
            candidates=item.get("image_versions2").get("candidates")
            videos=item.get("video_versions")
            for candidate in candidates:
                candidate.update({"pk":item.get("pk")})
                stories.append(candidate)
            if videos:
                for video in videos:
                    video.update({"pk":item.get("pk")})
                    stories.append(video)
        
        return stories

    def getStories(self)->requests.Response:
        return self.session.get(self.apiUrl+"feed/reels_media/",params={"reel_ids":self.getUserId()})

    def downloadStories(self,obj=None):
        if obj is None:
            obj=self.getStoriesMedia()
        self.d.image_versions2(obj,self.getUserId(),"stories")
        return

    def getFollowers(self)->list:
        return self._hfollow("followers")

    def getFollowings(self)->list:
        return self._hfollow("following")
    
    def _hfollow(self,type:str)->list:
        url=f"{self.apiUrl}friendships/{self.getUserId()}/{type}/"
        rtn=list()
        max_id=0
        while True:
            params={
                "count":100,
                "max_id":max_id
            }
            data=self.session.get(url,params=params).json()
            rtn+=data.get("users")

            if not data.get("next_max_id"):
                break

            max_id=data.get("next_max_id")
        
        return rtn

    def getUserId(self)->str:
        if self.userId is None:
            sys.exit("[ERROR] UserId is required. Use setUserId function")
        return self.userId

    def setUserName(self,username:str)->None:
        url=self.apiUrl+"users/web_profile_info/?username="+username
        r=self.session.get(url)
        if r.status_code != 200:
            sys.stderr.write("[ERROR] User not found: %s",username)
            return None

        user=r.json().get("data").get("user")
        basicInfo={
            "Name":user.get("full_name"),
            "Followers":user.get("edge_followed_by").get("count"),
            "Following":user.get("edge_follow").get("count"),
            "Is Verified":user.get("is_verified"),
            "Profile Picture":user.get("profile_pic_url_hd"),
            "Post count":user.get("edge_owner_to_timeline_media").get("count")
        }
        _Print.printUserInfo(basicInfo)

        self.userId=user.get("id")
        self.username=username
