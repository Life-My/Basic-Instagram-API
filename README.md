# Basic-Instagram-API Usage

```python
from Instagram import Instagram

i=Instagram("<username>","<password>")

i.setUser("eminem")
i.downloadPosts()
i.downloadReels()

#### Or

i.setUser("snoopdogg")
posts=i.getPosts()
for post in posts:
  print(post)

i.downloadPosts(posts)

```

It will download files in `<user_id>/(posts|reels)/<type>/<id>-<width>x<height>.<ext>` format
