'''
Created on May 26, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import response as resp, err, other_response as oresp
from db.models import Label
import json
from django.core.exceptions import ObjectDoesNotExist

class ByLabel(View):
    '''
    Get all the posts of a certain label.
    '''
    
    def get(self, request, *args, **kwargs):
        '''
        Get a list of all posts related to a request. Returns just the post id and title. Must pass in id through the
        path as follows:
        
            /controllers/blog/label/posts/{id}/
            
        Only one id will be considered or an exception will be thrown.
        
        Json returned will be of the following:
        
            [
                {
                "id" : <id>,
                "title" : <title>
                }, ...
            ]
        '''
        if not args:
            return err("Did not provide an id to lookup.")
        try:
            lbl = Label.objects.get(name = args[0][:-1])
        except ObjectDoesNotExist:
            return err("Label {} does not exist.".format(args[0]))
        posts = lbl.posts.values("id", "title")
        return oresp(request, json.dumps([post for post in posts]))