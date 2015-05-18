'''
Created on May 17, 2015

@author: derigible
'''
from django.views.generic.base import View
from django.core import serializers
from controllers.response import response as resp
from db.models import Post as BlogPost

class Post(View):
    '''
    The class that handles the posts.
    '''
    
    routes = (
              {"pattern" : '$', "kwargs" : {"django_url_name" : "homepage"}},
              {"pattern" : 'projects/{}/$', "map" : [('(?P<contentType>\w*)',)]},
              )
    
    add_ending = False
    
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