'''
Created on May 17, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import response as resp, err
from controllers.utils import authenticated, read, has_level
from db.models import Post as BlogPost
from db.models import Poster as User
from json import loads as load
from django.utils.decorators import method_decorator

class Post(View):
    '''
    The class that handles the posts.
    '''
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all posts. Otherwise, looks
        for args in this manner: y/m/d/<post-name>
        '''
        if not args:
            return resp(request, BlogPost.objects.all())
        else:
            return resp(request, BlogPost.objects.all())
    
    @method_decorator(authenticated)
    @method_decorator(has_level(3))
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
        bp.labels.add(*j["labels"])
        return resp(request, (bp,))
        
class Poster(View):
    '''
    The class that handles the poster objects.
    '''
    
    fields = ('email', 'joined_on', 'last_login', 'level')
    
    @method_decorator(authenticated)
    @method_decorator(has_level(2))
    def get(self, request, *args, **kwargs):
        '''
        Get all the posters in the system. The first arg should be the email or the primary key of the 
        user to use
        '''
        if args[0] is not None:
            if args[0].isdigit():
                return resp(request, User.objects.filter(id = args[0]), fields = self.fields)
            else:
                return resp(request, User.objects.filter(email = args[0]), fields = self.fields)
        elif request.user.level >= 4:
            return resp(request, User.objects.all(), fields = self.fields)
        else:
            return err("Your level of {} is not allowed to see all users.".format(User.get_level_name(request.user.level)), 403)
    