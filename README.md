# Usage

```python
from Instagram import Instagram

i=Instagram("<username>","<password>")

def dumpUser(user):
    i.setUserName(user)
    
    i.downloadHighlights()
    i.downloadPosts()
    i.downloadReelsMedia()
    i.downloadStories()

dumpUser("<user_name>")

```

# Methods
```
getReelsMedia()->list

getReel(max_idstr=None)->requests.Response

downloadReelsMedia(obj=None)

getPostsMedia()->list

getPosts(cursorstr=None)->requests.Response

downloadPosts(obj=None)

getHighlightsMedia()-> list

getHighlightIds()->requests.Response

getHighligts()->requests.Response

downloadHighlights(obj=None)

getStoriesMedia()->list

getStories()->requests.Response

downloadStories(obj=None)

getFollowers()->list

getFollowings()->list

getUserId()->str

setUserName(usernamestr)->None
``` 

It will download files in `<user_id>/(posts|reels)/<type>/<id>-<width>x<height>.<ext>` format
