import requests
from urllib.parse import urlparse
import os
import sys
import logging
import json
import re

class _Session:

    def session(username,password):
        session = requests.Session() 
        url="https://www.instagram.com/"
        session.get(url) #set csrf

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
        session.post(url+"accounts/login/ajax/",headers=headers,data=data) # login request
        
        r=session.get(url).text
        regex=r"\"X-IG-App-ID\".\"(\w*)\"" # get X-Ig-App-Id
        result=re.search(regex,r)

        headers={
            "X-Csrftoken": session.cookies.get_dict().get("csrftoken"),
            "X-Ig-App-Id":result.groups(1)[0]
        }
        session.headers.update(headers)

        return session

class _Download():

    def __init__(self,session):
        self.session = session
        
    def download(self, url:str,filename:str,path:str)->None:
        r=self.session.get(url)
        if r.status_code != 200:
            logging.error("Download failed %s" % url)
        ext = os.path.splitext(urlparse(url).path)[1]
        if ext in [".jpg", ".jpeg",".png",".webp"]:
            type="img"
        elif ext in [".gif", ".mp4", ".webm",".mpeg"]:
            type = "video" 
        else:
            logging.error("Unknown file extension: %s" % ext)
            return False
        path +=type+"/"

        if not os.path.exists(path):
            os.makedirs(path)
        filename=path+filename+ext
        with open(filename, 'wb') as imageFile:
            imageFile.write(r.content)

    def downloadReels(self,obj,userid):
        for o in obj:
            filename=f'{str(o.get("pk"))}-{o.get("width")}x{o.get("height")}'
            path=str(userid)+"/reels/"
            self.download(o.get("url"),filename,path)
        return True
    
    def downloadPosts(self,obj,userid):
        for o in obj:
            filename=f'{str(o.get("id"))}-{o.get("config_width")}x{o.get("config_height")}'
            path=str(userid)+"/posts/"
            self.download(o.get("src"),filename,path)
        return True

class _Print:

    def printUserInfo(basicInfo):
        print("+","-"*100,"+")
        for k, v in basicInfo.items():
            print(k,": ",v)
        print("+","-"*100,"+")

class Instagram():

    def __init__(self,username:str,password:str)->None:
        self.userId=None
        self.username=None
        self.apiUrl="https://i.instagram.com/api/v1/"
        self.graphUrl="https://www.instagram.com/graphql/query/"
        self.reels=list()
        self.posts=list()
        self.session=_Session.session(username,password)
        self.d=_Download(self.session)

    def getReels(self,p:dict={})->list:
        PATH ="clips/user/"
        params={
            "target_user_id": self.getUserId(), 
            "page_size": "12",
            "include_feed_video": "true"
        }
        params.update(p)
        r=self.session.post(self.apiUrl+PATH,data=params)

        if r.status_code != 200 and r.headers.get("Content-Type") != "application/json":
            logging.error("Failed to request %s" % r.status_code)
            sys.exit(1)
        logging.info("Requested %s" % r.status_code)
        data=r.json()
        del r
        max_id=None
        if data.get("paging_info").get("more_available"):
            max_id={"max_id":data["paging_info"]["max_id"]}
        for item in data.get("items"):
            img=item.get("media").get("image_versions2")
            video=item.get("media").get("video_versions")
            pk={"pk":item.get("media").get("pk")}
            if img.get("candidates"):
                for candidate in img.get("candidates"):
                    candidate.update(pk)
                    self.reels.append(candidate)
            
            if video:
                for v in video:
                    v.update(pk)
                    self.reels.append(v)
            if img.get("additional_candidates"):
                ac = img.get("additional_candidates")
                iff = ac.get("igtv_first_frame")
                iff.update(pk)
                ff = ac.get("first_frame")
                ff.update(pk)
                self.reels.append(iff)
                self.reels.append(ff)
        if max_id:
            self.getReels(max_id)

        return self.reels
    
    def downloadReels(self, obj=None):
        if obj is None:
            obj=self.getReels()
        self.d.downloadReels(obj,self.getUserId())
    
    def getPosts(self,cursor:str=None):
        hash="69cba40317214236af40e7efa697781d"
        variables={
            "id":self.getUserId(),
            "first":12
        }
        if cursor is not None:
            variables.update({"after":cursor})
        
        variables =json.dumps(variables)
        r=self.session.get(self.graphUrl,params={
            "query_hash":hash,
            "variables":variables
        })
        media=r.json().get("data").get("user").get("edge_owner_to_timeline_media")
        for edge in media.get("edges"):
            resources=edge.get("node").get("thumbnail_resources")
            for resource in resources:
                resource.update({"id":edge.get("node").get("id")})
                self.posts.append(resource)

        if media.get("page_info").get("has_next_page"):
            self.getPosts(media.get("page_info").get("end_cursor"))

        return self.posts

    def downloadPosts(self,obj=None)->None:
        if obj is None:
            obj=self.getPosts()
        self.d.downloadPosts(obj,self.getUserId())

    def getUserId(self):
        if self.userId is None:
            logging.error("UserId is required. Use setUserId function")
            sys.exit(1)
        return self.userId

    def setUser(self,username:str)->None:
        url=self.apiUrl+"users/web_profile_info/?username="+username
        r=self.session.get(url)
        if r.status_code != 200:
            logging.error("User not found: %s",username)
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

        self.posts=list()
        self.reels=list()
        self.userId=user.get("id")
        self.username=username
