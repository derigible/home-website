'''
Created on May 17, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import response as resp
from controllers.utils import authenticated, read, err
from db.models import Post as BlogPost
from db.models import Poster as User
from json import loads as load
from django.utils.decorators import method_decorator
from django.db.utils import IntegrityError

class Post(View):
    '''
    The class that handles the posts.
    '''
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all posts. Otherwise, looks
        for args in this manner: y/m/d/<post-name>
        '''
        print("YES")
        if not args:
            return resp(request, BlogPost.objects.all())
        else:
            return resp(request, BlogPost.objects.all())
    
    @method_decorator(authenticated)
    def post(self, request, *args, **kwargs):
        '''
        Creates a new post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "post" {
                    "title" : "<title text>",
                    "text" : "<text>"
                }
                "labels : [
                    "<label name>",...
                ]
            }
        '''
        j = load(read(request))
        bp = BlogPost.objects.create(user = request.user, **j["post"])
        bp.labels = j["labels"]
        return resp(request, (bp,))
        
class Poster(View):
    '''
    The class that handles the poster objects.
    '''
    
    def post(self, request, *args, **kwargs):
        '''
        Creates a new poster. The poster object should be of the following json type:
        
            {
                "email" : "<email>",
                "password" : "<password>"
            }
        '''
        j = load(read(request))
        try:
            p = User.objects.create_user(**j)
            return resp(request, (p,))
        except IntegrityError as ie:
            return err(ie)
        
        
        